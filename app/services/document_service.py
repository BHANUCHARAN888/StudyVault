from pathlib import Path
from uuid import uuid4
from tempfile import SpooledTemporaryFile

from fastapi import UploadFile
from sqlalchemy import asc, desc, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.document import Document
from app.models.file_deletion_task import FileDeletionTask
from app.models.subject import Subject
from app.models.user import User
from app.schemas.document import DocumentUpdate
from app.services.storage_service import upload_file, delete_file

MAX_FILE_SIZE = settings.max_file_size_mb * 1024 * 1024
CHUNK_SIZE = 1024 * 1024


def upload_document(
    db: Session,
    current_user: User,
    file: UploadFile,
    title: str,
    subject_id: int | None,
) -> Document:
    clean_title = title.strip()

    if not clean_title:
        raise ValueError("Document title cannot be empty")

    if len(clean_title) > 255:
        raise ValueError("Document title cannot exceed 255 characters")

    if not file.filename:
        raise ValueError("Filename is required")

    original_filename = Path(file.filename).name

    if Path(original_filename).suffix.lower() != ".pdf":
        raise ValueError("Only PDF files are allowed")

    if subject_id is not None:
        subject = db.scalar(
            select(Subject).where(
                Subject.id == subject_id,
                Subject.owner_id == current_user.id,
            )
        )
        if subject is None:
            raise LookupError("Subject not found")

    stored_filename = f"{uuid4().hex}.pdf"
    object_key = f"{current_user.id}/{stored_filename}"

    size = 0
    header = b""
    uploaded = False

    try:
        with SpooledTemporaryFile(
            max_size=8 * 1024 * 1024,
            mode="w+b",
        ) as temporary_file:

            while chunk := file.file.read(CHUNK_SIZE):
                size += len(chunk)

                if size > MAX_FILE_SIZE:
                    raise ValueError(
                        f"File exceeds the {settings.max_file_size_mb} MiB limit"
                    )

                if len(header) < 5:
                    header += chunk[: 5 - len(header)]

                temporary_file.write(chunk)

            if size == 0:
                raise ValueError("Uploaded file is empty")

            if header != b"%PDF-":
                raise ValueError(
                    "File does not have a valid PDF signature"
                )

            temporary_file.seek(0)

            upload_file(
                temporary_file,
                object_key,
                content_type="application/pdf",
            )
            uploaded = True

        document = Document(
            title=clean_title,
            original_filename=original_filename,
            stored_filename=stored_filename,
            file_path=object_key,
            file_size=size,
            content_type="application/pdf",
            owner_id=current_user.id,
            subject_id=subject_id,
        )

        db.add(document)
        db.commit()
        db.refresh(document)

        return document

    except Exception:
        db.rollback()

        if uploaded:
            try:
                delete_file(object_key)
            except Exception as cleanup_error:
                try:
                    task = FileDeletionTask(
                        file_path=object_key,
                        attempts=1,
                        last_error=str(cleanup_error)[:2000],
                    )
                    db.add(task)
                    db.commit()

                except Exception:
                    db.rollback()

        raise

def list_documents(
    db: Session,
    current_user: User,
    subject_id: int | None = None,
    search: str | None = None,
    sort_by: str = "created_at",
    order: str = "desc",
    limit: int = 10,
    offset: int = 0,
) -> tuple[list[Document], int]:
    query = select(Document).where(
        Document.owner_id == current_user.id
    )

    if subject_id is not None:
        query = query.where(Document.subject_id == subject_id)

    if search:
        query = query.where(
            Document.title.ilike(f"%{search.strip()}%")
        )

    # Count matching documents before applying pagination.
    count_query = select(func.count()).select_from(query.subquery())
    total = db.scalar(count_query) or 0

    sort_columns = {
        "created_at": Document.created_at,
        "title": Document.title,
        "file_size": Document.file_size,
    }

    column = sort_columns[sort_by]
    sort_expression = asc(column) if order == "asc" else desc(column)
    query = query.order_by(
          sort_expression,
          Document.id.asc(),
    )

    query = query.offset(offset).limit(limit)

    documents = list(db.scalars(query).all())

    return documents, total


def get_document(
    db: Session,
    document_id: int,
    current_user: User,
) -> Document:
    document = db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.owner_id == current_user.id,
        )
    )

    if document is None:
        raise LookupError("Document not found")

    return document


def update_document(
    db: Session,
    document_id: int,
    data: DocumentUpdate,
    current_user: User,
) -> Document:
    document = get_document(db, document_id, current_user)

    changes = data.model_dump(exclude_unset=True)

    if not changes:
        raise ValueError("Provide at least one field to update")

    if "title" in changes:
        if changes["title"] is None:
            raise ValueError("Title cannot be null")
        document.title = changes["title"].strip()

    if "subject_id" in changes:
        subject_id = changes["subject_id"]

        if subject_id is not None:
            subject = db.scalar(
                select(Subject).where(
                    Subject.id == subject_id,
                    Subject.owner_id == current_user.id,
                )
            )
            if subject is None:
                raise LookupError("Subject not found")

        document.subject_id = subject_id

    try:
        db.commit()
        db.refresh(document)
        return document
    except Exception:
        db.rollback()
        raise


def delete_document(
    db: Session,
    document_id: int,
    current_user: User,
) -> None:
    document = get_document(db, document_id, current_user)
    object_key = document.file_path

    try:
        # Record the cleanup task and delete the document
        # in the same database transaction.
        task = FileDeletionTask(file_path=object_key)
        db.add(task)
        db.delete(document)
        db.commit()

    except Exception:
        db.rollback()
        raise

    # Attempt deletion from Backblaze B2.
    try:
        delete_file(object_key)

        db.delete(task)
        db.commit()

    except Exception as exc:
        db.rollback()

        # Preserve the cleanup task for a later retry.
        try:
            pending_task = (
                db.query(FileDeletionTask)
                .filter(
                    FileDeletionTask.file_path == object_key
                )
                .first()
            )

            if pending_task is not None:
                pending_task.attempts += 1
                pending_task.last_error = str(exc)[:2000]
                db.commit()

        except Exception:
            db.rollback()
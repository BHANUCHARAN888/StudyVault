from pathlib import Path
from uuid import uuid4

from sqlalchemy import asc, desc, func, select

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.document import Document
from app.models.subject import Subject
from app.models.user import User
from app.schemas.document import DocumentUpdate
from app.models.file_deletion_task import FileDeletionTask

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
    storage_dir = settings.storage_path / str(current_user.id)
    storage_dir.mkdir(parents=True, exist_ok=True)
    destination = storage_dir / stored_filename

    size = 0
    header = b""

    try:
        with destination.open("wb") as output:
            while chunk := file.file.read(CHUNK_SIZE):
                size += len(chunk)

                if size > MAX_FILE_SIZE:
                    raise ValueError(
                        f"File exceeds the {settings.max_file_size_mb} MiB limit"
                    )

                if len(header) < 5:
                    header += chunk[: 5 - len(header)]

                output.write(chunk)

        if size == 0:
            raise ValueError("Uploaded file is empty")

        if header != b"%PDF-":
           raise ValueError("File does not have a valid PDF signature")

        document = Document(
            title=clean_title,
            original_filename=original_filename,
            stored_filename=stored_filename,
            file_path=str(destination),
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
        destination.unlink(missing_ok=True)
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
    query = query.order_by(
        asc(column) if order == "asc" else desc(column)
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
    file_path = document.file_path

    try:
        # Record the cleanup task and delete the document
        # in the same database transaction.
        task = FileDeletionTask(file_path=file_path)
        db.add(task)
        db.delete(document)
        db.commit()

    except Exception:
        db.rollback()
        raise

    # The database deletion has succeeded. Attempt physical cleanup.
    # Keep the task in the database if file removal fails.
    try:
        Path(file_path).unlink(missing_ok=True)

        db.delete(task)
        db.commit()

    except Exception as exc:
        db.rollback()

        # Record the cleanup failure for a later retry.
        try:
            pending_task = (
                db.query(FileDeletionTask)
                .filter(FileDeletionTask.file_path == file_path)
                .first()
            )

            if pending_task is not None:
                pending_task.attempts += 1
                pending_task.last_error = str(exc)[:2000]
                db.commit()

        except Exception:
            db.rollback()

from typing import Annotated
from urllib.parse import quote

from botocore.exceptions import ClientError
from fastapi.responses import StreamingResponse
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status, Query, Response
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.db.dependencies import get_db
from app.models.user import User
from app.schemas.document import DocumentResponse, DocumentUpdate
from app.services.document_service import (
    delete_document,
    get_document,
    list_documents,
    update_document,
    upload_document,
)
from app.services.storage_service import download_file

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("/", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
def upload(
    file: Annotated[UploadFile, File()],
    title: Annotated[str, Form()],
    subject_id: Annotated[int | None, Form()] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return upload_document(db, current_user, file, title, subject_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/", response_model=list[DocumentResponse])
def list_all(
    response: Response,
    subject_id: int | None = None,
    search: str | None = None,
    sort_by: str = Query(
        default="created_at",
        pattern="^(created_at|title|file_size)$",
    ),
    order: str = Query(
        default="desc",
        pattern="^(asc|desc)$",
    ),
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    documents, total = list_documents(
        db=db,
        current_user=current_user,
        subject_id=subject_id,
        search=search,
        sort_by=sort_by,
        order=order,
        limit=limit,
        offset=offset,
    )
    response.headers["X-Total-Count"] = str(total)
    return documents

@router.get("/{document_id}/file")
def open_document_file(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        document = get_document(db, document_id, current_user)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    try:
        file_body = download_file(document.file_path)

    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code")

        if error_code in ("NoSuchKey", "404", "NotFound"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="PDF file not found",
            ) from exc

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to retrieve PDF from storage",
        ) from exc

    def stream_file():
        try:
            while chunk := file_body.read(1024 * 1024):
                yield chunk
        finally:
            file_body.close()

    filename = quote(document.original_filename)

    return StreamingResponse(
        stream_file(),
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f"inline; filename*=UTF-8''{filename}"
            )
        },
    )

@router.get("/{document_id}", response_model=DocumentResponse)
def get_one(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return get_document(db, document_id, current_user)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{document_id}", response_model=DocumentResponse)
def update(
    document_id: int,
    data: DocumentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return update_document(db, document_id, data, current_user)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        delete_document(db, document_id, current_user)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

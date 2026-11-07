import pytest
import jwt

from pathlib import Path
from datetime import datetime, timedelta, timezone

from app.main import app

from fastapi import UploadFile
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base
from app.db.dependencies import get_db

from app.core.config import settings
from app.models.file_deletion_task import FileDeletionTask
from app.models import Document, User
from app.services.file_cleanup_service import retry_file_deletions
from app.services.auth_service import create_password_reset_token


TEST_DATABASE_URL = "sqlite://"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    bind=test_engine,
    autoflush=False,
    expire_on_commit=False,
)


@pytest.fixture
def client(tmp_path, monkeypatch):
    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)

def test_register_user(client):
    response = client.post(
        "/auth/register",
        json={
            "email": "student@example.com",
            "password": "StudyVault123",
        },
    )

    assert response.status_code == 201
    assert response.json()["email"] == "student@example.com"
    assert response.json()["is_verified"] is False
    assert "hashed_password" not in response.json()

def register_and_verify(client, email, password, monkeypatch):
    monkeypatch.setattr(
        "app.services.auth_service.send_verification_email",
        lambda recipient_email, verification_url: None,
    )

    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
        },
    )
    assert response.status_code == 201, response.json()

    db = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        assert user is not None
        user.is_verified = True
        db.commit()
    finally:
        db.close()

def test_duplicate_registration(client):
    payload = {
        "email": "student@example.com",
        "password": "StudyVault123",
    }

    first_response = client.post("/auth/register", json=payload)
    second_response = client.post("/auth/register", json=payload)

    assert first_response.status_code == 201
    assert second_response.status_code == 409


def test_auth_me_requires_token(client):
    response = client.get("/auth/me")

    assert response.status_code == 401

def test_login_returns_access_token(client, monkeypatch):
    register_and_verify(
        client,
        "student@example.com",
        "StudyVault123",
        monkeypatch,
    )

    response = client.post(
        "/auth/login",
        json={
            "email": "student@example.com",
            "password": "StudyVault123",
        },
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]


def test_login_rejects_wrong_password(client, monkeypatch):
    register_and_verify(
        client,
        "student@example.com",
        "StudyVault123",
        monkeypatch,
    )

    response = client.post(
        "/auth/login",
        json={
            "email": "student@example.com",
            "password": "WrongPass123",
        },
    )

    assert response.status_code == 401

def test_auth_me_with_valid_token(client, monkeypatch):
    register_and_verify(
        client,
        "student@example.com",
        "StudyVault123",
        monkeypatch,
    )

    login_response = client.post(
        "/auth/login",
        json={
            "email": "student@example.com",
            "password": "StudyVault123",
        },
    )
    assert login_response.status_code == 200, login_response.json()

    token = login_response.json()["access_token"]
    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == "student@example.com"

def register_and_login(client, email, monkeypatch):
    register_and_verify(
        client,
        email,
        "StudyVault123",
        monkeypatch,
    )

    response = client.post(
        "/auth/login",
        json={
            "email": email,
            "password": "StudyVault123",
        },
    )

    assert response.status_code == 200, response.json()

    return {
        "Authorization": f"Bearer {response.json()['access_token']}"
    }


def test_user_cannot_access_another_users_document(client, monkeypatch):
    owner_headers = register_and_login(
        client, "owner@example.com", monkeypatch,
    )
    other_headers = register_and_login(
        client, "other@example.com", monkeypatch,
    )

    # Create a subject owned by the first user.
    subject_response = client.post(
        "/subjects/",
        json={"name": "Python"},
        headers=owner_headers,
    )
    assert subject_response.status_code == 201

    subject_id = subject_response.json()["id"]

    # Create a real-looking minimal PDF for the upload test.
    pdf_content = (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog>>endobj\n"
        b"%%EOF"
    )

    upload_response = client.post(
        "/documents/",
        headers=owner_headers,
        data={
            "title": "Private Notes",
            "subject_id": str(subject_id),
        },
        files={
            "file": (
                "notes.pdf",
                pdf_content,
                "application/pdf",
            )
        },
    )

    assert upload_response.status_code == 201
    document_id = upload_response.json()["id"]

    # Another user must not be able to read the document.
    response = client.get(
        f"/documents/{document_id}",
        headers=other_headers,
    )

    assert response.status_code == 404

    # Another user must not see it in their document list.
    response = client.get(
        "/documents/",
        headers=other_headers,
    )

    assert response.status_code == 200
    assert all(
        doc["id"] != document_id
        for doc in response.json()
    )

def test_auth_me_rejects_invalid_token(client):
    response = client.get(
        "/auth/me",
        headers={"Authorization": "Bearer invalid.token.value"},
    )

    assert response.status_code == 401

def test_auth_me_rejects_expired_token(client):
    expired_payload = {
        "sub": "1",
        "exp": datetime.now(timezone.utc) - timedelta(minutes=5),
    }

    expired_token = jwt.encode(
        expired_payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )

    assert response.status_code == 401

def test_user_cannot_update_or_delete_another_users_subject(client, monkeypatch):
    owner_headers = register_and_login(
        client, "subject_owner@example.com", monkeypatch
    )
    other_headers = register_and_login(
        client, "subject_other@example.com", monkeypatch
    )

    # Owner creates a subject.
    create_response = client.post(
        "/subjects/",
        json={"name": "Python"},
        headers=owner_headers,
    )

    assert create_response.status_code == 201
    subject_id = create_response.json()["id"]

    # Another user attempts to rename it.
    update_response = client.patch(
        f"/subjects/{subject_id}",
        json={"name": "Hacked Subject"},
        headers=other_headers,
    )

    assert update_response.status_code == 404

    # Another user attempts to delete it.
    delete_response = client.delete(
        f"/subjects/{subject_id}",
        headers=other_headers,
    )

    assert delete_response.status_code == 404

    # Confirm the original owner still has the subject.
    list_response = client.get(
        "/subjects/",
        headers=owner_headers,
    )

    assert list_response.status_code == 200
    assert any(
        subject["id"] == subject_id
        and subject["name"] == "Python"
        for subject in list_response.json()
    )

def test_user_cannot_assign_another_users_subject_to_document(client, monkeypatch):
    owner_headers = register_and_login(
        client, "owner_subject@example.com", monkeypatch
    )
    other_headers = register_and_login(
        client, "other_subject@example.com", monkeypatch
    )

    # User A creates a private subject.
    subject_response = client.post(
        "/subjects/",
        json={"name": "Private Python"},
        headers=owner_headers,
    )

    assert subject_response.status_code == 201
    subject_id = subject_response.json()["id"]

    # User B tries to upload a PDF using User A's subject.
    pdf_content = (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog>>endobj\n"
        b"%%EOF"
    )

    upload_response = client.post(
        "/documents/",
        headers=other_headers,
        data={
            "title": "My Notes",
            "subject_id": str(subject_id),
        },
        files={
            "file": (
                "notes.pdf",
                pdf_content,
                "application/pdf",
            )
        },
    )

    # The API must reject the cross-user subject assignment.
    assert upload_response.status_code == 404

    # User A's subject must remain intact.
    list_response = client.get(
        "/subjects/",
        headers=owner_headers,
    )

    assert list_response.status_code == 200
    assert any(
        subject["id"] == subject_id
        and subject["name"] == "Private Python"
        for subject in list_response.json()
    )

def test_upload_rejects_non_pdf_extension(client, monkeypatch):
    headers = register_and_login(client, "nonpdf@example.com", monkeypatch)

    response = client.post(
        "/documents/",
        headers=headers,
        data={"title": "Not a PDF"},
        files={
            "file": (
                "notes.txt",
                b"This is not a PDF",
                "text/plain",
            )
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Only PDF files are allowed"


def test_upload_rejects_invalid_pdf_signature(client, monkeypatch):
    headers = register_and_login(client, "invalidpdf@example.com", monkeypatch)

    response = client.post(
        "/documents/",
        headers=headers,
        data={"title": "Invalid PDF"},
        files={
            "file": (
                "notes.pdf",
                b"This is not a real PDF",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "File does not have a valid PDF signature"
    )


def test_upload_rejects_empty_pdf(client, monkeypatch):
    headers = register_and_login(client, "emptypdf@example.com", monkeypatch)

    response = client.post(
        "/documents/",
        headers=headers,
        data={"title": "Empty PDF"},
        files={
            "file": (
                "empty.pdf",
                b"",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Uploaded file is empty"

def test_upload_rejects_file_over_size_limit(client, monkeypatch):
    import app.services.document_service as document_service

    headers = register_and_login(client, "largefile@example.com", monkeypatch)

    # Use a small limit so the test doesn't need a 50 MiB file.
    monkeypatch.setattr(document_service, "MAX_FILE_SIZE", 10)

    response = client.post(
        "/documents/",
        headers=headers,
        data={"title": "Too Large"},
        files={
            "file": (
                "large.pdf",
                b"%PDF-1.4\nThis content exceeds the limit",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 400
    assert "exceeds" in response.json()["detail"].lower()

def test_failed_upload_does_not_upload_to_b2(client, monkeypatch):
    from app.services import document_service

    headers = register_and_login(
        client,
        "cleanup@example.com",
        monkeypatch,
    )

    upload_calls = []

    def track_upload(file_object, object_key, content_type):
        upload_calls.append(object_key)

    monkeypatch.setattr(
        document_service,
        "upload_file",
        track_upload,
    )

    response = client.post(
        "/documents/",
        headers=headers,
        data={"title": "Invalid PDF"},
        files={
            "file": (
                "invalid.pdf",
                b"Not a PDF",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 400
    assert "valid PDF signature" in response.json()["detail"]
    assert upload_calls == []

def test_download_document_file(client, monkeypatch):
    from app.routers import documents as documents_router

    headers = register_and_login(
        client,
        "download@example.com",
        monkeypatch,
    )

    pdf_content = b"%PDF-1.4\nTest PDF content\n%%EOF"

    upload_response = client.post(
        "/documents/",
        headers=headers,
        data={"title": "Download test"},
        files={
            "file": (
                "download.pdf",
                pdf_content,
                "application/pdf",
            )
        },
    )

    assert upload_response.status_code == 201
    document_id = upload_response.json()["id"]

    class FakeFileBody:
        def __init__(self, content):
            self.content = content

        def read(self, size=-1):
            if not self.content:
                return b""

            chunk = self.content[:size]
            self.content = self.content[size:]
            return chunk

        def close(self):
            pass

    monkeypatch.setattr(
        documents_router,
        "download_file",
        lambda object_key: FakeFileBody(pdf_content),
    )

    response = client.get(
        f"/documents/{document_id}/file",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.content == pdf_content
    assert response.headers["content-type"] == "application/pdf"
    assert "inline" in response.headers["content-disposition"]


def test_user_cannot_download_another_users_document(client, monkeypatch):
    from app.routers import documents as documents_router

    owner_headers = register_and_login(
        client,
        "download-owner@example.com",
        monkeypatch,
    )

    pdf_content = b"%PDF-1.4\nPrivate PDF content\n%%EOF"

    upload_response = client.post(
        "/documents/",
        headers=owner_headers,
        data={"title": "Private document"},
        files={
            "file": (
                "private.pdf",
                pdf_content,
                "application/pdf",
            )
        },
    )

    assert upload_response.status_code == 201
    document_id = upload_response.json()["id"]

    other_user_headers = register_and_login(
        client,
        "download-other@example.com",
        monkeypatch,
    )

    def unexpected_download(object_key):
        raise AssertionError("B2 download must not be called")

    monkeypatch.setattr(
        documents_router,
        "download_file",
        unexpected_download,
    )

    response = client.get(
        f"/documents/{document_id}/file",
        headers=other_user_headers,
    )

    assert response.status_code == 404


def test_download_returns_404_when_b2_file_missing(client, monkeypatch):
    from botocore.exceptions import ClientError
    from app.routers import documents as documents_router

    headers = register_and_login(
        client,
        "missing-file@example.com",
        monkeypatch,
    )

    pdf_content = b"%PDF-1.4\nTest PDF content\n%%EOF"

    upload_response = client.post(
        "/documents/",
        headers=headers,
        data={"title": "Missing file test"},
        files={
            "file": (
                "missing.pdf",
                pdf_content,
                "application/pdf",
            )
        },
    )

    assert upload_response.status_code == 201
    document_id = upload_response.json()["id"]

    def missing_file(object_key):
        raise ClientError(
            {
                "Error": {
                    "Code": "NoSuchKey",
                    "Message": "The specified key does not exist",
                }
            },
            "GetObject",
        )

    monkeypatch.setattr(
        documents_router,
        "download_file",
        missing_file,
    )

    response = client.get(
        f"/documents/{document_id}/file",
        headers=headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "PDF file not found"

def test_password_reset_revokes_old_access_token(
    client,
    monkeypatch,
):
    email = "revocation@example.com"
    password = "OldPassword123"

    register_and_verify(client, email, password, monkeypatch)

    login_response = client.post(
    "/auth/login",
    json={
        "email": email,
        "password": password,
    },
)

    assert login_response.status_code == 200

    old_token = login_response.json()["access_token"]
    old_headers = {"Authorization": f"Bearer {old_token}"}

    # Confirm the old token works before password reset.
    response = client.get("/auth/me", headers=old_headers)
    assert response.status_code == 200

    # Create a valid password-reset token directly for this test.
    db = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        raw_reset_token = create_password_reset_token(db, user)
        db.commit()
    finally:
        db.close()

    reset_response = client.post(
        "/auth/reset-password",
        json={
            "token": raw_reset_token,
            "new_password": "NewPassword123",
        },
    )

    assert reset_response.status_code == 200

    # Old access token must now be rejected.
    response = client.get("/auth/me", headers=old_headers)
    assert response.status_code == 401


def test_failed_file_deletion_can_be_retried(client, monkeypatch):
    from app.services import document_service, file_cleanup_service

    headers = register_and_login(
        client,
        "cleanup@example.com",
        monkeypatch,
    )

    pdf_content = b"%PDF-1.4\nTest PDF content\n%%EOF"

    response = client.post(
        "/documents/",
        headers=headers,
        data={"title": "Cleanup test"},
        files={
            "file": (
                "cleanup.pdf",
                pdf_content,
                "application/pdf",
            )
        },
    )

    assert response.status_code == 201
    document_id = response.json()["id"]

    db = TestingSessionLocal()

    try:
        document = db.query(Document).filter_by(id=document_id).first()
        assert document is not None

        object_key = document.file_path
        owner = document.owner

        def failing_delete(object_key):
            raise PermissionError("Simulated B2 deletion failure")

        monkeypatch.setattr(document_service, "delete_file", failing_delete)

        document_service.delete_document(db, document_id, owner)

        assert db.query(Document).filter_by(id=document_id).first() is None

        task = (
            db.query(FileDeletionTask)
            .filter_by(file_path=object_key)
            .first()
        )

        assert task is not None
        assert task.attempts >= 1
        assert "Simulated B2 deletion failure" in task.last_error

        deleted_objects = []

        def successful_delete(object_key):
            deleted_objects.append(object_key)

        monkeypatch.setattr(
            file_cleanup_service,
            "delete_file",
            successful_delete,
        )

        result = retry_file_deletions(db)

        assert result == {"deleted": 1, "failed": 0}
        assert deleted_objects == [object_key]

        assert (
            db.query(FileDeletionTask)
            .filter_by(file_path=object_key)
            .first()
            is None
        )

    finally:
        db.close()


def test_list_documents_search_filter_sort_and_pagination(
    client, monkeypatch
):
    headers = register_and_login(
        client,
        "listing@example.com",
        monkeypatch,
    )

    # Create two subjects.
    python_response = client.post(
        "/subjects/",
        json={"name": "Python"},
        headers=headers,
    )
    assert python_response.status_code == 201
    python_id = python_response.json()["id"]

    sql_response = client.post(
        "/subjects/",
        json={"name": "SQL"},
        headers=headers,
    )
    assert sql_response.status_code == 201
    sql_id = sql_response.json()["id"]

    # Upload three documents.
    pdf = b"%PDF-1.4\nTest PDF content\n%%EOF"

    documents = [
        ("Python Basics", python_id),
        ("Advanced Python", python_id),
        ("SQL Basics", sql_id),
    ]

    for title, subject_id in documents:
        response = client.post(
            "/documents/",
            headers=headers,
            data={
                "title": title,
                "subject_id": str(subject_id),
            },
            files={
                "file": (
                    f"{title}.pdf",
                    pdf,
                    "application/pdf",
                )
            },
        )
        assert response.status_code == 201, response.json()

    # 1. Search should return only matching documents.
    response = client.get(
        "/documents/?search=python",
        headers=headers,
    )

    assert response.status_code == 200
    assert len(response.json()) == 2
    assert all("Python" in doc["title"] for doc in response.json())

    # 2. Subject filtering.
    response = client.get(
        f"/documents/?subject_id={sql_id}",
        headers=headers,
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["title"] == "SQL Basics"

    # 3. Ascending title sorting.
    response = client.get(
        "/documents/?sort_by=title&order=asc",
        headers=headers,
    )

    assert response.status_code == 200
    titles = [doc["title"] for doc in response.json()]
    assert titles == sorted(titles)

    # 4. Descending title sorting.
    response = client.get(
        "/documents/?sort_by=title&order=desc",
        headers=headers,
    )

    assert response.status_code == 200
    titles = [doc["title"] for doc in response.json()]
    assert titles == sorted(titles, reverse=True)

    # 5. Pagination and total matching count.
    response = client.get(
        "/documents/?limit=2&offset=0",
        headers=headers,
    )

    assert response.status_code == 200
    assert len(response.json()) == 2
    assert response.headers["X-Total-Count"] == "3"

    response = client.get(
        "/documents/?limit=2&offset=2",
        headers=headers,
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.headers["X-Total-Count"] == "3"


def test_list_documents_rejects_invalid_query_parameters(
    client, monkeypatch
):
    headers = register_and_login(
        client,
        "invalid-params@example.com",
        monkeypatch,
    )

    invalid_queries = [
        "?sort_by=invalid",
        "?order=random",
        "?limit=0",
        "?limit=101",
        "?offset=-1",
    ]

    for query in invalid_queries:
        response = client.get(
            f"/documents/{query}",
            headers=headers,
        )

        assert response.status_code == 422, (
            f"Expected 422 for {query}, got {response.status_code}"
        )

def test_subject_crud_flow(client, monkeypatch):
    headers = register_and_login(
        client,
        "subject-crud@example.com",
        monkeypatch,
    )

    # Create
    create_response = client.post(
        "/subjects/",
        headers=headers,
        json={"name": "Python"},
    )

    assert create_response.status_code == 201
    subject = create_response.json()
    subject_id = subject["id"]
    assert subject["name"] == "Python"

    # List
    list_response = client.get(
        "/subjects/",
        headers=headers,
    )

    assert list_response.status_code == 200
    assert any(item["id"] == subject_id for item in list_response.json())

    # Update
    update_response = client.patch(
        f"/subjects/{subject_id}",
        headers=headers,
        json={"name": "Advanced Python"},
    )

    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Advanced Python"

    # Delete
    delete_response = client.delete(
        f"/subjects/{subject_id}",
        headers=headers,
    )

    assert delete_response.status_code == 204

    # Verify deletion
    get_response = client.get(
        "/subjects/",
        headers=headers,
    )

    assert all(
        item["id"] != subject_id
        for item in get_response.json()
    )

def test_document_update_validation(client, monkeypatch):
    headers = register_and_login(
        client,
        "document-update@example.com",
        monkeypatch,
    )

    upload_response = client.post(
        "/documents/",
        headers=headers,
        data={"title": "Original Title"},
        files={
            "file": (
                "original.pdf",
                b"%PDF-1.4 test content",
                "application/pdf",
            )
        },
    )

    assert upload_response.status_code == 201
    document_id = upload_response.json()["id"]

    invalid_updates = [
    ({"title": ""}, 422),
    ({"title": "   "}, 422),
    ({"title": None}, 400),
    ({"unexpected_field": "value"}, 422),
]

    for payload, expected_status in invalid_updates:
        response = client.patch(
             f"/documents/{document_id}",
             headers=headers,
             json=payload,
    )

        assert response.status_code == expected_status, (
            f"Expected {expected_status} for {payload}, "
            f"got {response.status_code}"
        )

    get_response = client.get(
        f"/documents/{document_id}",
        headers=headers,
    )

    assert get_response.status_code == 200
    assert get_response.json()["title"] == "Original Title"

def test_document_delete_success(client, monkeypatch):
    headers = register_and_login(
        client,
        "document-delete@example.com",
        monkeypatch,
    )

    from app.services import document_service

    uploaded_objects = []
    deleted_objects = []

    def fake_upload_file(file, object_key, content_type):
        uploaded_objects.append(object_key)

    def fake_delete_file(object_key):
        deleted_objects.append(object_key)

    monkeypatch.setattr(
        document_service,
        "upload_file",
        fake_upload_file,
    )
    monkeypatch.setattr(
        document_service,
        "delete_file",
        fake_delete_file,
    )

    upload_response = client.post(
        "/documents/",
        headers=headers,
        data={"title": "Delete Me"},
        files={
            "file": (
                "delete-me.pdf",
                b"%PDF-1.4 test content",
                "application/pdf",
            )
        },
    )

    assert upload_response.status_code == 201

    document_id = upload_response.json()["id"]
    object_key = uploaded_objects[0]

    # Delete document
    delete_response = client.delete(
        f"/documents/{document_id}",
        headers=headers,
    )

    assert delete_response.status_code == 204

    # Verify B2 deletion
    assert deleted_objects == [object_key]

    # Verify document no longer exists
    get_response = client.get(
        f"/documents/{document_id}",
        headers=headers,
    )

    assert get_response.status_code == 404

    # Verify cleanup task was removed after successful B2 deletion
    from app.models.file_deletion_task import FileDeletionTask

    with TestingSessionLocal() as db:
        task = (
            db.query(FileDeletionTask)
            .filter(FileDeletionTask.file_path == object_key)
            .first()
        )

        assert task is None

def test_user_cannot_delete_another_users_document(client, monkeypatch):
    from app.services import document_service

    owner_headers = register_and_login(
        client,
        "document-owner@example.com",
        monkeypatch,
    )

    other_user_headers = register_and_login(
        client,
        "document-other@example.com",
        monkeypatch,
    )

    deleted_objects = []

    def fake_upload_file(file, object_key, content_type):
        pass

    def fake_delete_file(object_key):
        deleted_objects.append(object_key)

    monkeypatch.setattr(
        document_service,
        "upload_file",
        fake_upload_file,
    )
    monkeypatch.setattr(
        document_service,
        "delete_file",
        fake_delete_file,
    )

    upload_response = client.post(
        "/documents/",
        headers=owner_headers,
        data={"title": "Private Document"},
        files={
            "file": (
                "private.pdf",
                b"%PDF-1.4 test content",
                "application/pdf",
            )
        },
    )

    assert upload_response.status_code == 201
    document_id = upload_response.json()["id"]

    # Another user attempts deletion.
    delete_response = client.delete(
        f"/documents/{document_id}",
        headers=other_user_headers,
    )

    assert delete_response.status_code == 404

    # B2 deletion must not be attempted.
    assert deleted_objects == []

    # Original owner must still access the document.
    get_response = client.get(
        f"/documents/{document_id}",
        headers=owner_headers,
    )

    assert get_response.status_code == 200
    assert get_response.json()["title"] == "Private Document"



def test_failed_upload_cleanup_creates_deletion_task(client, monkeypatch):
    from unittest.mock import patch
    from fastapi import UploadFile
    from io import BytesIO
    from app.services import document_service

    register_and_login(
        client,
        "orphan-cleanup@example.com",
        monkeypatch,
    )

    uploaded_objects = []

    def fake_upload(file_object, object_key, content_type):
        uploaded_objects.append(object_key)

    def failing_delete(object_key):
        raise PermissionError("Simulated B2 cleanup failure")

    monkeypatch.setattr(document_service, "upload_file", fake_upload)
    monkeypatch.setattr(document_service, "delete_file", failing_delete)

    db = TestingSessionLocal()

    try:
        original_commit = db.commit
        commit_calls = 0

        def commit_with_one_failure():
            nonlocal commit_calls
            commit_calls += 1

            if commit_calls == 1:
                raise RuntimeError("Simulated database failure")

            original_commit()

        with patch.object(
            db,
            "commit",
            side_effect=commit_with_one_failure,
        ):
            with pytest.raises(
                RuntimeError,
                match="Simulated database failure",
            ):
                document_service.upload_document(
                    db=db,
                    current_user=db.query(User).filter_by(
                        email="orphan-cleanup@example.com"
                    ).first(),
                    file=UploadFile(
                        filename="orphan.pdf",
                        file=BytesIO(
                            b"%PDF-1.4\nTest PDF\n%%EOF"
                        ),
                    ),
                    title="Orphan test",
                    subject_id=None,
                )

        assert len(uploaded_objects) == 1
        assert db.query(Document).count() == 0

        task = db.query(FileDeletionTask).filter_by(
            file_path=uploaded_objects[0]
        ).first()

        assert task is not None
        assert task.attempts == 1
        assert "Simulated B2 cleanup failure" in task.last_error

    finally:
        db.close()

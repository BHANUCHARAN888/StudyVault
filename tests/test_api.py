import pytest
import jwt

from pathlib import Path
from datetime import datetime, timedelta, timezone

from app.main import app

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

    monkeypatch.setattr(settings, "storage_dir", str(tmp_path))

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


def test_failed_upload_does_not_leave_file(client, monkeypatch, tmp_path):
    headers = register_and_login(client, "cleanup@example.com", monkeypatch)

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

    # No files should remain after the failed upload.
    stored_files = list(tmp_path.rglob("*.pdf"))
    assert stored_files == []

def test_failed_file_deletion_can_be_retried(client, monkeypatch):
    from app.services import document_service

    headers = register_and_login(client, "cleanup@example.com", monkeypatch)

    # Upload a valid PDF.
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

    assert response.status_code == 201, response.text
    document_id = response.json()["id"]

    db = TestingSessionLocal()

    try:
        document = db.query(Document).filter_by(id=document_id).first()
        assert document is not None

        file_path = Path(document.file_path)
        assert file_path.exists()

        # Simulate a filesystem permission failure for this file.
        original_unlink = Path.unlink

        def failing_unlink(self, *args, **kwargs):
            if self.resolve() == file_path.resolve():
                raise PermissionError("Simulated file lock")
            return original_unlink(self, *args, **kwargs)

        monkeypatch.setattr(Path, "unlink", failing_unlink)

        document_service.delete_document(
            db,
            document_id,
            document.owner,
        )

        # The database record is gone, but the PDF remains.
        assert db.query(Document).filter_by(id=document_id).first() is None
        assert file_path.exists()

        task = (
            db.query(FileDeletionTask)
            .filter_by(file_path=str(file_path))
            .first()
        )

        assert task is not None
        assert task.attempts >= 1
        assert "Simulated file lock" in task.last_error

        # Restore normal file deletion and retry the task.
        monkeypatch.setattr(Path, "unlink", original_unlink)

        result = retry_file_deletions(db)

        assert result == {"deleted": 1, "failed": 0}
        assert not file_path.exists()

        assert (
            db.query(FileDeletionTask)
            .filter_by(file_path=str(file_path))
            .first()
            is None
        )

    finally:
        db.close()

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
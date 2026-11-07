from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    generate_verification_token,
    hash_verification_token,
    generate_password_reset_token,
    hash_password_reset_token,
)
from app.models.password_reset_token import PasswordResetToken
from app.models.email_verification_token import EmailVerificationToken
from app.services.email_service import (
    send_verification_email,
    send_password_reset_email,
)
from app.models.user import User
from app.schemas.auth import UserRegister, UserLogin

def create_email_verification_token(
    db: Session,
    user: User,
) -> str:
    raw_token = generate_verification_token()
    token_hash = hash_verification_token(raw_token)

    verification_token = EmailVerificationToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
    )

    db.add(verification_token)
    db.flush()

    return raw_token

def create_password_reset_token(
    db: Session,
    user: User,
) -> str:
    raw_token = generate_password_reset_token()
    token_hash = hash_password_reset_token(raw_token)

    reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
    )

    db.add(reset_token)
    db.flush()

    return raw_token

def request_password_reset(
    db: Session,
    email: str,
) -> None:
    normalized_email = email.strip().lower()

    user = db.scalar(
        select(User).where(User.email == normalized_email)
    )

    # Always return silently if the account doesn't exist.
    if user is None or not user.is_active or not user.is_verified:
        return

    try:
        # Remove any previous reset token for this user.
        existing_token = db.scalar(
            select(PasswordResetToken).where(
                PasswordResetToken.user_id == user.id
            )
        )

        if existing_token is not None:
            db.delete(existing_token)
            db.flush()

        raw_token = create_password_reset_token(db, user)
        db.commit()

    except Exception:
        db.rollback()
        raise

    reset_url = (
        f"{settings.frontend_url.rstrip('/')}"
        f"/reset-password?token={quote(raw_token, safe='')}"
    )

    send_password_reset_email(
        recipient_email=user.email,
        reset_url=reset_url,
    )

def reset_password(
    db: Session,
    raw_token: str,
    new_password: str,
) -> User:
    token_hash = hash_password_reset_token(raw_token)

    reset_token = db.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash
        )
    )

    if reset_token is None:
        raise ValueError("Invalid or expired password reset link")

    expires_at = reset_token.expires_at

    if expires_at.tzinfo is None:
       expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at <= datetime.now(timezone.utc):
        db.delete(reset_token)
        db.commit()
        raise ValueError("Invalid or expired password reset link")

    user = db.get(User, reset_token.user_id)

    if user is None or not user.is_active or not user.is_verified:
        db.delete(reset_token)
        db.commit()
        raise ValueError("Invalid or expired password reset link")

    try:
        user.hashed_password = hash_password(new_password)
        user.token_version += 1

        db.delete(reset_token)
        db.commit()
        db.refresh(user)

    except Exception:
        db.rollback()
        raise

    return user

def register_user(
    db: Session,
    user_data: UserRegister,
) -> User:
    normalized_email = str(user_data.email).strip().lower()

    existing_user = db.scalar(
        select(User).where(User.email == normalized_email)
    )

    if existing_user is not None:
        raise ValueError("Email is already registered")

    user = User(
        email=normalized_email,
        hashed_password=hash_password(user_data.password),
        is_verified=False,
        is_active=True,
    )

    try:
        db.add(user)
        db.flush()

        raw_token = create_email_verification_token(db, user)

        db.commit()
        db.refresh(user)

    except Exception:
        db.rollback()
        raise

    verification_url = (
        f"{settings.frontend_url.rstrip('/')}"
        f"/verify-email?token={quote(raw_token, safe='')}"
    )

    send_verification_email(
        recipient_email=user.email,
        verification_url=verification_url,
    )

    return user

def verify_email_token(
    db: Session,
    raw_token: str,
) -> User:
    token_hash = hash_verification_token(raw_token)

    verification_token = db.scalar(
        select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash == token_hash
        )
    )

    if verification_token is None:
        raise ValueError("Invalid or expired verification link")

    if verification_token.expires_at <= datetime.now(timezone.utc):
        db.delete(verification_token)
        db.commit()
        raise ValueError("Invalid or expired verification link")

    user = db.get(User, verification_token.user_id)

    if user is None:
        db.delete(verification_token)
        db.commit()
        raise ValueError("Invalid or expired verification link")

    user.is_verified = True
    db.delete(verification_token)

    try:
        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()
        raise

    return user

def resend_verification_email(
    db: Session,
    email: str,
) -> None:
    normalized_email = email.strip().lower()

    user = db.scalar(
        select(User).where(User.email == normalized_email)
    )

    if user is None:
        raise ValueError("Account not found")

    if user.is_verified:
        raise ValueError("Email is already verified")

    try:
        # Remove the previous token, if it exists.
        existing_token = db.scalar(
            select(EmailVerificationToken).where(
                EmailVerificationToken.user_id == user.id
            )
        )

        if existing_token is not None:
            db.delete(existing_token)
            db.flush()

        # Generate a fresh token.
        raw_token = create_email_verification_token(db, user)

        db.commit()

    except Exception:
        db.rollback()
        raise

    verification_url = (
        f"{settings.frontend_url.rstrip('/')}"
        f"/verify-email?token={quote(raw_token, safe='')}"
    )

    send_verification_email(
        recipient_email=user.email,
        verification_url=verification_url,
    )

def authenticate_user(db: Session, login_data: UserLogin) -> str:
    normalized_email = str(login_data.email).strip().lower()

    user = db.scalar(
        select(User).where(User.email == normalized_email)
    )

    if user is None:
        raise ValueError("Invalid email or password")

    if not verify_password(
        login_data.password,
        user.hashed_password,
    ):
        raise ValueError("Invalid email or password")

    if not user.is_verified:
       raise ValueError("Please verify your email before logging in")
    if not user.is_active:
        raise ValueError("Account is inactive")

    return create_access_token(user.id, user.token_version)

import logging

from sqlalchemy import exc
logger = logging.getLogger(__name__)

import smtplib
from email.message import EmailMessage

from app.core.config import settings


def send_verification_email(
    recipient_email: str,
    verification_url: str,
) -> None:
    if (
        not settings.smtp_email
        or not settings.smtp_app_password
        or not settings.email_from
    ):
        raise RuntimeError("Email service is not configured")

    message = EmailMessage()
    message["Subject"] = "Verify your StudyVault email"
    message["From"] = settings.email_from
    message["To"] = recipient_email

    message.set_content(
        f"""
Welcome to StudyVault!

Please verify your email address to activate your account.

Verification link:
{verification_url}

This verification link will expire in 30 minutes.

If you did not create this account, you can ignore this email.
"""
    )

    message.add_alternative(
        f"""
        <html>
            <body>
                <h2>Welcome to StudyVault!</h2>
                <p>Please verify your email address to activate your account.</p>
                <p>
                    <a href="{verification_url}">
                        Verify Email Address
                    </a>
                </p>
                <p>This verification link will expire in 30 minutes.</p>
                <p>If you did not create this account, you can ignore this email.</p>
            </body>
        </html>
        """,
        subtype="html",
    )

    try:
        with smtplib.SMTP_SSL(
            settings.smtp_host,
            settings.smtp_port,
            timeout=15,
        ) as server:
            server.login(
                settings.smtp_email,
                settings.smtp_app_password.get_secret_value(),
            )
            server.send_message(message)

    except (smtplib.SMTPException, OSError) as exc:
        logger.exception("Failed to send verification email")
        raise RuntimeError(
            "Unable to send verification email. Please try again later."
        ) from exc

def send_password_reset_email(
    recipient_email: str,
    reset_url: str,
) -> None:
    if (
        not settings.smtp_email
        or not settings.smtp_app_password
        or not settings.email_from
    ):
        raise RuntimeError("Email service is not configured")

    message = EmailMessage()
    message["Subject"] = "Reset your StudyVault password"
    message["From"] = settings.email_from
    message["To"] = recipient_email

    message.set_content(
        f"""
We received a request to reset your StudyVault password.

Use the link below to choose a new password:

{reset_url}

This password reset link will expire in 30 minutes.

If you did not request a password reset, you can ignore this email.
Your password will remain unchanged.
"""
    )

    message.add_alternative(
        f"""
        <html>
            <body>
                <h2>Password Reset Request</h2>
                <p>We received a request to reset your StudyVault password.</p>
                <p>
                    <a href="{reset_url}">
                        Reset Password
                    </a>
                </p>
                <p>This password reset link will expire in 30 minutes.</p>
                <p>If you did not request a password reset, you can ignore this email.</p>
            </body>
        </html>
        """,
        subtype="html",
    )

    try:
        with smtplib.SMTP_SSL(
            settings.smtp_host,
            settings.smtp_port,
            timeout=15,
        ) as server:
            server.login(
                settings.smtp_email,
                settings.smtp_app_password.get_secret_value(),
            )
            server.send_message(message)

    except (smtplib.SMTPException, OSError) as exc:
        logger.exception("Failed to send password reset email")
        raise RuntimeError(
            "Unable to send password reset email. Please try again later."
        ) from exc

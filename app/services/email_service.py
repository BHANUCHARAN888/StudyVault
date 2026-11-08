import logging

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)


def _send_email(
    recipient_email: str,
    subject: str,
    text_body: str,
    html_body: str,
) -> None:
    if settings.email_relay_url and settings.email_relay_secret:
        payload = {
            "secret": settings.email_relay_secret.get_secret_value(),
            "to": recipient_email,
            "subject": subject,
            "text": text_body,
            "html": html_body,
        }

        try:
            response = requests.post(
                settings.email_relay_url,
                json=payload,
                timeout=30,
            )
            response.raise_for_status()

            result = response.json()

            if not result.get("success"):
                raise RuntimeError("Email relay rejected the request")

        except (requests.RequestException, ValueError, RuntimeError) as exc:
            logger.exception("Failed to send email through relay")
            raise RuntimeError(
                "Unable to send email. Please try again later."
            ) from exc

        return

    if (
        not settings.smtp_email
        or not settings.smtp_app_password
        or not settings.email_from
    ):
        raise RuntimeError("Email service is not configured")

    import smtplib
    from email.message import EmailMessage

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.email_from
    message["To"] = recipient_email
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

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
        logger.exception("Failed to send email through SMTP")
        raise RuntimeError(
            "Unable to send email. Please try again later."
        ) from exc


def send_verification_email(
    recipient_email: str,
    verification_url: str,
) -> None:
    text_body = f"""
Welcome to StudyVault!

Please verify your email address to activate your account.

Verification link:
{verification_url}

This verification link will expire in 30 minutes.

If you did not create this account, you can ignore this email.
"""

    html_body = f"""
<html>
    <body>
        <h2>Welcome to StudyVault!</h2>
        <p>Please verify your email address to activate your account.</p>
        <p><a href="{verification_url}">Verify Email Address</a></p>
        <p>This verification link will expire in 30 minutes.</p>
        <p>If you did not create this account, you can ignore this email.</p>
    </body>
</html>
"""

    _send_email(
        recipient_email,
        "Verify your StudyVault email",
        text_body,
        html_body,
    )


def send_password_reset_email(
    recipient_email: str,
    reset_url: str,
) -> None:
    text_body = f"""
We received a request to reset your StudyVault password.

Use the link below to choose a new password:

{reset_url}

This password reset link will expire in 30 minutes.

If you did not request a password reset, you can ignore this email.
Your password will remain unchanged.
"""

    html_body = f"""
<html>
    <body>
        <h2>Password Reset Request</h2>
        <p>We received a request to reset your StudyVault password.</p>
        <p><a href="{reset_url}">Reset Password</a></p>
        <p>This password reset link will expire in 30 minutes.</p>
        <p>If you did not request a password reset, you can ignore this email.</p>
    </body>
</html>
"""

    _send_email(
        recipient_email,
        "Reset your StudyVault password",
        text_body,
        html_body,
    )
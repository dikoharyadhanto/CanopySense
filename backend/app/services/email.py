import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from app.database import settings

logger = logging.getLogger(__name__)


async def send_otp_email(to_email: str, otp_code: str, username: str) -> None:
    """Send a 6-digit OTP to the user's registered email address."""
    if not settings.SMTP_HOST or not settings.SMTP_USER:
        logger.warning(
            "SMTP not configured — OTP email not sent (set SMTP_HOST and SMTP_USER)"
        )
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "CanopySense — Verification Code"
    msg["From"] = settings.EMAIL_FROM or settings.SMTP_USER
    msg["To"] = to_email

    body_text = (
        f"Hello {username},\n\n"
        f"Your CanopySense verification code is: {otp_code}\n\n"
        f"This code is valid for 10 minutes. Do not share it with anyone.\n\n"
        f"If you did not attempt to log in, contact your administrator immediately.\n"
    )

    body_html = (
        "<html><body>"
        f"<p>Hello <strong>{username}</strong>,</p>"
        "<p>Your CanopySense verification code is:</p>"
        f"<h2 style='letter-spacing:4px;font-family:monospace'>{otp_code}</h2>"
        "<p>This code is valid for <strong>10 minutes</strong>. "
        "Do not share it with anyone.</p>"
        "<p style='color:#888;font-size:12px'>"
        "If you did not attempt to log in, contact your administrator immediately."
        "</p></body></html>"
    )

    msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))

    await aiosmtplib.send(
        msg,
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SMTP_USER,
        password=settings.SMTP_PASSWORD,
        start_tls=True,
    )
    logger.info("OTP email sent to %s", to_email)


async def send_password_reset_email(to_email: str, username: str, reset_link: str) -> None:
    """Send password reset link to the user's email."""
    if not settings.SMTP_HOST or not settings.SMTP_USER:
        logger.warning("SMTP not configured — password reset email not sent")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "CanopySense — Reset Password"
    msg["From"] = settings.EMAIL_FROM or settings.SMTP_USER
    msg["To"] = to_email

    body_text = (
        f"Hello {username},\n\n"
        f"Click the link below to reset your CanopySense password:\n{reset_link}\n\n"
        f"This link is valid for 1 hour. If you did not request a password reset, ignore this email.\n"
    )
    body_html = (
        "<html><body>"
        f"<p>Hello <strong>{username}</strong>,</p>"
        "<p>Click the button below to reset your CanopySense password:</p>"
        f"<p><a href='{reset_link}' style='background:#19C853;color:#fff;padding:10px 20px;"
        "border-radius:6px;text-decoration:none;font-weight:bold'>Reset Password</a></p>"
        "<p style='color:#888;font-size:12px'>This link is valid for <strong>1 hour</strong>. "
        "If you did not request a password reset, ignore this email.</p>"
        "</body></html>"
    )

    msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))

    await aiosmtplib.send(
        msg,
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SMTP_USER,
        password=settings.SMTP_PASSWORD,
        start_tls=True,
    )
    logger.info("Password reset email sent to %s", to_email)


async def send_viewer_invite_email(to_email: str, company_name: str, invite_link: str) -> None:
    """Send viewer invitation link to the invitee's email."""
    if not settings.SMTP_HOST or not settings.SMTP_USER:
        logger.warning("SMTP not configured — viewer invite email not sent")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Undangan CanopySense — {company_name}"
    msg["From"] = settings.EMAIL_FROM or settings.SMTP_USER
    msg["To"] = to_email

    body_text = (
        f"Anda telah diundang untuk bergabung dengan {company_name} di CanopySense.\n\n"
        f"Klik tautan berikut untuk menerima undangan:\n{invite_link}\n\n"
        f"Tautan ini berlaku selama 48 jam.\n"
    )
    body_html = (
        "<html><body>"
        f"<p>Anda telah diundang untuk bergabung dengan <strong>{company_name}</strong> di CanopySense.</p>"
        f"<p><a href='{invite_link}' style='background:#19C853;color:#fff;padding:10px 20px;"
        "border-radius:6px;text-decoration:none;font-weight:bold'>Terima Undangan</a></p>"
        "<p style='color:#888;font-size:12px'>Tautan ini berlaku selama <strong>48 jam</strong>.</p>"
        "</body></html>"
    )

    msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))

    await aiosmtplib.send(
        msg,
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SMTP_USER,
        password=settings.SMTP_PASSWORD,
        start_tls=True,
    )
    logger.info("Viewer invite email sent to %s", to_email)

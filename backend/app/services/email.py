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

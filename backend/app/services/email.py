import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import aiosmtplib
import jinja2

from app.database import settings

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).parent.parent.parent / "emails" / "templates" / "id"

_jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(_TEMPLATE_DIR)),
    undefined=jinja2.StrictUndefined,
    autoescape=True,
)

_BLOCKED_DOMAIN_PATTERNS = (
    ".local",
    ".test",
    ".invalid",
    ".example",
)
_BLOCKED_EXACT_DOMAINS = {"example.com"}


def _is_blocked_domain(email: str) -> bool:
    if "@" not in email:
        return False
    domain = email.split("@", 1)[1].lower()
    if domain in _BLOCKED_EXACT_DOMAINS:
        return True
    return any(domain.endswith(pat) for pat in _BLOCKED_DOMAIN_PATTERNS)


def _render_template(template_name: str, variables: dict) -> str:
    tmpl = _jinja_env.get_template(template_name)
    return tmpl.render(**variables)


def _build_msg(to_email: str, subject: str, html_body: str) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{settings.MAIL_FROM_NAME} <{settings.EMAIL_FROM or settings.SMTP_USER}>"
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html"))
    return msg


async def _send(msg: MIMEMultipart, to_email: str) -> None:
    """Dispatch a pre-built message. Reads MAIL_MODE at call time."""
    mail_mode = settings.MAIL_MODE.lower()

    if mail_mode == "log_only":
        subject = msg.get("Subject", "")
        logger.info("MAIL_LOG_ONLY to=%s subject=%r body_preview=...skipped...", to_email, subject)
        return

    if settings.MAIL_BLOCK_DUMMY_DOMAINS and _is_blocked_domain(to_email):
        logger.warning(
            "MAIL_BLOCKED dummy domain: to=%s — skipping send (MAIL_BLOCK_DUMMY_DOMAINS=true)",
            to_email,
        )
        return

    if mail_mode == "sandbox":
        await aiosmtplib.send(
            msg,
            hostname=settings.MAIL_SANDBOX_HOST,
            port=settings.MAIL_SANDBOX_PORT,
            start_tls=False,
        )
        logger.info("MAIL_SANDBOX email sent to %s via %s:%s", to_email, settings.MAIL_SANDBOX_HOST, settings.MAIL_SANDBOX_PORT)
        return

    # smtp mode (default)
    if not settings.SMTP_HOST or not settings.SMTP_USER:
        logger.warning("SMTP not configured — email not sent (set SMTP_HOST and SMTP_USER)")
        return
    await aiosmtplib.send(
        msg,
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SMTP_USER,
        password=settings.SMTP_PASSWORD,
        start_tls=True,
    )
    logger.info("MAIL_SMTP email sent to %s", to_email)


async def send_otp_email(to_email: str, otp_code: str, username: str) -> None:
    html = _render_template("otp_verification.html", {
        "contact_name": username,
        "verification_code": otp_code,
        "expires_in_minutes": 10,
    })
    msg = _build_msg(to_email, "CanopySense — Kode Verifikasi", html)
    await _send(msg, to_email)


async def send_password_reset_email(to_email: str, username: str, reset_link: str) -> None:
    html = _render_template("password_reset.html", {
        "contact_name": username,
        "reset_link": reset_link,
        "expires_in_minutes": 60,
    })
    msg = _build_msg(to_email, "CanopySense — Reset Kata Sandi", html)
    await _send(msg, to_email)


async def send_viewer_invite_email(to_email: str, company_name: str, invite_link: str) -> None:
    html = _render_template("viewer_invitation.html", {
        "company_name": company_name,
        "invite_link": invite_link,
        "expires_in_minutes": 2880,
    })
    msg = _build_msg(to_email, "CanopySense — Undangan Viewer", html)
    await _send(msg, to_email)


async def send_registration_confirmation_email(to_email: str, contact_name: str, company_name: str) -> None:
    html = _render_template("registration_received.html", {
        "contact_name": contact_name,
        "company_name": company_name,
    })
    msg = _build_msg(to_email, "CanopySense — Pendaftaran Sedang Ditinjau", html)
    await _send(msg, to_email)


async def send_registration_notify_superadmin_email(
    company_name: str, contact_name: str, contact_email: str, phone: str
) -> None:
    notify_to = settings.SUPERADMIN_NOTIFY_EMAIL or settings.EMAIL_FROM
    if not notify_to:
        logger.warning("No superadmin email configured — notify email not sent")
        return
    html = _render_template("registration_notify_superadmin.html", {
        "contact_name": contact_name,
        "company_name": company_name,
        "contact_email": contact_email,
        "phone": phone or "—",
    })
    msg = _build_msg(notify_to, "CanopySense — Pendaftaran Baru Menunggu Tinjauan", html)
    await _send(msg, notify_to)


async def send_registration_rejection_email(
    to_email: str, contact_name: str, company_name: str, reason: str
) -> None:
    html = _render_template("registration_rejected.html", {
        "contact_name": contact_name,
        "company_name": company_name,
        "reject_reason": reason,
    })
    msg = _build_msg(to_email, "CanopySense — Pendaftaran Tidak Disetujui", html)
    await _send(msg, to_email)


async def send_registration_approval_setup_email(
    to_email: str, contact_name: str, company_name: str, setup_link: str
) -> None:
    html = _render_template("registration_approved.html", {
        "contact_name": contact_name,
        "company_name": company_name,
        "setup_link": setup_link,
        "expires_in_minutes": 60,
    })
    msg = _build_msg(to_email, "CanopySense — Pendaftaran Perusahaan Disetujui", html)
    await _send(msg, to_email)


async def send_estate_change_approved_email(to_email: str, contact_name: str, company_name: str = "") -> None:
    html = _render_template("estate_change_approved.html", {
        "contact_name": contact_name,
        "company_name": company_name,
    })
    msg = _build_msg(to_email, "CanopySense — Perubahan Estate Disetujui", html)
    await _send(msg, to_email)


async def send_estate_change_rejected_email(to_email: str, contact_name: str, company_name: str = "", reason: str = "") -> None:
    html = _render_template("estate_change_rejected.html", {
        "contact_name": contact_name,
        "company_name": company_name,
        "reject_reason": reason,
    })
    msg = _build_msg(to_email, "CanopySense — Perubahan Estate Ditolak", html)
    await _send(msg, to_email)

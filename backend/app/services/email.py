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


async def _send(msg: MIMEMultipart) -> None:
    await aiosmtplib.send(
        msg,
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SMTP_USER,
        password=settings.SMTP_PASSWORD,
        start_tls=True,
    )


def _smtp_configured() -> bool:
    return bool(settings.SMTP_HOST and settings.SMTP_USER)


async def send_registration_confirmation_email(to_email: str, contact_name: str, company_name: str) -> None:
    if not _smtp_configured():
        logger.warning("SMTP not configured — registration confirmation email not sent")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "CanopySense — Pendaftaran Diterima"
    msg["From"] = settings.EMAIL_FROM or settings.SMTP_USER
    msg["To"] = to_email

    body_text = (
        f"Halo {contact_name},\n\n"
        f"Pendaftaran perusahaan {company_name} di CanopySense telah diterima dan sedang ditinjau.\n"
        f"Anda akan menerima email konfirmasi setelah pendaftaran disetujui atau ditolak.\n\n"
        f"Terima kasih.\n"
    )
    body_html = (
        "<html><body>"
        f"<p>Halo <strong>{contact_name}</strong>,</p>"
        f"<p>Pendaftaran perusahaan <strong>{company_name}</strong> di CanopySense telah diterima "
        "dan sedang dalam proses peninjauan oleh administrator.</p>"
        "<p>Anda akan mendapat email konfirmasi setelah pendaftaran disetujui atau ditolak.</p>"
        "<p style='color:#888;font-size:12px'>Jika Anda tidak merasa mendaftar, abaikan email ini.</p>"
        "</body></html>"
    )
    msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))
    await _send(msg)
    logger.info("Registration confirmation email sent to %s", to_email)


async def send_registration_notify_superadmin_email(
    company_name: str, contact_name: str, contact_email: str, phone: str
) -> None:
    notify_to = settings.SUPERADMIN_NOTIFY_EMAIL or settings.EMAIL_FROM
    if not _smtp_configured() or not notify_to:
        logger.warning("SMTP not configured or no superadmin email — notify email not sent")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"CanopySense — Pendaftaran Baru: {company_name}"
    msg["From"] = settings.EMAIL_FROM or settings.SMTP_USER
    msg["To"] = notify_to

    body_text = (
        f"Pendaftaran baru diterima:\n\n"
        f"Perusahaan : {company_name}\n"
        f"Kontak     : {contact_name}\n"
        f"Email      : {contact_email}\n"
        f"Telepon    : {phone or '-'}\n\n"
        f"Login ke admin panel untuk meninjau pendaftaran ini.\n"
    )
    body_html = (
        "<html><body>"
        "<p>Pendaftaran baru diterima di CanopySense:</p>"
        "<table style='border-collapse:collapse'>"
        f"<tr><td style='padding:4px 12px 4px 0'><strong>Perusahaan</strong></td><td>{company_name}</td></tr>"
        f"<tr><td style='padding:4px 12px 4px 0'><strong>Kontak</strong></td><td>{contact_name}</td></tr>"
        f"<tr><td style='padding:4px 12px 4px 0'><strong>Email</strong></td><td>{contact_email}</td></tr>"
        f"<tr><td style='padding:4px 12px 4px 0'><strong>Telepon</strong></td><td>{phone or '-'}</td></tr>"
        "</table>"
        "<p>Login ke admin panel untuk meninjau pendaftaran ini.</p>"
        "</body></html>"
    )
    msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))
    await _send(msg)
    logger.info("Superadmin registration notify sent to %s", notify_to)


async def send_registration_rejection_email(
    to_email: str, contact_name: str, company_name: str, reason: str
) -> None:
    if not _smtp_configured():
        logger.warning("SMTP not configured — registration rejection email not sent")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "CanopySense — Pendaftaran Tidak Disetujui"
    msg["From"] = settings.EMAIL_FROM or settings.SMTP_USER
    msg["To"] = to_email

    body_text = (
        f"Halo {contact_name},\n\n"
        f"Kami menyampaikan bahwa pendaftaran perusahaan {company_name} tidak dapat disetujui.\n\n"
        f"Alasan: {reason}\n\n"
        f"Jika ada pertanyaan, hubungi administrator CanopySense.\n"
    )
    body_html = (
        "<html><body>"
        f"<p>Halo <strong>{contact_name}</strong>,</p>"
        f"<p>Kami menyampaikan bahwa pendaftaran perusahaan <strong>{company_name}</strong> "
        "tidak dapat disetujui.</p>"
        f"<p><strong>Alasan:</strong> {reason}</p>"
        "<p>Jika ada pertanyaan, hubungi administrator CanopySense.</p>"
        "</body></html>"
    )
    msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))
    await _send(msg)
    logger.info("Registration rejection email sent to %s", to_email)


async def send_registration_approval_setup_email(
    to_email: str, contact_name: str, company_name: str, setup_link: str
) -> None:
    if not _smtp_configured():
        logger.warning("SMTP not configured — registration approval setup email not sent")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"CanopySense — Selamat Datang, {company_name}!"
    msg["From"] = settings.EMAIL_FROM or settings.SMTP_USER
    msg["To"] = to_email

    body_text = (
        f"Halo {contact_name},\n\n"
        f"Selamat! Pendaftaran perusahaan {company_name} di CanopySense telah disetujui.\n\n"
        f"Klik tautan berikut untuk mengatur akun manager Anda:\n{setup_link}\n\n"
        f"Tautan ini berlaku selama 1 jam.\n"
    )
    body_html = (
        "<html><body>"
        f"<p>Halo <strong>{contact_name}</strong>,</p>"
        f"<p>Selamat! Pendaftaran perusahaan <strong>{company_name}</strong> di CanopySense "
        "telah disetujui.</p>"
        "<p>Klik tombol di bawah untuk mengatur akun manager Anda:</p>"
        f"<p><a href='{setup_link}' style='background:#19C853;color:#fff;padding:10px 20px;"
        "border-radius:6px;text-decoration:none;font-weight:bold'>Atur Akun Saya</a></p>"
        "<p style='color:#888;font-size:12px'>Tautan ini berlaku selama <strong>1 jam</strong>.</p>"
        "</body></html>"
    )
    msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))
    await _send(msg)
    logger.info("Registration approval setup email sent to %s", to_email)


async def send_estate_change_approved_email(to_email: str, full_name: str) -> None:
    if not _smtp_configured():
        logger.warning("SMTP not configured — estate change approved email not sent")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "CanopySense — Perubahan Data Estate Disetujui"
    msg["From"] = settings.EMAIL_FROM or settings.SMTP_USER
    msg["To"] = to_email

    body_text = (
        f"Halo {full_name},\n\n"
        "Permintaan perubahan data estate Anda telah disetujui oleh administrator.\n"
        "Data estate baru sudah aktif di sistem CanopySense.\n"
    )
    body_html = (
        "<html><body>"
        f"<p>Halo <strong>{full_name}</strong>,</p>"
        "<p>Permintaan perubahan data estate Anda telah <strong>disetujui</strong> oleh administrator.</p>"
        "<p>Data estate baru sudah aktif di sistem CanopySense.</p>"
        "</body></html>"
    )
    msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))
    await _send(msg)
    logger.info("Estate change approved email sent to %s", to_email)


async def send_estate_change_rejected_email(to_email: str, full_name: str, reason: str) -> None:
    if not _smtp_configured():
        logger.warning("SMTP not configured — estate change rejected email not sent")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "CanopySense — Perubahan Data Estate Ditolak"
    msg["From"] = settings.EMAIL_FROM or settings.SMTP_USER
    msg["To"] = to_email

    body_text = (
        f"Halo {full_name},\n\n"
        f"Permintaan perubahan data estate Anda tidak disetujui.\n\nAlasan: {reason}\n\n"
        "Anda dapat mengajukan permintaan baru setelah melakukan perbaikan.\n"
    )
    body_html = (
        "<html><body>"
        f"<p>Halo <strong>{full_name}</strong>,</p>"
        "<p>Permintaan perubahan data estate Anda <strong>tidak disetujui</strong>.</p>"
        f"<p><strong>Alasan:</strong> {reason}</p>"
        "<p>Anda dapat mengajukan permintaan baru setelah melakukan perbaikan.</p>"
        "</body></html>"
    )
    msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))
    await _send(msg)
    logger.info("Estate change rejected email sent to %s", to_email)

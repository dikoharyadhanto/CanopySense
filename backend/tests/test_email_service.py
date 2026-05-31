"""Unit tests for email service — TC-030 through TC-033."""
import pytest
import jinja2
from unittest.mock import AsyncMock, patch, MagicMock

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.email import _render_template, _is_blocked_domain, _jinja_env


class TestStrictUndefined:
    """TC-030: Jinja2 StrictUndefined raises UndefinedError when variable is missing."""

    def test_missing_variable_raises(self):
        with pytest.raises(jinja2.UndefinedError):
            _render_template("otp_verification.html", {
                "contact_name": "Test User",
                # verification_code and expires_in_minutes deliberately omitted
            })

    def test_all_variables_provided_succeeds(self):
        html = _render_template("otp_verification.html", {
            "contact_name": "Test User",
            "verification_code": "123456",
            "expires_in_minutes": 10,
        })
        assert "Test User" in html
        assert "123456" in html


class TestAutoescape:
    """TC-031: Jinja2 autoescape=True escapes HTML in template variables."""

    def test_xss_in_company_name_is_escaped(self):
        html = _render_template("registration_received.html", {
            "contact_name": "<script>alert(1)</script>",
            "company_name": "<script>xss</script>",
        })
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_xss_in_contact_name_is_escaped(self):
        html = _render_template("otp_verification.html", {
            "contact_name": '<img src=x onerror="alert(1)">',
            "verification_code": "000000",
            "expires_in_minutes": 10,
        })
        assert "<img" not in html
        assert "&lt;img" in html


class TestBlockedDomain:
    """TC-032: _is_blocked_domain covers all 5 blocked patterns."""

    @pytest.mark.parametrize("email", [
        "test@x.local",
        "user@x.test",
        "foo@example.com",
        "bar@x.invalid",
        "baz@x.example",
    ])
    def test_blocked_domains_return_true(self, email):
        assert _is_blocked_domain(email) is True

    @pytest.mark.parametrize("email", [
        "user@gmail.com",
        "admin@canopysense.app",
        "test@company.co.id",
    ])
    def test_real_domains_return_false(self, email):
        assert _is_blocked_domain(email) is False

    def test_no_at_sign_returns_false(self):
        assert _is_blocked_domain("notanemail") is False


class TestSmtpModeIsolation:
    """TC-033: MAIL_MODE=smtp dispatches to SMTP_HOST, not MAIL_SANDBOX_HOST."""

    @pytest.mark.asyncio
    async def test_smtp_mode_uses_smtp_host(self):
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Test"
        msg["From"] = "test@canopysense.app"
        msg["To"] = "recipient@company.com"
        msg.attach(MIMEText("<p>test</p>", "html"))

        with patch("app.services.email.settings") as mock_settings, \
             patch("app.services.email.aiosmtplib.send", new_callable=AsyncMock) as mock_send:

            mock_settings.MAIL_MODE = "smtp"
            mock_settings.MAIL_BLOCK_DUMMY_DOMAINS = True
            mock_settings.SMTP_HOST = "smtp.real-server.com"
            mock_settings.SMTP_PORT = 587
            mock_settings.SMTP_USER = "user@canopysense.app"
            mock_settings.SMTP_PASSWORD = "password"
            mock_settings.MAIL_SANDBOX_HOST = "mailpit"
            mock_settings.MAIL_SANDBOX_PORT = 1025

            from app.services.email import _send
            await _send(msg, "recipient@company.com")

            mock_send.assert_called_once()
            call_kwargs = mock_send.call_args[1]
            assert call_kwargs["hostname"] == "smtp.real-server.com"
            assert call_kwargs["hostname"] != "mailpit"

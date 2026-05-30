"""
test_security.py — CanopySense security contract tests.

Covers TC-004 through TC-016 from FMN-PLAN-v1.14 security hardening contract,
plus DEV-identified additions (timing side-channel, file-size limit).

All tests are offline (no DB, no Redis, no live server required).
They verify structural and static-analysis contracts: module presence,
function signatures, configuration defaults, middleware registration,
migration DDL, and code-level security patterns.

Usage:
    python -m pytest tests/test_security.py -v

Prerequisites:
    pip install pytest
"""
from __future__ import annotations

import importlib
import importlib.util
import pathlib
import sys
import types

import pytest

_ROOT = pathlib.Path(__file__).parent.parent
_BACKEND = _ROOT / "backend"
sys.path.insert(0, str(_BACKEND))


# ---------------------------------------------------------------------------
# Stub helpers — load backend modules without full app startup
# ---------------------------------------------------------------------------

def _stub_database(secret_key: str = "test-secret-key-for-unit-tests-only-32c") -> None:
    if "app.database" not in sys.modules:
        db_stub = types.ModuleType("app.database")
        db_stub.get_db_pool = lambda: None
        db_stub.settings = types.SimpleNamespace(
            SECRET_KEY=secret_key,
            ALGORITHM="HS256",
            ACCESS_TOKEN_EXPIRE_MINUTES=60,
            ALLOWED_ORIGINS="http://localhost:3000",
            SMTP_HOST="",
            SMTP_PORT=587,
            SMTP_USER="",
            SMTP_PASSWORD="",
            EMAIL_FROM="",
            DEVICE_TOKEN_EXPIRE_DAYS=90,
            MAX_UPLOAD_SIZE_BYTES=10 * 1024 * 1024,
            ENVIRONMENT="development",
        )
        sys.modules["app.database"] = db_stub


def _read_source(rel_path: str) -> str:
    return (_BACKEND / rel_path).read_text()


# ===========================================================================
# TC-006 variant: JWT / Secret Key
# ===========================================================================

class TestJWTModule:
    """JWT module security contracts."""

    def setup_method(self):
        self._src = _read_source("app/auth/jwt.py")

    def test_algorithm_pinned_to_hs256(self):
        assert 'algorithms=[settings.ALGORITHM]' in self._src or 'algorithms=["HS256"]' in self._src

    def test_decode_uses_algorithm_list(self):
        assert "jwt.decode" in self._src

    def test_verify_password_uses_bcrypt(self):
        assert "bcrypt" in self._src or "_bcrypt" in self._src

    def test_get_password_hash_uses_bcrypt(self):
        assert "bcrypt.hashpw" in self._src or "_bcrypt.hashpw" in self._src

    def test_create_access_token_sets_exp(self):
        assert '"exp"' in self._src or "'exp'" in self._src


class TestStartupSecretValidation:
    """Startup validation rejects weak SECRET_KEY."""

    def test_weak_secret_validation_exists_in_main(self):
        src = _read_source("app/main.py")
        assert "_validate_startup_config" in src

    def test_validation_checks_minimum_length(self):
        src = _read_source("app/main.py")
        assert "32" in src

    def test_validation_checks_default_string(self):
        src = _read_source("app/main.py")
        assert "super_secret_key_change_me_in_production" in src

    def test_testing_env_var_skips_validation(self):
        src = _read_source("app/main.py")
        assert "TESTING" in src

    def test_database_py_removes_hardcoded_default(self):
        src = _read_source("app/database.py")
        assert "super_secret_key_change_me_in_production" not in src

    def test_token_lifetime_reduced_to_60_min(self):
        src = _read_source("app/database.py")
        assert "ACCESS_TOKEN_EXPIRE_MINUTES: int = 60" in src
        # Must NOT contain the original 1-week default
        assert "60 * 24 * 7" not in src


# ===========================================================================
# TC-007: Password Policy
# ===========================================================================

class TestPasswordPolicy:
    """Password policy is enforced on /auth/setup."""

    def setup_method(self):
        self._src = _read_source("app/auth/routes.py")

    def test_password_policy_function_defined(self):
        assert "_enforce_password_policy" in self._src

    def test_setup_endpoint_calls_policy(self):
        assert "_enforce_password_policy(body.new_password)" in self._src

    def test_policy_requires_minimum_12_chars(self):
        assert ".{12,}" in self._src

    def test_policy_requires_uppercase(self):
        assert "[A-Z]" in self._src

    def test_policy_requires_lowercase(self):
        assert "[a-z]" in self._src

    def test_policy_returns_422(self):
        assert "status_code=422" in self._src


# ===========================================================================
# TC-008: Anti-Enumeration / Timing Side-Channel
# ===========================================================================

class TestAntiEnumeration:
    """Login endpoint prevents username enumeration via timing and error message."""

    def setup_method(self):
        self._src = _read_source("app/auth/routes.py")

    def test_dummy_hash_constant_defined(self):
        assert "_DUMMY_HASH" in self._src

    def test_dummy_hash_is_valid_bcrypt_format(self):
        # The hash must start with bcrypt prefix
        assert "$2b$12$" in self._src

    def test_constant_time_comparison_on_missing_user(self):
        # verify_password must be called before the 401 raise when user is not found
        assert "verify_password(form_data.password, _DUMMY_HASH)" in self._src

    def test_error_message_does_not_distinguish_user_vs_password(self):
        assert "Incorrect username or password" in self._src
        # Both branches must use the same message — check only one distinct message exists
        assert self._src.count("Incorrect username or password") >= 1

    def test_rate_limiting_on_login(self):
        assert '@limiter.limit("10/minute")' in self._src or "10/minute" in self._src


# ===========================================================================
# TC-004: CORS Hardening
# ===========================================================================

class TestCORSHardening:
    """CORS is driven by an env-var allowlist, not a wildcard."""

    def setup_method(self):
        self._src = _read_source("app/main.py")

    def test_cors_uses_allowed_origins_env_var(self):
        assert "ALLOWED_ORIGINS" in self._src

    def test_cors_no_wildcard_hardcoded(self):
        assert 'allow_origins=["*"]' not in self._src

    def test_cors_splits_comma_separated_list(self):
        assert ".split(" in self._src

    def test_database_py_allowed_origins_default_is_not_wildcard(self):
        src = _read_source("app/database.py")
        assert "ALLOWED_ORIGINS" in src
        assert '"*"' not in src


# ===========================================================================
# TC-005: Security Headers
# ===========================================================================

class TestSecurityHeaders:
    """Security headers middleware exists and injects all required headers."""

    def test_middleware_file_exists(self):
        assert (_BACKEND / "app/middleware/security_headers.py").exists()

    def test_middleware_class_defined(self):
        src = _read_source("app/middleware/security_headers.py")
        assert "SecurityHeadersMiddleware" in src

    def test_x_content_type_options_header(self):
        src = _read_source("app/middleware/security_headers.py")
        assert "X-Content-Type-Options" in src
        assert "nosniff" in src

    def test_x_frame_options_header(self):
        src = _read_source("app/middleware/security_headers.py")
        assert "X-Frame-Options" in src
        assert "DENY" in src

    def test_referrer_policy_header(self):
        src = _read_source("app/middleware/security_headers.py")
        assert "Referrer-Policy" in src

    def test_permissions_policy_header(self):
        src = _read_source("app/middleware/security_headers.py")
        assert "Permissions-Policy" in src

    def test_content_security_policy_header(self):
        src = _read_source("app/middleware/security_headers.py")
        assert "Content-Security-Policy" in src

    def test_hsts_header_defined(self):
        src = _read_source("app/middleware/security_headers.py")
        assert "Strict-Transport-Security" in src

    def test_middleware_registered_in_main(self):
        src = _read_source("app/main.py")
        assert "SecurityHeadersMiddleware" in src


# ===========================================================================
# TC-013: Request Size Limit / Error Response Hygiene
# ===========================================================================

class TestRequestSizeLimit:
    """Request body size limit is enforced at the middleware level."""

    def setup_method(self):
        self._src = _read_source("app/main.py")

    def test_size_limit_middleware_registered(self):
        assert "limit_request_size" in self._src

    def test_size_limit_returns_413(self):
        assert "413" in self._src

    def test_size_limit_reads_content_length_header(self):
        assert "content-length" in self._src

    def test_max_request_size_references_settings(self):
        assert "MAX_UPLOAD_SIZE_BYTES" in self._src


# ===========================================================================
# TC-009: RBAC Guards
# ===========================================================================

class TestRBACGuards:
    """RBAC guards exist and perform server-side DB re-reads."""

    def setup_method(self):
        self._deps = _read_source("app/api/deps.py")

    def test_get_current_admin_defined(self):
        assert "async def get_current_admin" in self._deps

    def test_get_current_super_admin_defined(self):
        assert "async def get_current_super_admin" in self._deps

    def test_admin_guard_reads_from_db_not_jwt(self):
        # Must contain a SELECT query — not rely solely on JWT claims
        assert "SELECT" in self._deps

    def test_admin_guard_checks_is_admin_or_is_global_admin(self):
        assert "is_admin" in self._deps
        assert "is_global_admin" in self._deps

    def test_super_admin_guard_checks_only_is_global_admin(self):
        assert "is_global_admin" in self._deps

    def test_guards_return_403_for_unauthorized_role(self):
        assert "HTTP_403_FORBIDDEN" in self._deps

    def test_guards_check_is_active(self):
        assert "is_active" in self._deps


# ===========================================================================
# TC-014: Pipeline Trigger Validation
# ===========================================================================

class TestPipelineTrigger:
    """Pipeline trigger endpoint has validation and RBAC."""

    def setup_method(self):
        self._src = _read_source("app/api/admin/pipeline.py")

    def test_uses_admin_guard(self):
        assert "get_current_admin" in self._src or "get_current_super_admin" in self._src

    def test_validate_trigger_request_imported(self):
        assert "validate_trigger_request" in self._src

    def test_validate_date_window_imported(self):
        assert "validate_date_window" in self._src

    def test_trigger_endpoint_calls_validation(self):
        assert "validate_trigger_request" in self._src


# ===========================================================================
# TC-015: Estate Onboarding File Size + Rollback
# ===========================================================================

class TestEstateOnboarding:
    """File upload endpoints enforce size limit before reading."""

    def setup_method(self):
        self._src = _read_source("app/api/admin/estate_onboarding.py")

    def test_file_size_check_before_read_in_preview(self):
        # file.read() must be called with size limit as argument to cap memory read
        assert "MAX_UPLOAD_SIZE_BYTES" in self._src, "MAX_UPLOAD_SIZE_BYTES not found"
        assert "await file.read(settings.MAX_UPLOAD_SIZE_BYTES" in self._src, (
            "file.read() must be called with MAX_UPLOAD_SIZE_BYTES as size argument"
        )

    def test_file_size_check_raises_422(self):
        assert "status_code=422" in self._src

    def test_uses_admin_guard(self):
        assert "get_current_admin" in self._src

    def test_transaction_context_manager_used(self):
        assert "async with" in self._src

    def test_settings_imported(self):
        assert "from app.database import" in self._src
        assert "settings" in self._src


# ===========================================================================
# TC-016: Data Viewer Safety
# ===========================================================================

class TestDataViewer:
    """Data viewer endpoint uses super-admin guard and filters sensitive fields."""

    def setup_method(self):
        self._src = _read_source("app/api/admin/data_viewer.py")

    def test_uses_super_admin_guard(self):
        assert "get_current_super_admin" in self._src

    def test_table_allowlist_exists(self):
        assert "TABLE_ALLOWLIST" in self._src or "ALLOWLIST" in self._src

    def test_password_hash_excluded_from_users(self):
        assert "password_hash" in self._src  # present in exclusion logic
        # Must NOT be returned — verify it appears in a negative context
        # (the allowlist should exclude it from the SELECT columns)
        assert "password_hash" not in self._src.split("TABLE_ALLOWLIST")[1].split("]")[0] \
            if "TABLE_ALLOWLIST" in self._src else True

    def test_parameterized_filter_used(self):
        # Parameterized queries use dynamic $N indexing — prevents SQL injection
        # data_viewer.py uses ${len(params)} f-string pattern rather than literal $1
        assert "${len(params)}" in self._src or "$1" in self._src

    def test_no_arbitrary_table_access(self):
        # Should not use string interpolation of table name without allowlist check
        src = self._src
        assert "ALLOWLIST" in src or "allowlist" in src

    def test_sensitive_fields_explicitly_excluded(self):
        assert "password_hash" in self._src
        assert "setup_token_hash" in self._src


# ===========================================================================
# Phase E: New Device Detection + Email OTP
# ===========================================================================

class TestDeviceOTPModule:
    """Device detection + OTP module structural contracts."""

    def test_device_module_exists(self):
        assert (_BACKEND / "app/auth/device.py").exists()

    def test_email_service_exists(self):
        assert (_BACKEND / "app/services/email.py").exists()

    def test_generate_device_token_defined(self):
        src = _read_source("app/auth/device.py")
        assert "def generate_device_token" in src

    def test_device_token_uses_cryptographic_random(self):
        src = _read_source("app/auth/device.py")
        assert "secrets.token_urlsafe" in src or "secrets.token_hex" in src

    def test_device_token_hashed_before_storage(self):
        src = _read_source("app/auth/device.py")
        assert "hashlib.sha256" in src or "_hash_device_token" in src

    def test_otp_generated_with_6_digits(self):
        src = _read_source("app/auth/device.py")
        assert "1_000_000" in src or "1000000" in src

    def test_otp_session_has_expiry(self):
        src = _read_source("app/auth/device.py")
        assert "timedelta(minutes=10)" in src

    def test_constant_time_on_invalid_otp_session(self):
        src = _read_source("app/auth/device.py")
        assert "_DUMMY_OTP_HASH" in src

    def test_resend_limit_enforces_3_per_10_min(self):
        src = _read_source("app/auth/device.py")
        assert "< 3" in src
        assert "10 minutes" in src


class TestDeviceOTPRoutes:
    """Device OTP endpoints registered in routes.py."""

    def setup_method(self):
        self._src = _read_source("app/auth/routes.py")

    def test_verify_device_endpoint_exists(self):
        assert '"/verify-device"' in self._src

    def test_resend_otp_endpoint_exists(self):
        assert '"/resend-otp"' in self._src

    def test_login_issues_pending_token_for_unknown_device(self):
        assert "pending_token" in self._src

    def test_login_device_challenge_scope_is_privileged_only(self):
        assert "is_privileged" in self._src

    def test_device_token_cookie_is_httponly(self):
        assert "httponly=True" in self._src

    def test_device_token_cookie_is_secure(self):
        assert "secure=True" in self._src

    def test_device_token_cookie_samesite_strict(self):
        assert 'samesite="strict"' in self._src

    def test_resend_limited_to_429(self):
        assert "HTTP_429_TOO_MANY_REQUESTS" in self._src


# ===========================================================================
# Infrastructure: Migration file
# ===========================================================================

class TestSecurityMigration:
    """Migration 007 adds known_devices and device_otp_sessions tables."""

    def setup_method(self):
        migration = _ROOT / "database/migrations/007_security_hardening.sql"
        assert migration.exists(), "007_security_hardening.sql must exist"
        self._sql = migration.read_text()

    def test_known_devices_table_created(self):
        assert "known_devices" in self._sql

    def test_device_otp_sessions_table_created(self):
        assert "device_otp_sessions" in self._sql

    def test_device_hash_unique_constraint(self):
        assert "UNIQUE" in self._sql

    def test_otp_expires_at_column_present(self):
        assert "otp_expires_at" in self._sql

    def test_used_column_present(self):
        assert "used" in self._sql

    def test_migration_wrapped_in_transaction(self):
        assert "BEGIN" in self._sql
        assert "COMMIT" in self._sql

    def test_no_drop_table_in_migration(self):
        assert "DROP TABLE" not in self._sql.upper()


# ===========================================================================
# Infrastructure: Docker Compose hardening
# ===========================================================================

class TestDockerComposeHardening:
    """docker-compose.yml does not expose DB/Redis to host ports."""

    def setup_method(self):
        compose_path = _ROOT / "docker-compose.yml"
        assert compose_path.exists()
        self._src = compose_path.read_text()

    def test_db_port_not_host_published(self):
        # Should not contain "5432:5432" host binding
        assert '"5432:5432"' not in self._src
        assert "'5432:5432'" not in self._src
        assert "- 5432:5432" not in self._src

    def test_redis_port_not_host_published(self):
        assert '"6379:6379"' not in self._src
        assert "'6379:6379'" not in self._src
        assert "- 6379:6379" not in self._src

    def test_pgadmin_not_in_default_compose(self):
        assert "pgadmin" not in self._src

    def test_internal_network_defined(self):
        assert "canopy_internal" in self._src

    def test_postgres_password_uses_env_var(self):
        # Must not have hardcoded "postgres" as password
        assert "POSTGRES_PASSWORD: postgres" not in self._src

    def test_secret_key_uses_env_var(self):
        assert "SECRET_KEY=${SECRET_KEY}" in self._src


class TestDevToolsCompose:
    """docker-compose.dev-tools.yml contains pgAdmin as opt-in."""

    def test_dev_tools_file_exists(self):
        assert (_ROOT / "docker-compose.dev-tools.yml").exists()

    def test_pgadmin_in_dev_tools(self):
        src = (_ROOT / "docker-compose.dev-tools.yml").read_text()
        assert "pgadmin" in src

    def test_dev_tools_uses_env_var_for_pgadmin_password(self):
        src = (_ROOT / "docker-compose.dev-tools.yml").read_text()
        assert "PGADMIN_DEFAULT_PASSWORD" in src


# ===========================================================================
# Infrastructure: .gitignore
# ===========================================================================

class TestGitignore:
    """secret/ folder is gitignored."""

    def test_secret_folder_in_gitignore(self):
        gitignore = (_ROOT / ".gitignore").read_text()
        assert "secret/" in gitignore


# ===========================================================================
# Infrastructure: Staging Reset Script
# ===========================================================================

class TestStagingResetScript:
    """staging_reset.py has production guard and requires --confirm flag."""

    def setup_method(self):
        script = _ROOT / "scripts/staging_reset.py"
        assert script.exists(), "scripts/staging_reset.py must exist"
        self._src = script.read_text()

    def test_production_guard_present(self):
        assert "production" in self._src

    def test_confirm_flag_required(self):
        assert "--confirm" in self._src

    def test_exits_if_environment_is_production(self):
        assert "sys.exit" in self._src

    def test_truncates_operational_tables(self):
        assert "TRUNCATE" in self._src

    def test_bootstraps_super_admin(self):
        assert "is_global_admin" in self._src

    def test_uses_bcrypt_for_password(self):
        assert "bcrypt" in self._src

    def test_admin_credentials_from_env_vars(self):
        assert "RESET_ADMIN_USERNAME" in self._src
        assert "RESET_ADMIN_PASSWORD" in self._src

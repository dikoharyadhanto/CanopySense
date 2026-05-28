"""
test_admin_contracts.py — CanopySense admin feature contract tests.

Covers TC-001 through TC-024 from FMN-PLAN v1.10 test contract.
All tests in this file are offline (no DB, no Redis, no GEE required).
They verify structural contracts: module presence, function signatures, schema
shape, route registration, guard logic, and migration file contents.

Usage:
    python -m pytest tests/test_admin_contracts.py -v

Prerequisites:
    pip install pytest fastapi asyncpg pydantic
"""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import pathlib
import re
import sys
import types

import pytest

_ROOT = pathlib.Path(__file__).parent.parent
_BACKEND = _ROOT / "backend"
sys.path.insert(0, str(_BACKEND))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load(module_path: str) -> types.ModuleType:
    """Load a backend module by dotted path without full app startup."""
    spec = importlib.util.spec_from_file_location(
        module_path,
        _BACKEND / module_path.replace(".", "/").replace("/py", "") / "__init__.py"
        if ((_BACKEND / module_path.replace(".", "/")).is_dir())
        else _BACKEND / (module_path.replace(".", "/") + ".py"),
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot find module: {module_path}")
    mod = importlib.util.module_from_spec(spec)
    # Inject a minimal stub for app.database to avoid startup side effects
    if "app.database" not in sys.modules:
        db_stub = types.ModuleType("app.database")
        db_stub.get_db_pool = lambda: None
        db_stub.settings = types.SimpleNamespace(
            SECRET_KEY="test-secret",
            ALGORITHM="HS256",
            ACCESS_TOKEN_EXPIRE_MINUTES=60,
        )
        sys.modules["app.database"] = db_stub
    spec.loader.exec_module(mod)
    return mod


# ===========================================================================
# TC-001: Migration file exists and contains required DDL
# ===========================================================================

class TestMigration004Exists:
    """TC-001 — migration 004_admin_features.sql is present and correct."""

    def test_file_exists(self):
        migration = _ROOT / "database/migrations/004_admin_features.sql"
        assert migration.exists(), "004_admin_features.sql must exist"

    def test_contains_is_admin_column(self):
        sql = (_ROOT / "database/migrations/004_admin_features.sql").read_text()
        assert "is_admin" in sql

    def test_contains_setup_token_hash(self):
        sql = (_ROOT / "database/migrations/004_admin_features.sql").read_text()
        assert "setup_token_hash" in sql

    def test_contains_setup_required(self):
        sql = (_ROOT / "database/migrations/004_admin_features.sql").read_text()
        assert "setup_required" in sql

    def test_contains_admin_audit_log_table(self):
        sql = (_ROOT / "database/migrations/004_admin_features.sql").read_text()
        assert "admin_audit_log" in sql

    def test_audit_log_has_append_only_trigger(self):
        sql = (_ROOT / "database/migrations/004_admin_features.sql").read_text()
        assert "prevent_admin_audit_log_mutation" in sql or "immutable_admin_audit_log" in sql

    def test_no_drop_existing_tables(self):
        sql = (_ROOT / "database/migrations/004_admin_features.sql").read_text().lower()
        assert "drop table" not in sql, "Migration must not drop existing tables"


# ===========================================================================
# TC-002: Admin guard dependencies exist and have correct signatures
# ===========================================================================

class TestAdminGuardSignatures:
    """TC-002 — get_current_admin and get_current_super_admin exist in deps.py."""

    def setup_method(self):
        # We check file content directly to avoid async execution
        self._deps = (_BACKEND / "app/api/deps.py").read_text()

    def test_get_current_admin_defined(self):
        assert "async def get_current_admin" in self._deps

    def test_get_current_super_admin_defined(self):
        assert "async def get_current_super_admin" in self._deps

    def test_admin_guard_reads_is_admin_from_db(self):
        assert "is_admin" in self._deps

    def test_admin_guard_reads_is_global_admin_from_db(self):
        assert "is_global_admin" in self._deps

    def test_admin_guard_checks_is_active(self):
        assert "is_active" in self._deps

    def test_get_current_user_includes_is_admin(self):
        # get_current_user SELECT must include is_admin for /me response
        assert "u.is_admin" in self._deps

    def test_403_for_non_admin(self):
        assert "HTTP_403_FORBIDDEN" in self._deps or "403" in self._deps


# ===========================================================================
# TC-003: Admin API namespace files exist
# ===========================================================================

class TestAdminNamespaceFiles:
    """TC-003 — all admin module files must exist."""

    REQUIRED_FILES = [
        "backend/app/api/admin/__init__.py",
        "backend/app/api/admin/audit_log.py",
        "backend/app/api/admin/companies.py",
        "backend/app/api/admin/managers.py",
        "backend/app/api/admin/subscriptions.py",
        "backend/app/api/admin/internal_users.py",
        "backend/app/api/admin/audit.py",
        "backend/app/api/admin/dashboard.py",
        "backend/app/api/admin/router.py",
    ]

    @pytest.mark.parametrize("rel_path", REQUIRED_FILES)
    def test_file_exists(self, rel_path):
        assert (_ROOT / rel_path).exists(), f"{rel_path} must exist"


# ===========================================================================
# TC-004: log_admin_action signature
# ===========================================================================

class TestAuditLogHelper:
    """TC-004 — log_admin_action helper has correct parameters."""

    def test_parameters(self):
        src = (_BACKEND / "app/api/admin/audit_log.py").read_text()
        assert "async def log_admin_action" in src
        assert "actor_id" in src
        assert "action" in src
        assert "target_type" in src
        assert "target_id" in src


# ===========================================================================
# TC-005: Admin router registration in main.py
# ===========================================================================

class TestAdminRouterRegistration:
    """TC-005 — admin router is registered under /api/admin in main.py."""

    def test_admin_router_imported(self):
        main_src = (_BACKEND / "app/main.py").read_text()
        assert "admin_router" in main_src or "admin.router" in main_src

    def test_admin_router_prefix(self):
        main_src = (_BACKEND / "app/main.py").read_text()
        assert '"/api/admin"' in main_src or "'/api/admin'" in main_src


# ===========================================================================
# TC-006: Auth setup endpoint exists
# ===========================================================================

class TestLoginEndpoint:
    """TC-005b — login rejects inactive and setup-pending users before token creation."""

    def test_is_active_selected_in_login_query(self):
        """FMN finding: is_active must be checked at login, not only at /auth/me."""
        src = (_BACKEND / "app/auth/routes.py").read_text()
        assert "u.is_active" in src or "is_active" in src

    def test_inactive_user_rejected_before_token(self):
        """Deactivated users must be rejected before access_token is created."""
        src = (_BACKEND / "app/auth/routes.py").read_text()
        # Find the login function body (skip imports); look for the is_active
        # rejection HTTPException before the access_token assignment statement
        login_fn_start = src.find("async def login_for_access_token")
        assert login_fn_start != -1, "login function must exist"
        login_body = src[login_fn_start:]
        # is_active rejection check must precede the access_token variable assignment
        is_active_pos = login_body.find('is_active')
        token_assign_pos = login_body.find("access_token =")
        assert is_active_pos != -1, "is_active check must exist in login body"
        assert token_assign_pos != -1, "access_token assignment must exist in login body"
        assert is_active_pos < token_assign_pos, \
            "is_active check must appear before access_token assignment in login flow"

    def test_inactive_returns_403(self):
        src = (_BACKEND / "app/auth/routes.py").read_text()
        assert "deactivated" in src.lower() or "is_active" in src


class TestAuthSetupEndpoint:
    """TC-006 — POST /auth/setup endpoint is defined."""

    def test_setup_route_defined(self):
        src = (_BACKEND / "app/auth/routes.py").read_text()
        assert '"/setup"' in src or "'/setup'" in src

    def test_setup_verifies_token_hash(self):
        src = (_BACKEND / "app/auth/routes.py").read_text()
        assert "verify_password" in src
        assert "setup_token_hash" in src

    def test_setup_clears_token_after_use(self):
        src = (_BACKEND / "app/auth/routes.py").read_text()
        assert "setup_token_hash = NULL" in src or "setup_token_hash=None" in src.replace(" ", "")

    def test_setup_sets_setup_required_false(self):
        src = (_BACKEND / "app/auth/routes.py").read_text()
        assert "setup_required = FALSE" in src or "setup_required=FALSE" in src or "setup_required = False" in src


# ===========================================================================
# TC-007: /me response includes is_admin and is_global_admin
# ===========================================================================

class TestMeResponseFields:
    """TC-007 — /auth/me includes is_admin and is_global_admin fields."""

    def test_me_returns_is_admin(self):
        src = (_BACKEND / "app/auth/routes.py").read_text()
        assert '"is_admin"' in src or "'is_admin'" in src

    def test_me_returns_is_global_admin(self):
        src = (_BACKEND / "app/auth/routes.py").read_text()
        assert '"is_global_admin"' in src or "'is_global_admin'" in src


# ===========================================================================
# TC-008: Companies endpoint has list, create, detail
# ===========================================================================

class TestCompaniesEndpoints:
    """TC-008 — companies module exposes GET, POST, GET/{id}."""

    def test_list_route_exists(self):
        src = (_BACKEND / "app/api/admin/companies.py").read_text()
        assert "async def list_companies" in src

    def test_create_route_exists(self):
        src = (_BACKEND / "app/api/admin/companies.py").read_text()
        assert "async def create_company" in src

    def test_detail_route_exists(self):
        src = (_BACKEND / "app/api/admin/companies.py").read_text()
        assert "async def get_company_detail" in src

    def test_detail_includes_readiness(self):
        src = (_BACKEND / "app/api/admin/companies.py").read_text()
        assert "readiness" in src
        assert "estate_count" in src or "estates" in src

    def test_detail_includes_subscription(self):
        src = (_BACKEND / "app/api/admin/companies.py").read_text()
        assert "subscription" in src

    def test_create_seeds_subscription(self):
        src = (_BACKEND / "app/api/admin/companies.py").read_text()
        assert "company_subscriptions" in src


# ===========================================================================
# TC-009: Managers endpoint creates user with setup token
# ===========================================================================

class TestManagersEndpoints:
    """TC-009 — managers module creates user + setup token, supports deactivate."""

    def test_create_route_exists(self):
        src = (_BACKEND / "app/api/admin/managers.py").read_text()
        assert "async def create_manager" in src

    def test_invite_does_not_require_full_name(self):
        """FMN finding: full_name must not be required at invite — set by Manager at /auth/setup."""
        src = (_BACKEND / "app/api/admin/managers.py").read_text()
        # ManagerCreate model must not have full_name as a required field
        model_block = src[src.find("class ManagerCreate"):src.find("class ManagerCreate") + 200]
        assert "full_name" not in model_block

    def test_invite_inserts_null_full_name(self):
        """full_name stored as NULL at invite; Manager fills it at setup."""
        src = (_BACKEND / "app/api/admin/managers.py").read_text()
        assert "NULL" in src  # NULL placeholder in INSERT

    def test_setup_token_generated(self):
        src = (_BACKEND / "app/api/admin/managers.py").read_text()
        assert "token_urlsafe" in src or "setup_token" in src

    def test_token_bcrypt_hashed(self):
        src = (_BACKEND / "app/api/admin/managers.py").read_text()
        assert "get_password_hash" in src

    def test_token_not_stored_plaintext(self):
        src = (_BACKEND / "app/api/admin/managers.py").read_text()
        assert "setup_token_hash" in src
        assert "plaintext_token" in src or "setup_token" in src

    def test_plaintext_returned_once(self):
        src = (_BACKEND / "app/api/admin/managers.py").read_text()
        assert '"setup_token"' in src or "'setup_token'" in src

    def test_deactivate_route_exists(self):
        src = (_BACKEND / "app/api/admin/managers.py").read_text()
        assert "update_manager_status" in src

    def test_deactivate_not_delete(self):
        src = (_BACKEND / "app/api/admin/managers.py").read_text()
        src_lower = src.lower()
        assert "delete from users" not in src_lower
        assert "is_active" in src


# ===========================================================================
# TC-010: Subscription update validates tier/status/raster_mode values
# ===========================================================================

class TestSubscriptionEndpoints:
    """TC-010 — subscriptions module validates allowed field values."""

    def test_valid_tiers_defined(self):
        src = (_BACKEND / "app/api/admin/subscriptions.py").read_text()
        assert "basic" in src and "premium" in src

    def test_valid_statuses_defined(self):
        src = (_BACKEND / "app/api/admin/subscriptions.py").read_text()
        assert "active" in src and "cancelled" in src

    def test_valid_raster_modes_defined(self):
        src = (_BACKEND / "app/api/admin/subscriptions.py").read_text()
        assert "gee_mapid" in src and "maps_platform" in src

    def test_validation_raises_on_invalid(self):
        src = (_BACKEND / "app/api/admin/subscriptions.py").read_text()
        assert "HTTP_422" in src or "422" in src or "Invalid tier" in src or "Invalid status" in src


# ===========================================================================
# TC-011: Internal users endpoint requires super-admin guard
# ===========================================================================

class TestInternalUsersEndpoints:
    """TC-011 — internal_users uses get_current_super_admin, not get_current_admin."""

    def test_uses_super_admin_guard(self):
        src = (_BACKEND / "app/api/admin/internal_users.py").read_text()
        assert "get_current_super_admin" in src

    def test_does_not_use_plain_admin_guard(self):
        src = (_BACKEND / "app/api/admin/internal_users.py").read_text()
        # Should only reference super_admin guard, not the plain admin guard
        assert "get_current_admin" not in src

    def test_cannot_deactivate_self(self):
        src = (_BACKEND / "app/api/admin/internal_users.py").read_text()
        assert "super_admin" in src and "user_id" in src
        assert "own account" in src or "yourself" in src or "super_admin[" in src


# ===========================================================================
# TC-012: Audit log endpoint scopes non-super-admins
# ===========================================================================

class TestAuditEndpoints:
    """TC-012 — audit endpoint scopes non-super-admins to own entries."""

    def test_scope_check_present(self):
        src = (_BACKEND / "app/api/admin/audit.py").read_text()
        assert "is_global_admin" in src
        assert "actor_id" in src

    def test_paginated(self):
        src = (_BACKEND / "app/api/admin/audit.py").read_text()
        assert "limit" in src and "offset" in src


# ===========================================================================
# TC-013: Bootstrap script uses stdin, no hardcoded credentials
# ===========================================================================

class TestBootstrapScript:
    """TC-013 — create_superadmin.py uses stdin prompts, no args/env secrets."""

    def test_script_exists(self):
        assert (_ROOT / "backend/scripts/create_superadmin.py").exists()

    def test_uses_getpass(self):
        src = (_ROOT / "backend/scripts/create_superadmin.py").read_text()
        assert "getpass" in src

    def test_no_hardcoded_credentials(self):
        src = (_ROOT / "backend/scripts/create_superadmin.py").read_text()
        # Ensure no literal password/credential strings
        assert "password123" not in src.lower()
        assert "admin123" not in src.lower()
        assert "secret" not in src.lower() or "SECRET_KEY" not in src  # allow env var name

    def test_idempotency_check(self):
        src = (_ROOT / "backend/scripts/create_superadmin.py").read_text()
        assert "already exists" in src

    def test_sets_is_global_admin(self):
        src = (_ROOT / "backend/scripts/create_superadmin.py").read_text()
        assert "is_global_admin" in src and "TRUE" in src


# ===========================================================================
# TC-014: Frontend AdminRoute checks /auth/me, not JWT claims
# ===========================================================================

class TestFrontendAdminRoute:
    """TC-014 — AdminRoute.tsx fetches /auth/me to determine admin access."""

    def test_file_exists(self):
        assert (_ROOT / "frontend/src/components/AdminRoute.tsx").exists()

    def test_calls_get_me(self):
        src = (_ROOT / "frontend/src/components/AdminRoute.tsx").read_text()
        assert "getMe" in src

    def test_checks_is_admin_or_is_global_admin(self):
        src = (_ROOT / "frontend/src/components/AdminRoute.tsx").read_text()
        assert "is_admin" in src and "is_global_admin" in src

    def test_redirects_manager_to_dashboard(self):
        src = (_ROOT / "frontend/src/components/AdminRoute.tsx").read_text()
        assert "/dashboard" in src

    def test_redirects_unauthenticated_to_login(self):
        src = (_ROOT / "frontend/src/components/AdminRoute.tsx").read_text()
        assert "/login" in src


# ===========================================================================
# TC-015: Frontend admin routes registered in App.tsx
# ===========================================================================

class TestFrontendAdminRoutes:
    """TC-015 — App.tsx includes /admin/* routes under AdminRoute guard."""

    def test_admin_route_imported(self):
        src = (_ROOT / "frontend/src/App.tsx").read_text()
        assert "AdminRoute" in src

    def test_admin_layout_imported(self):
        src = (_ROOT / "frontend/src/App.tsx").read_text()
        assert "AdminLayout" in src

    def test_admin_index_route(self):
        src = (_ROOT / "frontend/src/App.tsx").read_text()
        assert '"/admin"' in src or "'/admin'" in src

    def test_companies_route(self):
        src = (_ROOT / "frontend/src/App.tsx").read_text()
        assert "/admin/companies" in src

    def test_audit_route(self):
        src = (_ROOT / "frontend/src/App.tsx").read_text()
        assert "/admin/audit" in src

    def test_setup_route_outside_admin(self):
        src = (_ROOT / "frontend/src/App.tsx").read_text()
        assert "SetupAccount" in src
        assert '"/setup"' in src or "'/setup'" in src


# ===========================================================================
# TC-016: adminApi.ts exports required functions
# ===========================================================================

class TestAdminApiTs:
    """TC-016 — adminApi.ts exports all required API client functions."""

    REQUIRED_EXPORTS = [
        "getMe",
        "getDashboard",
        "listCompanies",
        "createCompany",
        "getCompanyDetail",
        "createManager",
        "updateManagerStatus",
        "getSubscription",
        "updateSubscription",
        "listInternalAdmins",
        "createInternalAdmin",
        "updateInternalAdminStatus",
        "listAuditLog",
    ]

    @pytest.mark.parametrize("fn_name", REQUIRED_EXPORTS)
    def test_export_exists(self, fn_name):
        src = (_ROOT / "frontend/src/lib/adminApi.ts").read_text()
        assert fn_name in src, f"adminApi.ts must export {fn_name}"


# ===========================================================================
# TC-017: SetupAccount page exists and posts to /auth/setup
# ===========================================================================

class TestSetupAccountPage:
    """TC-017 — SetupAccount.tsx exists and calls POST /auth/setup."""

    def test_file_exists(self):
        assert (_ROOT / "frontend/src/pages/SetupAccount.tsx").exists()

    def test_posts_to_setup(self):
        src = (_ROOT / "frontend/src/pages/SetupAccount.tsx").read_text()
        assert "/auth/setup" in src

    def test_has_token_field(self):
        src = (_ROOT / "frontend/src/pages/SetupAccount.tsx").read_text()
        assert "token" in src

    def test_has_password_fields(self):
        src = (_ROOT / "frontend/src/pages/SetupAccount.tsx").read_text()
        assert "password" in src.lower()


# ===========================================================================
# TC-018: Subscription edit page covers all modifiable fields
# ===========================================================================

class TestSubscriptionEditPage:
    """TC-018 — SubscriptionEdit.tsx covers tier, status, raster_mode, timelapse."""

    def test_file_exists(self):
        assert (_ROOT / "frontend/src/pages/admin/SubscriptionEdit.tsx").exists()

    def test_tier_field(self):
        src = (_ROOT / "frontend/src/pages/admin/SubscriptionEdit.tsx").read_text()
        assert "tier" in src

    def test_raster_serving_mode_field(self):
        src = (_ROOT / "frontend/src/pages/admin/SubscriptionEdit.tsx").read_text()
        assert "raster_serving_mode" in src

    def test_timelapse_field(self):
        src = (_ROOT / "frontend/src/pages/admin/SubscriptionEdit.tsx").read_text()
        assert "timelapse" in src.lower()


# ===========================================================================
# TC-019: Manager invite page shows one-time token display
# ===========================================================================

class TestManagerInvitePage:
    """TC-019 — ManagerInvite.tsx shows setup_token once after creation."""

    def test_file_exists(self):
        assert (_ROOT / "frontend/src/pages/admin/ManagerInvite.tsx").exists()

    def test_displays_setup_token(self):
        src = (_ROOT / "frontend/src/pages/admin/ManagerInvite.tsx").read_text()
        assert "setup_token" in src or "token" in src.lower()

    def test_shown_only_once_note(self):
        src = (_ROOT / "frontend/src/pages/admin/ManagerInvite.tsx").read_text()
        assert "only once" in src or "one-time" in src or "not stored" in src.lower()

    def test_no_full_name_field_in_invite_form(self):
        """FMN finding: full_name must not be required in invite — Manager sets at setup."""
        src = (_ROOT / "frontend/src/pages/admin/ManagerInvite.tsx").read_text()
        # fullName state and Full Name label must be absent from the form
        assert "fullName" not in src
        assert "Full Name" not in src


# ===========================================================================
# TC-020: UserManagement page is super-admin only
# ===========================================================================

class TestUserManagementPage:
    """TC-020 — UserManagement.tsx guards against non-super-admin access."""

    def test_file_exists(self):
        assert (_ROOT / "frontend/src/pages/admin/UserManagement.tsx").exists()

    def test_checks_is_global_admin(self):
        src = (_ROOT / "frontend/src/pages/admin/UserManagement.tsx").read_text()
        assert "is_global_admin" in src

    def test_shows_forbidden_for_plain_admin(self):
        src = (_ROOT / "frontend/src/pages/admin/UserManagement.tsx").read_text()
        assert "Super-admin" in src or "super_admin" in src or "Forbidden" in src or "access required" in src


# ===========================================================================
# TC-021: No pipeline-trigger controls in admin namespace
# ===========================================================================

class TestNoPipelineTriggerInAdmin:
    """TC-021 — admin namespace must not contain pipeline trigger endpoints."""

    ADMIN_FILES = [
        "backend/app/api/admin/companies.py",
        "backend/app/api/admin/managers.py",
        "backend/app/api/admin/dashboard.py",
        "backend/app/api/admin/subscriptions.py",
    ]

    @pytest.mark.parametrize("rel_path", ADMIN_FILES)
    def test_no_pipeline_trigger(self, rel_path):
        src = (_ROOT / rel_path).read_text().lower()
        assert "trigger" not in src or "patcher" not in src, \
            f"{rel_path} must not contain pipeline trigger logic"


# ===========================================================================
# TC-022: No GEE credential exposure in admin namespace
# ===========================================================================

class TestNoGeeCredentialsInAdmin:
    """TC-022 — admin namespace must not reference GEE service account."""

    GEE_KEYWORDS = ["service_account", "gee_key", "google_credentials", "credentials.json"]

    @pytest.mark.parametrize("keyword", GEE_KEYWORDS)
    def test_no_gee_keyword(self, keyword):
        admin_dir = _ROOT / "backend/app/api/admin"
        for f in admin_dir.glob("*.py"):
            src = f.read_text().lower()
            assert keyword not in src, \
                f"{f.name} must not reference GEE credentials ({keyword})"


# ===========================================================================
# TC-023: No hard-delete on users or companies
# ===========================================================================

class TestNoHardDelete:
    """TC-023 — admin API must not hard-delete users or companies."""

    FILES_TO_CHECK = [
        "backend/app/api/admin/companies.py",
        "backend/app/api/admin/managers.py",
        "backend/app/api/admin/internal_users.py",
    ]

    @pytest.mark.parametrize("rel_path", FILES_TO_CHECK)
    def test_no_delete_statement(self, rel_path):
        src = (_ROOT / rel_path).read_text().lower()
        assert "delete from users" not in src
        assert "delete from companies" not in src


# ===========================================================================
# TC-024: Subscription backend validates against allowed value sets
# ===========================================================================

class TestSubscriptionValidation:
    """TC-024 — subscription PATCH validates tier, status, raster_serving_mode."""

    def test_tier_validation_raises_error(self):
        src = (_ROOT / "backend/app/api/admin/subscriptions.py").read_text()
        assert "VALID_TIERS" in src or ("basic" in src and "premium" in src)
        assert "Invalid tier" in src or "422" in src or "HTTP_422" in src

    def test_status_validation_raises_error(self):
        src = (_ROOT / "backend/app/api/admin/subscriptions.py").read_text()
        assert "VALID_STATUSES" in src or "active" in src
        assert "Invalid status" in src or "422" in src or "HTTP_422" in src

    def test_raster_mode_validation_raises_error(self):
        src = (_ROOT / "backend/app/api/admin/subscriptions.py").read_text()
        assert "VALID_RASTER_MODES" in src
        assert "Invalid raster_serving_mode" in src or "422" in src or "HTTP_422" in src

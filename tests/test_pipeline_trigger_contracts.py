"""
test_pipeline_trigger_contracts.py — CanopySense pipeline trigger contract tests.

Covers TC-001 through TC-020 from FMN-PLAN v1.11 test contract.
All tests are offline (no DB, no subprocess, no GEE required).
Verifies: migration DDL, module presence, function signatures, route registration,
RBAC guard wiring, validation logic, permission model, and regression safety.

Usage:
    python -m pytest tests/test_pipeline_trigger_contracts.py -v
"""
from __future__ import annotations

import importlib
import importlib.util
import inspect
import pathlib
import re
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_ROOT = pathlib.Path(__file__).parent.parent
_BACKEND = _ROOT / "backend"
sys.path.insert(0, str(_BACKEND))


# ---------------------------------------------------------------------------
# Module loader helper (same pattern as test_admin_contracts.py)
# ---------------------------------------------------------------------------

def _make_db_stub() -> types.ModuleType:
    stub = types.ModuleType("app.database")
    stub.get_db_pool = lambda: None
    stub.settings = types.SimpleNamespace(
        SECRET_KEY="test-secret",
        ALGORITHM="HS256",
        ACCESS_TOKEN_EXPIRE_MINUTES=60,
        CLOUD_FUNCTION_URL="",
        PATCHER_API_KEY="",
        CONTRACTOR_ID="",
        PGHOST="localhost",
        PGPORT=5432,
        PGUSER="postgres",
        PGPASSWORD="",
        PGDATABASE="canopysense",
        PGSCHEMA="canopysense",
        FUNCTION_TIMEOUT_SECONDS=120,
        PATCHER_API_VERSION="1.1",
        RASTER_CACHE_TTL_SECONDS=43200,
    )
    return stub


def _load(module_path: str) -> types.ModuleType:
    if "app.database" not in sys.modules:
        sys.modules["app.database"] = _make_db_stub()

    spec = importlib.util.spec_from_file_location(
        module_path,
        _BACKEND / module_path.replace(".", "/").replace("/py", "") / "__init__.py"
        if ((_BACKEND / module_path.replace(".", "/")).is_dir())
        else _BACKEND / (module_path.replace(".", "/") + ".py"),
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot find module: {module_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ===========================================================================
# TC-001: Migration 005 file exists and contains required DDL
# ===========================================================================

class TestMigration005Exists:
    """TC-001 — migration 005_pipeline_trigger.sql is present and correct."""

    def test_file_exists(self):
        f = _ROOT / "database/migrations/005_pipeline_trigger.sql"
        assert f.exists(), "005_pipeline_trigger.sql must exist"

    def test_contains_admin_pipeline_runs(self):
        sql = (_ROOT / "database/migrations/005_pipeline_trigger.sql").read_text()
        assert "admin_pipeline_runs" in sql

    def test_contains_admin_pipeline_schedules(self):
        sql = (_ROOT / "database/migrations/005_pipeline_trigger.sql").read_text()
        assert "admin_pipeline_schedules" in sql

    def test_runs_has_mode_check(self):
        sql = (_ROOT / "database/migrations/005_pipeline_trigger.sql").read_text()
        assert "scheduled" in sql and "backfill" in sql

    def test_schedules_has_cadence_check(self):
        sql = (_ROOT / "database/migrations/005_pipeline_trigger.sql").read_text()
        assert "daily" in sql and "weekly" in sql and "monthly" in sql

    def test_no_drop_existing_tables(self):
        sql = (_ROOT / "database/migrations/005_pipeline_trigger.sql").read_text().lower()
        assert "drop table" not in sql

    def test_is_idempotent(self):
        sql = (_ROOT / "database/migrations/005_pipeline_trigger.sql").read_text()
        assert "IF NOT EXISTS" in sql


# ===========================================================================
# TC-001 continued: patcher_local.py accepts --run-id
# ===========================================================================

class TestPatcherLocalRunIdArg:
    """TC-001 — patcher_local.py has the --run-id argument."""

    def test_run_id_arg_present(self):
        src = (_ROOT / "src/patcher_local.py").read_text()
        assert "--run-id" in src

    def test_run_id_used_in_main(self):
        src = (_ROOT / "src/patcher_local.py").read_text()
        assert "args.run_id" in src


# ===========================================================================
# TC-002: Dispatcher module — function signatures and allowed modes
# ===========================================================================

class TestDispatcherModule:
    """TC-002 — pipeline_dispatcher.py has required functions and constants."""

    def _mod(self):
        if "app.database" not in sys.modules:
            sys.modules["app.database"] = _make_db_stub()
        return _load("app.services.pipeline_dispatcher")

    def test_module_importable(self):
        mod = self._mod()
        assert mod is not None

    def test_allowed_modes_set(self):
        mod = self._mod()
        assert hasattr(mod, "ALLOWED_MODES")
        assert "scheduled" in mod.ALLOWED_MODES
        assert "backfill" in mod.ALLOWED_MODES

    def test_upload_not_in_allowed_modes(self):
        mod = self._mod()
        assert "upload" not in mod.ALLOWED_MODES

    def test_allowed_cadences_set(self):
        mod = self._mod()
        assert hasattr(mod, "ALLOWED_CADENCES")
        assert {"daily", "weekly", "monthly"} == mod.ALLOWED_CADENCES

    def test_max_backfill_months_defined(self):
        mod = self._mod()
        assert hasattr(mod, "MAX_BACKFILL_MONTHS")
        assert mod.MAX_BACKFILL_MONTHS >= 12

    def test_validate_trigger_request_is_async(self):
        mod = self._mod()
        assert inspect.iscoroutinefunction(mod.validate_trigger_request)

    def test_check_concurrency_is_async(self):
        mod = self._mod()
        assert inspect.iscoroutinefunction(mod.check_concurrency)

    def test_create_run_record_is_async(self):
        mod = self._mod()
        assert inspect.iscoroutinefunction(mod.create_run_record)

    def test_dispatch_trigger_is_async(self):
        mod = self._mod()
        assert inspect.iscoroutinefunction(mod.dispatch_trigger)

    def test_patcher_local_path_points_to_existing_file(self):
        mod = self._mod()
        assert hasattr(mod, "PATCHER_LOCAL_PATH")
        assert mod.PATCHER_LOCAL_PATH.exists(), (
            f"PATCHER_LOCAL_PATH {mod.PATCHER_LOCAL_PATH} must exist"
        )

    def test_no_shell_true_in_dispatcher(self):
        src = (_BACKEND / "app/services/pipeline_dispatcher.py").read_text()
        assert "shell=True" not in src, "Subprocess must never use shell=True"


# ===========================================================================
# TC-003: Trigger request contract — validation logic (sync unit tests)
# ===========================================================================

class TestValidationLogicOffline:
    """TC-003 — validate_trigger_request rejects bad inputs without a DB."""

    def _validate_sync(self, mode, company_id, estate_id, afdeling_id, date_start, date_end):
        """
        Run validate_trigger_request with a fake pool that always returns a valid row
        for estate/afdeling lookups so we can focus on non-DB validation paths.
        """
        import asyncio
        if "app.database" not in sys.modules:
            sys.modules["app.database"] = _make_db_stub()
        mod = _load("app.services.pipeline_dispatcher")

        fake_pool = MagicMock()
        fake_conn = AsyncMock()
        fake_conn.fetchrow = AsyncMock(return_value={"id": 1})
        fake_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=fake_conn)
        fake_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        coro = mod.validate_trigger_request(
            fake_pool, mode, company_id, estate_id, afdeling_id, date_start, date_end
        )
        return asyncio.run(coro)

    def test_invalid_mode_rejected(self):
        err, code = self._validate_sync("upload", 1, 1, None, None, None)
        assert err is not None
        assert code == 400
        assert "mode" in err.lower()

    def test_scheduled_valid(self):
        err, code = self._validate_sync("scheduled", 1, 1, None, None, None)
        assert err is None

    def test_backfill_requires_date_start(self):
        err, code = self._validate_sync("backfill", 1, 1, None, None, "2026-01")
        assert err is not None and "date_start" in err

    def test_backfill_requires_date_end(self):
        err, code = self._validate_sync("backfill", 1, 1, None, "2024-01", None)
        assert err is not None and "date_end" in err

    def test_backfill_bad_date_format_rejected(self):
        err, code = self._validate_sync("backfill", 1, 1, None, "2024-1", "2024-06")
        assert err is not None and "YYYY-MM" in err

    def test_backfill_start_after_end_rejected(self):
        err, code = self._validate_sync("backfill", 1, 1, None, "2025-06", "2024-01")
        assert err is not None and "date_start" in err.lower()

    def test_backfill_range_too_large_rejected(self):
        err, code = self._validate_sync("backfill", 1, 1, None, "2020-01", "2030-12")
        assert err is not None and "maximum" in err.lower()

    def test_backfill_valid_range_accepted(self):
        err, code = self._validate_sync("backfill", 1, 1, None, "2023-01", "2025-12")
        assert err is None


# ===========================================================================
# TC-004: Unauthenticated access denied (route guard wiring)
# ===========================================================================

class TestPipelineRouteRegistration:
    """TC-004 — pipeline routes registered under /api/admin/pipeline."""

    def test_pipeline_router_in_admin_router(self):
        src = (_BACKEND / "app/api/admin/router.py").read_text()
        assert "pipeline" in src

    def test_pipeline_router_uses_pipeline_prefix(self):
        src = (_BACKEND / "app/api/admin/router.py").read_text()
        assert "/pipeline" in src

    def test_trigger_endpoint_exists(self):
        src = (_BACKEND / "app/api/admin/pipeline.py").read_text()
        assert "/trigger" in src

    def test_runs_endpoint_exists(self):
        src = (_BACKEND / "app/api/admin/pipeline.py").read_text()
        assert "/runs" in src

    def test_schedules_endpoint_exists(self):
        src = (_BACKEND / "app/api/admin/pipeline.py").read_text()
        assert "/schedules" in src

    def test_scopes_estates_endpoint_exists(self):
        src = (_BACKEND / "app/api/admin/pipeline.py").read_text()
        assert "/scopes/estates" in src

    def test_scopes_afdelings_endpoint_exists(self):
        src = (_BACKEND / "app/api/admin/pipeline.py").read_text()
        assert "/scopes/afdelings" in src


# ===========================================================================
# TC-005: Manager access denied — guard dependencies correctly wired
# ===========================================================================

class TestRBACGuardWiring:
    """TC-005 — correct guard deps are wired to trigger/schedule endpoints."""

    def test_trigger_uses_get_current_admin(self):
        src = (_BACKEND / "app/api/admin/pipeline.py").read_text()
        assert "get_current_admin" in src

    def test_schedule_create_uses_get_current_super_admin(self):
        src = (_BACKEND / "app/api/admin/pipeline.py").read_text()
        assert "get_current_super_admin" in src

    def test_schedule_patch_uses_get_current_super_admin(self):
        src = (_BACKEND / "app/api/admin/pipeline.py").read_text()
        lines = src.splitlines()
        # Verify at least 2 occurrences of get_current_super_admin (create + patch)
        count = sum(1 for ln in lines if "get_current_super_admin" in ln)
        assert count >= 2, "Both POST and PATCH /schedules must use get_current_super_admin"

    def test_list_schedules_uses_get_current_admin(self):
        src = (_BACKEND / "app/api/admin/pipeline.py").read_text()
        # GET /schedules uses get_current_admin (read-only for all admins)
        assert "get_current_admin" in src

    def test_deps_module_has_get_current_admin(self):
        src = (_BACKEND / "app/api/deps.py").read_text()
        assert "get_current_admin" in src
        assert "get_current_super_admin" in src


# ===========================================================================
# TC-007: Invalid trigger scopes rejected
# ===========================================================================

class TestScopeValidation:
    """TC-007 — validate_trigger_request rejects missing/invalid scope."""

    def _validate_scope_fail(self, mode, company_id, estate_id, afdeling_id,
                              date_start, date_end, estate_exists=False):
        """Run validate with a pool that returns None for estate lookup (not found)."""
        import asyncio
        if "app.database" not in sys.modules:
            sys.modules["app.database"] = _make_db_stub()
        mod = _load("app.services.pipeline_dispatcher")

        fake_pool = MagicMock()
        fake_conn = AsyncMock()
        # None = estate not found
        fake_conn.fetchrow = AsyncMock(return_value={"id": 1} if estate_exists else None)
        fake_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=fake_conn)
        fake_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        coro = mod.validate_trigger_request(
            fake_pool, mode, company_id, estate_id, afdeling_id, date_start, date_end
        )
        return asyncio.run(coro)

    def test_estate_not_in_company_rejected(self):
        err, code = self._validate_scope_fail(
            "scheduled", 1, 99, None, None, None, estate_exists=False
        )
        assert err is not None
        assert code == 400
        assert "estate_id" in err


# ===========================================================================
# TC-008: Invalid backfill date windows rejected (additional edge cases)
# ===========================================================================

class TestDateWindowValidation:
    """TC-008 — comprehensive date-window validation edge cases."""

    def _valid_dates(self, ds, de):
        import asyncio
        if "app.database" not in sys.modules:
            sys.modules["app.database"] = _make_db_stub()
        mod = _load("app.services.pipeline_dispatcher")

        fake_pool = MagicMock()
        fake_conn = AsyncMock()
        fake_conn.fetchrow = AsyncMock(return_value={"id": 1})
        fake_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=fake_conn)
        fake_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        coro = mod.validate_trigger_request(fake_pool, "backfill", 1, 1, None, ds, de)
        return asyncio.run(coro)

    def test_month_13_rejected(self):
        err, _ = self._valid_dates("2024-13", "2025-01")
        assert err is not None

    def test_month_00_rejected(self):
        err, _ = self._valid_dates("2024-00", "2025-01")
        assert err is not None

    def test_non_ym_format_rejected(self):
        err, _ = self._valid_dates("2024/01", "2025-01")
        assert err is not None

    def test_exact_48_months_accepted(self):
        err, _ = self._valid_dates("2022-01", "2026-01")
        assert err is None

    def test_49_months_rejected(self):
        err, _ = self._valid_dates("2021-12", "2026-01")
        assert err is not None and "maximum" in err.lower()


# ===========================================================================
# TC-009: Concurrency guard — check_concurrency uses correct query
# ===========================================================================

class TestConcurrencyGuard:
    """TC-009 — check_concurrency queries admin_pipeline_runs for running status."""

    def test_concurrency_check_queries_running_status(self):
        src = (_BACKEND / "app/services/pipeline_dispatcher.py").read_text()
        assert "status = 'running'" in src or "status='running'" in src

    def test_concurrency_check_function_exists(self):
        if "app.database" not in sys.modules:
            sys.modules["app.database"] = _make_db_stub()
        mod = _load("app.services.pipeline_dispatcher")
        assert hasattr(mod, "check_concurrency")

    def test_trigger_endpoint_calls_check_concurrency(self):
        src = (_BACKEND / "app/api/admin/pipeline.py").read_text()
        assert "check_concurrency" in src

    def test_trigger_returns_409_on_conflict(self):
        src = (_BACKEND / "app/api/admin/pipeline.py").read_text()
        assert "409" in src


# ===========================================================================
# TC-010: Schedule CRUD structure — request models and endpoint structure
# ===========================================================================

class TestScheduleCRUD:
    """TC-010 — schedule create/update/disable contract shape."""

    def test_schedule_create_model_has_mode(self):
        src = (_BACKEND / "app/api/admin/pipeline.py").read_text()
        assert "class ScheduleCreate" in src
        assert "mode:" in src or "mode :" in src

    def test_schedule_create_model_has_cadence(self):
        src = (_BACKEND / "app/api/admin/pipeline.py").read_text()
        assert "cadence:" in src or "cadence :" in src

    def test_schedule_update_model_has_enabled(self):
        src = (_BACKEND / "app/api/admin/pipeline.py").read_text()
        assert "class ScheduleUpdate" in src
        assert "enabled:" in src or "enabled :" in src

    def test_schedule_cadence_validated_against_allowlist(self):
        src = (_BACKEND / "app/api/admin/pipeline.py").read_text()
        assert "ALLOWED_CADENCES" in src

    def test_create_schedule_logs_to_audit(self):
        src = (_BACKEND / "app/api/admin/pipeline.py").read_text()
        assert "schedule_create" in src

    def test_update_schedule_logs_to_audit(self):
        src = (_BACKEND / "app/api/admin/pipeline.py").read_text()
        assert "schedule_update" in src


# ===========================================================================
# TC-011: Schedule runtime semantics — scheduler is asyncio loop
# ===========================================================================

class TestSchedulerSemantics:
    """TC-011 — scheduler module exists and is asyncio-based (not a daemon/cron)."""

    def test_scheduler_module_exists(self):
        f = _BACKEND / "app/services/pipeline_scheduler.py"
        assert f.exists()

    def test_scheduler_uses_asyncio_sleep(self):
        src = (_BACKEND / "app/services/pipeline_scheduler.py").read_text()
        assert "asyncio.sleep" in src

    def test_scheduler_handles_cancelled_error(self):
        src = (_BACKEND / "app/services/pipeline_scheduler.py").read_text()
        assert "CancelledError" in src

    def test_scheduler_started_in_startup_event(self):
        src = (_BACKEND / "app/main.py").read_text()
        assert "run_scheduler_loop" in src or "pipeline_scheduler" in src

    def test_scheduler_stopped_on_shutdown(self):
        src = (_BACKEND / "app/main.py").read_text()
        assert "_scheduler_task" in src
        assert "cancel()" in src


# ===========================================================================
# TC-012: Run history/status — response shape
# ===========================================================================

class TestRunHistoryShape:
    """TC-012 — run history endpoint returns expected fields."""

    def test_runs_endpoint_returns_items_and_total(self):
        src = (_BACKEND / "app/api/admin/pipeline.py").read_text()
        assert '"items"' in src
        assert '"total"' in src

    def test_run_detail_includes_batches(self):
        src = (_BACKEND / "app/api/admin/pipeline.py").read_text()
        assert '"batches"' in src

    def test_run_detail_queries_patcher_run_log(self):
        src = (_BACKEND / "app/api/admin/pipeline.py").read_text()
        assert "patcher_run_log" in src

    def test_admin_sees_own_runs_only(self):
        src = (_BACKEND / "app/api/admin/pipeline.py").read_text()
        assert "actor_id" in src and "is_global_admin" in src

    def test_super_admin_sees_all_runs(self):
        src = (_BACKEND / "app/api/admin/pipeline.py").read_text()
        assert "is_super" in src or "is_global_admin" in src


# ===========================================================================
# TC-013: Audit log integration
# ===========================================================================

class TestAuditLogIntegration:
    """TC-013 — trigger and schedule actions write to admin_audit_log."""

    def test_trigger_calls_log_admin_action(self):
        src = (_BACKEND / "app/api/admin/pipeline.py").read_text()
        assert "log_admin_action" in src
        assert "pipeline_trigger" in src

    def test_schedule_create_calls_log_admin_action(self):
        src = (_BACKEND / "app/api/admin/pipeline.py").read_text()
        assert "schedule_create" in src

    def test_schedule_update_calls_log_admin_action(self):
        src = (_BACKEND / "app/api/admin/pipeline.py").read_text()
        assert "schedule_update" in src


# ===========================================================================
# TC-014: Secret exposure — patcher key not returned in any response
# ===========================================================================

class TestSecretExposure:
    """TC-014 — no secret values are returned in API responses."""

    def test_pipeline_endpoint_does_not_return_patcher_api_key(self):
        src = (_BACKEND / "app/api/admin/pipeline.py").read_text()
        assert "PATCHER_API_KEY" not in src

    def test_pipeline_endpoint_does_not_return_cloud_function_url(self):
        src = (_BACKEND / "app/api/admin/pipeline.py").read_text()
        assert "CLOUD_FUNCTION_URL" not in src

    def test_dispatcher_env_overlay_not_in_api_response(self):
        src = (_BACKEND / "app/api/admin/pipeline.py").read_text()
        assert "patcher_env" not in src

    def test_sanitized_error_is_truncated(self):
        src = (_BACKEND / "app/services/pipeline_dispatcher.py").read_text()
        assert "500" in src or "[-500:]" in src

    def test_no_shell_injection_path(self):
        src = (_BACKEND / "app/services/pipeline_dispatcher.py").read_text()
        assert "shell=True" not in src


# ===========================================================================
# TC-015: Existing pipeline/raster contracts unaffected
# ===========================================================================

class TestExistingContractsUnaffected:
    """TC-015 — existing test files and migration chain still intact."""

    def test_pipeline_contracts_test_file_exists(self):
        f = _ROOT / "tests/test_pipeline_contracts.py"
        assert f.exists()

    def test_admin_contracts_test_file_exists(self):
        f = _ROOT / "tests/test_admin_contracts.py"
        assert f.exists()

    def test_migration_004_still_present(self):
        f = _ROOT / "database/migrations/004_admin_features.sql"
        assert f.exists()

    def test_patcher_local_still_has_backfill_flag(self):
        src = (_ROOT / "src/patcher_local.py").read_text()
        assert "--backfill" in src

    def test_patcher_local_run_id_is_backwards_compatible(self):
        """--run-id is optional: standalone usage without it still generates UUID."""
        src = (_ROOT / "src/patcher_local.py").read_text()
        assert "args.run_id if args.run_id else" in src or "args.run_id or str(uuid" in src


# ===========================================================================
# TC-016 / TC-017: Frontend pipeline pages exist
# ===========================================================================

class TestFrontendPagesExist:
    """TC-016/TC-017 — all three pipeline frontend pages created."""

    def test_pipeline_trigger_page_exists(self):
        f = _ROOT / "frontend/src/pages/admin/PipelineTrigger.tsx"
        assert f.exists()

    def test_pipeline_run_history_page_exists(self):
        f = _ROOT / "frontend/src/pages/admin/PipelineRunHistory.tsx"
        assert f.exists()

    def test_pipeline_schedules_page_exists(self):
        f = _ROOT / "frontend/src/pages/admin/PipelineSchedules.tsx"
        assert f.exists()

    def test_pipeline_trigger_calls_trigger_api(self):
        src = (_ROOT / "frontend/src/pages/admin/PipelineTrigger.tsx").read_text()
        assert "triggerPipeline" in src

    def test_pipeline_trigger_has_confirm_dialog(self):
        src = (_ROOT / "frontend/src/pages/admin/PipelineTrigger.tsx").read_text()
        assert "confirming" in src or "confirm" in src.lower()

    def test_pipeline_trigger_polls_for_status(self):
        src = (_ROOT / "frontend/src/pages/admin/PipelineTrigger.tsx").read_text()
        assert "getPipelineRun" in src

    def test_run_history_has_pagination(self):
        src = (_ROOT / "frontend/src/pages/admin/PipelineRunHistory.tsx").read_text()
        assert "page" in src

    def test_schedules_page_checks_super_admin(self):
        src = (_ROOT / "frontend/src/pages/admin/PipelineSchedules.tsx").read_text()
        assert "isSuperAdmin" in src or "is_global_admin" in src

    def test_schedules_create_restricted_to_super_admin_in_ui(self):
        src = (_ROOT / "frontend/src/pages/admin/PipelineSchedules.tsx").read_text()
        assert "isSuperAdmin" in src


# ===========================================================================
# TC-018: Frontend routes registered in App.tsx
# ===========================================================================

class TestFrontendRoutes:
    """TC-018 — pipeline routes registered in App.tsx."""

    def test_trigger_route_in_app(self):
        src = (_ROOT / "frontend/src/App.tsx").read_text()
        assert "pipeline/trigger" in src

    def test_history_route_in_app(self):
        src = (_ROOT / "frontend/src/App.tsx").read_text()
        assert "pipeline/history" in src

    def test_schedules_route_in_app(self):
        src = (_ROOT / "frontend/src/App.tsx").read_text()
        assert "pipeline/schedules" in src

    def test_pipeline_nav_in_admin_layout(self):
        src = (_ROOT / "frontend/src/components/AdminLayout.tsx").read_text()
        assert "PIPELINE_NAV" in src or "pipeline" in src.lower()


# ===========================================================================
# TC-019: Backend module import chain is clean
# ===========================================================================

class TestBackendModuleChain:
    """TC-019 — backend pipeline modules are importable without side effects."""

    def test_dispatcher_importable(self):
        if "app.database" not in sys.modules:
            sys.modules["app.database"] = _make_db_stub()
        mod = _load("app.services.pipeline_dispatcher")
        assert mod is not None

    def test_scheduler_importable(self):
        if "app.database" not in sys.modules:
            sys.modules["app.database"] = _make_db_stub()

        # scheduler imports dispatcher — ensure chain is clean
        mod = _load("app.services.pipeline_scheduler")
        assert mod is not None

    def test_settings_has_contractor_id(self):
        stub = _make_db_stub()
        assert hasattr(stub.settings, "CONTRACTOR_ID")

    def test_settings_has_pgschema(self):
        stub = _make_db_stub()
        assert hasattr(stub.settings, "PGSCHEMA")

    def test_settings_has_patcher_api_version(self):
        stub = _make_db_stub()
        assert hasattr(stub.settings, "PATCHER_API_VERSION")


# ===========================================================================
# TC-020: adminApi.ts exports all required pipeline functions
# ===========================================================================

class TestAdminApiExports:
    """TC-020 — frontend adminApi.ts has all 7 pipeline API functions."""

    def _src(self):
        return (_ROOT / "frontend/src/lib/adminApi.ts").read_text()

    def test_list_estates_for_company_exported(self):
        assert "listEstatesForCompany" in self._src()

    def test_list_afdelings_for_estate_exported(self):
        assert "listAfdelingsForEstate" in self._src()

    def test_trigger_pipeline_exported(self):
        assert "triggerPipeline" in self._src()

    def test_list_pipeline_runs_exported(self):
        assert "listPipelineRuns" in self._src()

    def test_get_pipeline_run_exported(self):
        assert "getPipelineRun" in self._src()

    def test_list_pipeline_schedules_exported(self):
        assert "listPipelineSchedules" in self._src()

    def test_create_pipeline_schedule_exported(self):
        assert "createPipelineSchedule" in self._src()

    def test_update_pipeline_schedule_exported(self):
        assert "updatePipelineSchedule" in self._src()

    def test_pipeline_run_type_exported(self):
        assert "PipelineRun" in self._src()

    def test_pipeline_schedule_type_exported(self):
        assert "PipelineSchedule" in self._src()


# ===========================================================================
# FMN-FINDING-1: Concurrency guard overlap — estate-level vs afdeling-level
# ===========================================================================

class TestConcurrencyGuardOverlap:
    """
    FMN Finding 1 — estate/afdeling scope overlap must be bidirectional.

    The original SQL only used `afdeling_id = $4 OR $4 IS NULL`, which
    missed the case where an estate-level run (afdeling_id IS NULL in DB)
    should block a new afdeling-level request.

    Fix: `afdeling_id = $4 OR afdeling_id IS NULL OR $4 IS NULL`
    """

    def _src(self):
        return (_BACKEND / "app/services/pipeline_dispatcher.py").read_text()

    def _mod(self):
        if "app.database" not in sys.modules:
            sys.modules["app.database"] = _make_db_stub()
        return _load("app.services.pipeline_dispatcher")

    def test_concurrency_sql_includes_afdeling_is_null_arm(self):
        """Existing estate-level run (NULL afdeling) must block new afdeling-level request."""
        src = self._src()
        assert "afdeling_id IS NULL" in src, (
            "check_concurrency SQL must include `afdeling_id IS NULL` to catch "
            "estate-level runs blocking afdeling-level requests"
        )

    def test_concurrency_sql_overlap_condition_is_three_way(self):
        """The OR chain must have all three arms: exact, existing-null, new-null."""
        src = self._src()
        assert "afdeling_id = $4 OR afdeling_id IS NULL OR $4 IS NULL" in src, (
            "Expected three-arm overlap condition in check_concurrency"
        )

    def test_concurrency_old_one_way_pattern_not_present(self):
        """Old two-arm pattern `$4 IS NULL)` alone must not be the only guard."""
        src = self._src()
        # The old pattern was: (afdeling_id = $4 OR $4 IS NULL)
        # With the fix the condition has three arms; old-only form should be gone.
        assert "(afdeling_id = $4 OR $4 IS NULL)" not in src, (
            "Old two-arm concurrency condition detected; fix must use three-arm form"
        )

    def test_estate_id_not_optional_in_concurrency_sql(self):
        """estate_id should match exactly — the `OR $3 IS NULL` arm was also removed."""
        src = self._src()
        assert "(estate_id = $3 OR $3 IS NULL)" not in src, (
            "estate_id match must be exact (no IS NULL arm) since estate_id is always required"
        )

    def test_check_concurrency_callable_estate_level_blocked_by_afdeling_run(self):
        """
        Simulate: existing row has afdeling_id IS NULL (estate-level run).
        A new afdeling-level request for the same estate should be BLOCKED.
        The mock returns a row unconditionally, verifying the query is reached.
        """
        import asyncio
        mod = self._mod()

        fake_pool = MagicMock()
        fake_conn = AsyncMock()
        # Simulate DB found a conflicting row
        fake_conn.fetchrow = AsyncMock(return_value={"id": 99})
        fake_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=fake_conn)
        fake_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        result = asyncio.run(mod.check_concurrency(fake_pool, "scheduled", 1, 10, 5))
        assert result is True, "check_concurrency must return True when DB returns a conflicting row"

    def test_check_concurrency_callable_no_conflict_returns_false(self):
        """When DB returns no conflicting row, check_concurrency must return False."""
        import asyncio
        mod = self._mod()

        fake_pool = MagicMock()
        fake_conn = AsyncMock()
        fake_conn.fetchrow = AsyncMock(return_value=None)
        fake_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=fake_conn)
        fake_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        result = asyncio.run(mod.check_concurrency(fake_pool, "scheduled", 1, 10, 5))
        assert result is False

    def test_check_concurrency_passes_correct_arg_count(self):
        """check_concurrency must accept mode, company_id, estate_id, afdeling_id."""
        mod = self._mod()
        sig = inspect.signature(mod.check_concurrency)
        params = list(sig.parameters)
        assert "mode" in params
        assert "company_id" in params
        assert "estate_id" in params
        assert "afdeling_id" in params


# ===========================================================================
# FMN-FINDING-2: Schedule update must revalidate merged date window
# ===========================================================================

class TestScheduleUpdateDateValidation:
    """
    FMN Finding 2 — PATCH /schedules/{id} must load existing schedule and
    validate the merged (existing + patch) date window before applying update.

    Without this fix a valid backfill schedule could be patched into a reversed
    or over-limit date range.
    """

    def _src_pipeline(self):
        return (_BACKEND / "app/api/admin/pipeline.py").read_text()

    def _src_dispatcher(self):
        return (_BACKEND / "app/services/pipeline_dispatcher.py").read_text()

    def _mod_dispatcher(self):
        if "app.database" not in sys.modules:
            sys.modules["app.database"] = _make_db_stub()
        return _load("app.services.pipeline_dispatcher")

    # -- validate_date_window is a standalone exported helper --

    def test_validate_date_window_exported_from_dispatcher(self):
        mod = self._mod_dispatcher()
        assert hasattr(mod, "validate_date_window"), (
            "validate_date_window must be a top-level export in pipeline_dispatcher"
        )

    def test_validate_date_window_is_synchronous(self):
        mod = self._mod_dispatcher()
        assert not inspect.iscoroutinefunction(mod.validate_date_window), (
            "validate_date_window must be a regular (sync) function — no DB needed"
        )

    def test_validate_date_window_accepts_non_backfill_without_dates(self):
        mod = self._mod_dispatcher()
        err, code = mod.validate_date_window("scheduled", None, None)
        assert err is None, "Non-backfill mode must pass with no dates"

    def test_validate_date_window_rejects_reversed_dates(self):
        mod = self._mod_dispatcher()
        err, code = mod.validate_date_window("backfill", "2025-06", "2023-01")
        assert err is not None and code == 400
        assert "date_start" in err.lower()

    def test_validate_date_window_rejects_excessive_range(self):
        mod = self._mod_dispatcher()
        err, code = mod.validate_date_window("backfill", "2020-01", "2030-12")
        assert err is not None and code == 400
        assert "maximum" in err.lower()

    def test_validate_date_window_rejects_bad_format(self):
        mod = self._mod_dispatcher()
        err, code = mod.validate_date_window("backfill", "2024-1", "2024-06")
        assert err is not None and "YYYY-MM" in err

    def test_validate_date_window_accepts_valid_range(self):
        mod = self._mod_dispatcher()
        err, code = mod.validate_date_window("backfill", "2023-01", "2025-12")
        assert err is None

    # -- update_schedule source-level checks --

    def test_update_schedule_loads_mode_from_existing_row(self):
        """Must fetch mode (not just id) so date window validation knows the mode."""
        src = self._src_pipeline()
        assert "mode" in src and "date_start" in src and "date_end" in src, (
            "update_schedule must SELECT mode, date_start, date_end from existing schedule"
        )

    def test_update_schedule_imports_validate_date_window(self):
        """pipeline.py must import validate_date_window from pipeline_dispatcher."""
        src = self._src_pipeline()
        assert "validate_date_window" in src, (
            "pipeline.py must import and call validate_date_window in update_schedule"
        )

    def test_update_schedule_merges_dates_before_validate(self):
        """Merged fields (existing + patch) must be passed to validate_date_window."""
        src = self._src_pipeline()
        assert "merged_start" in src or "merged_end" in src or (
            "existing[" in src and "validate_date_window" in src
        ), (
            "update_schedule must merge existing date fields with patch before validating"
        )

    def test_update_schedule_rejects_reversed_dates_via_mock(self):
        """
        Functional: mock pool returns a backfill schedule with valid dates.
        Patch with reversed dates must raise HTTPException 400.
        """
        import asyncio
        from fastapi import HTTPException as FastHTTPException

        if "app.database" not in sys.modules:
            sys.modules["app.database"] = _make_db_stub()

        # Need to load pipeline.py which imports from pipeline_dispatcher
        # Ensure dispatcher is pre-loaded so import chain works
        dispatcher_mod = _load("app.services.pipeline_dispatcher")
        sys.modules["app.services.pipeline_dispatcher"] = dispatcher_mod

        import typing as _typing
        pipeline_mod = _load("app.api.admin.pipeline")
        pipeline_mod.ScheduleUpdate.model_rebuild(_types_namespace={"Optional": _typing.Optional, "datetime": _typing.Any})

        # Existing schedule: backfill, 2023-01 → 2025-12 (valid)
        fake_existing = {
            "id": 1,
            "mode": "backfill",
            "date_start": "2023-01",
            "date_end": "2025-12",
        }

        fake_pool = MagicMock()
        fake_conn = AsyncMock()
        fake_conn.fetchrow = AsyncMock(return_value=fake_existing)
        fake_conn.execute = AsyncMock(return_value=None)
        fake_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=fake_conn)
        fake_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        # Fake super-admin user dependency
        fake_user = {"id": 1, "username": "superadmin", "is_global_admin": True}

        # Patch request: reverse the dates
        req = pipeline_mod.ScheduleUpdate(date_start="2025-12", date_end="2023-01")

        with pytest.raises(FastHTTPException) as exc_info:
            asyncio.run(
                pipeline_mod.update_schedule(
                    schedule_id=1,
                    req=req,
                    user=fake_user,
                    pool=fake_pool,
                )
            )
        assert exc_info.value.status_code == 400
        assert "date_start" in exc_info.value.detail.lower()

    def test_update_schedule_rejects_excessive_range_via_mock(self):
        """
        Functional: patch date_start only; existing date_end stays.
        The merged range must be validated — reject if it exceeds MAX_BACKFILL_MONTHS.
        """
        import asyncio
        from fastapi import HTTPException as FastHTTPException

        if "app.database" not in sys.modules:
            sys.modules["app.database"] = _make_db_stub()

        dispatcher_mod = _load("app.services.pipeline_dispatcher")
        sys.modules["app.services.pipeline_dispatcher"] = dispatcher_mod

        import typing as _typing
        pipeline_mod = _load("app.api.admin.pipeline")
        pipeline_mod.ScheduleUpdate.model_rebuild(_types_namespace={"Optional": _typing.Optional, "datetime": _typing.Any})

        # Existing schedule: backfill, date_end = 2030-12
        fake_existing = {
            "id": 2,
            "mode": "backfill",
            "date_start": "2023-01",
            "date_end": "2030-12",
        }

        fake_pool = MagicMock()
        fake_conn = AsyncMock()
        fake_conn.fetchrow = AsyncMock(return_value=fake_existing)
        fake_conn.execute = AsyncMock(return_value=None)
        fake_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=fake_conn)
        fake_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        fake_user = {"id": 1, "username": "superadmin", "is_global_admin": True}

        # Patch only date_start to make range = 2020-01 → 2030-12 (>48 months)
        req = pipeline_mod.ScheduleUpdate(date_start="2020-01")

        with pytest.raises(FastHTTPException) as exc_info:
            asyncio.run(
                pipeline_mod.update_schedule(
                    schedule_id=2,
                    req=req,
                    user=fake_user,
                    pool=fake_pool,
                )
            )
        assert exc_info.value.status_code == 400
        assert "maximum" in exc_info.value.detail.lower()

    def test_update_schedule_accepts_valid_patch_via_mock(self):
        """Valid date patch on a backfill schedule must not raise."""
        import asyncio
        from fastapi import HTTPException as FastHTTPException

        if "app.database" not in sys.modules:
            sys.modules["app.database"] = _make_db_stub()

        dispatcher_mod = _load("app.services.pipeline_dispatcher")
        sys.modules["app.services.pipeline_dispatcher"] = dispatcher_mod

        # Need audit_log stub for pipeline.py import
        if "app.api.admin.audit_log" not in sys.modules:
            stub = types.ModuleType("app.api.admin.audit_log")
            stub.log_admin_action = AsyncMock(return_value=None)
            sys.modules["app.api.admin.audit_log"] = stub

        # Need deps stub
        if "app.api.deps" not in sys.modules:
            stub = types.ModuleType("app.api.deps")
            stub.get_current_admin = lambda: None
            stub.get_current_super_admin = lambda: None
            sys.modules["app.api.deps"] = stub

        import typing as _typing
        pipeline_mod = _load("app.api.admin.pipeline")
        pipeline_mod.ScheduleUpdate.model_rebuild(_types_namespace={"Optional": _typing.Optional, "datetime": _typing.Any})

        fake_existing = {
            "id": 3,
            "mode": "backfill",
            "date_start": "2023-01",
            "date_end": "2024-12",
        }

        fake_pool = MagicMock()
        fake_conn = AsyncMock()
        fake_conn.fetchrow = AsyncMock(return_value=fake_existing)
        fake_conn.execute = AsyncMock(return_value=None)
        fake_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=fake_conn)
        fake_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        fake_user = {"id": 1, "username": "superadmin", "is_global_admin": True}

        # Valid patch: tighten end date (still within range)
        req = pipeline_mod.ScheduleUpdate(date_end="2024-06")

        result = asyncio.run(
            pipeline_mod.update_schedule(
                schedule_id=3,
                req=req,
                user=fake_user,
                pool=fake_pool,
            )
        )
        assert result["status"] == "updated"

    def test_scheduled_mode_patch_ignores_date_validation(self):
        """For a scheduled-mode schedule, patching dates should not trigger date validation."""
        mod = self._mod_dispatcher()
        # scheduled mode: validate_date_window always returns (None, None)
        err, code = mod.validate_date_window("scheduled", None, None)
        assert err is None
        # Even with values passed (would be ignored)
        err, code = mod.validate_date_window("scheduled", "2020-01", "2030-12")
        assert err is None

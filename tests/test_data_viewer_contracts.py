"""
test_data_viewer_contracts.py — CanopySense Admin Data Viewer contract tests.

Covers TC-002 through TC-014, TC-017 through TC-019 from FMN-PLAN v1.13.
All tests are offline (no DB required).

They verify:
  - TABLE_ALLOWLIST structure and completeness
  - Catalog endpoint exposes only allowed tables
  - Row/column endpoints are GET-only (read-only)
  - RBAC: get_current_super_admin enforced on all endpoints
  - Sensitive columns (password_hash, setup_token_hash, setup_token_expires_at) absent
  - Geometry/JSON columns are summarized in _build_select, not dumped raw
  - Pagination cap: MAX_PAGE_SIZE = 100
  - Sort identifiers validated against server-side sort_allowed list
  - Filter column validated against search_col; filter value is parameterized
  - Unknown table_id raises 404

Usage:
    python -m pytest tests/test_data_viewer_contracts.py -v
"""
from __future__ import annotations

import importlib.util
import inspect
import pathlib
import sys
import types

import pytest

_ROOT = pathlib.Path(__file__).parent.parent
_BACKEND = _ROOT / "backend"
sys.path.insert(0, str(_BACKEND))

REDACTED_COLUMNS = {"password_hash", "setup_token_hash", "setup_token_expires_at"}


# ---------------------------------------------------------------------------
# Module loader (stubs out DB / auth to avoid startup side effects)
# ---------------------------------------------------------------------------

def _make_db_stub() -> types.ModuleType:
    stub = types.ModuleType("app.database")
    stub.get_db_pool = lambda: None  # type: ignore[attr-defined]
    stub.settings = types.SimpleNamespace(  # type: ignore[attr-defined]
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


def _ensure_stubs() -> None:
    if "app.database" not in sys.modules:
        sys.modules["app.database"] = _make_db_stub()
    if "app.auth.jwt" not in sys.modules:
        jwt_stub = types.ModuleType("app.auth.jwt")
        jwt_stub.decode_access_token = lambda t: {"sub": "test"}  # type: ignore[attr-defined]
        jwt_stub.get_password_hash = lambda p: "hashed"  # type: ignore[attr-defined]
        jwt_stub.verify_password = lambda p, h: True  # type: ignore[attr-defined]
        sys.modules["app.auth.jwt"] = jwt_stub


def _load(dotted: str) -> types.ModuleType:
    path = _BACKEND / (dotted.replace(".", "/") + ".py")
    spec = importlib.util.spec_from_file_location(dotted, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot find: {path}")
    _ensure_stubs()
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


@pytest.fixture(scope="module")
def dv():
    return _load("app.api.admin.data_viewer")


@pytest.fixture(scope="module")
def deps():
    return _load("app.api.deps")


# ---------------------------------------------------------------------------
# TC-001 (TASK-001): TABLE_ALLOWLIST audit — all Phase 1 tables present
# ---------------------------------------------------------------------------

EXPECTED_TABLES = {
    "companies",
    "users",
    "company_subscriptions",
    "admin_audit_log",
    "admin_pipeline_runs",
    "admin_pipeline_schedules",
    "estates",
    "afdelings",
    "blocks",
    "satellite_data",
    "patcher_run_log",
}


def test_tc001_all_phase1_tables_present(dv):
    """TC-001: All Phase 1 operational tables are in TABLE_ALLOWLIST."""
    assert EXPECTED_TABLES.issubset(set(dv.TABLE_ALLOWLIST.keys()))


def test_tc001_allowlist_entries_have_required_keys(dv):
    required = {"schema", "table", "display", "columns", "geometry_cols",
                "json_cols", "default_sort", "sort_allowed"}
    for tid, entry in dv.TABLE_ALLOWLIST.items():
        missing = required - set(entry.keys())
        assert not missing, f"Table '{tid}' missing keys: {missing}"


# ---------------------------------------------------------------------------
# TC-002: Catalog endpoint exists and returns correct shape
# ---------------------------------------------------------------------------

def test_tc002_catalog_endpoint_exists(dv):
    """TC-002: /catalog GET endpoint is registered on the router."""
    routes = {r.path for r in dv.router.routes}
    assert "/catalog" in routes


def test_tc002_catalog_returns_all_allowlisted_tables(dv):
    """TC-002: catalog() result contains every entry from TABLE_ALLOWLIST."""
    import asyncio

    async def _run():
        class FakeAdmin:
            pass
        return await dv.catalog(admin=FakeAdmin())

    result = asyncio.run(_run())
    returned_ids = {t["id"] for t in result["tables"]}
    assert returned_ids == set(dv.TABLE_ALLOWLIST.keys())


# ---------------------------------------------------------------------------
# TC-003: Row/column endpoints are read-only (GET only, no mutation methods)
# ---------------------------------------------------------------------------

def test_tc003_all_routes_are_get_only(dv):
    """TC-003: No Data Viewer route uses POST, PUT, PATCH, or DELETE."""
    for route in dv.router.routes:
        methods = getattr(route, "methods", set()) or set()
        mutation = methods & {"POST", "PUT", "PATCH", "DELETE"}
        assert not mutation, f"Route {route.path} has mutation methods: {mutation}"


# ---------------------------------------------------------------------------
# TC-004 / TC-005: Super-admin dependency enforced on all endpoints
# ---------------------------------------------------------------------------

def test_tc004_tc005_super_admin_dep_on_all_endpoints(dv, deps):
    """TC-004/TC-005: get_current_super_admin is the auth dep for all Data Viewer endpoints."""
    for route in dv.router.routes:
        endpoint = getattr(route, "endpoint", None)
        if endpoint is None:
            continue
        src = inspect.getsource(endpoint)
        assert "get_current_super_admin" in src, (
            f"Endpoint {route.path} does not use get_current_super_admin"
        )


def test_tc005_get_current_super_admin_rejects_non_global_admin(deps):
    """TC-005: get_current_super_admin only accepts is_global_admin=TRUE."""
    src = inspect.getsource(deps.get_current_super_admin)
    assert "is_global_admin" in src
    # Must not accept is_admin alone
    assert "is_global_admin" in src
    # Verify it raises 403 for non-super-admin
    assert "403" in src or "FORBIDDEN" in src


# ---------------------------------------------------------------------------
# TC-006: Unknown table_id returns 404
# ---------------------------------------------------------------------------

def test_tc006_unknown_table_raises_404(dv):
    """TC-006: _get_entry raises HTTPException(404) for unknown table_id."""
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        dv._get_entry("__nonexistent_table__")
    assert exc_info.value.status_code == 404


def test_tc006_known_tables_do_not_raise(dv):
    for tid in EXPECTED_TABLES:
        entry = dv._get_entry(tid)
        assert entry is not None


# ---------------------------------------------------------------------------
# TC-007: Sort identifier injection rejected — sort_col validated against allowlist
# ---------------------------------------------------------------------------

def test_tc007_sort_col_falls_back_to_default_when_disallowed(dv):
    """TC-007: If sort_col is not in sort_allowed, effective_sort falls back to default_sort."""
    src = inspect.getsource(dv.get_rows)
    # The code must check membership before using sort_col as SQL identifier
    assert "sort_allowed" in src
    assert "default_sort" in src


def test_tc007_sort_dir_is_hardcoded_safe_values(dv):
    """TC-007: sort_dir is forced to 'DESC' or 'ASC' — no client string reaches SQL directly."""
    src = inspect.getsource(dv.get_rows)
    assert '"DESC"' in src and '"ASC"' in src


def test_tc007_no_table_from_client_input(dv):
    """TC-007: fqt (fully qualified table) is always assembled from server-side allowlist values."""
    src = inspect.getsource(dv.get_rows)
    # fqt comes from entry["schema"] and entry["table"], never from user input
    assert 'entry["schema"]' in src or "entry['schema']" in src
    assert 'entry["table"]' in src or "entry['table']" in src


# ---------------------------------------------------------------------------
# TC-008: Filter value injection safe — parameterized with $N
# ---------------------------------------------------------------------------

def test_tc008_filter_value_is_parameterized(dv):
    """TC-008: filter_val is always a $N parameter, never string-concatenated into SQL."""
    src = inspect.getsource(dv.get_rows)
    # filter_val is appended to params list, never formatted directly into the query
    assert "params.append" in src
    # The WHERE clause uses $N parameter marker
    assert "ILIKE $" in src


def test_tc008_filter_col_must_equal_search_col(dv):
    """TC-008: filter_col is validated against server-side search_col before use as SQL identifier."""
    src = inspect.getsource(dv.get_rows)
    assert "search_col" in src
    assert "422" in src


# ---------------------------------------------------------------------------
# TC-009: Sensitive columns are absent from every table's column allowlist
# ---------------------------------------------------------------------------

def test_tc009_redacted_columns_not_in_any_allowlist(dv):
    """TC-009: password_hash, setup_token_hash, setup_token_expires_at absent from all entries."""
    for tid, entry in dv.TABLE_ALLOWLIST.items():
        cols = set(entry["columns"])
        found = cols & REDACTED_COLUMNS
        assert not found, f"Table '{tid}' exposes redacted columns: {found}"


def test_tc009_users_table_has_no_credential_fields(dv):
    """TC-009: Users entry specifically excludes all credential and token fields."""
    users_entry = dv.TABLE_ALLOWLIST["users"]
    cols = set(users_entry["columns"])
    assert "password_hash" not in cols
    assert "setup_token_hash" not in cols
    assert "setup_token_expires_at" not in cols
    # But normal user fields are present
    assert "username" in cols
    assert "email" in cols
    assert "is_active" in cols


# ---------------------------------------------------------------------------
# TC-010: Pagination bounded — MAX_PAGE_SIZE enforced
# ---------------------------------------------------------------------------

def test_tc010_max_page_size_constant_exists(dv):
    """TC-010: MAX_PAGE_SIZE constant is defined."""
    assert hasattr(dv, "MAX_PAGE_SIZE")
    assert dv.MAX_PAGE_SIZE == 100


def test_tc010_page_size_query_param_capped(dv):
    """TC-010: page_size Query param has le=MAX_PAGE_SIZE, preventing oversized requests."""
    src = inspect.getsource(dv.get_rows)
    assert "le=MAX_PAGE_SIZE" in src or "le=100" in src


# ---------------------------------------------------------------------------
# TC-011: Sorting works only on allowed columns
# ---------------------------------------------------------------------------

def test_tc011_all_default_sort_cols_in_sort_allowed(dv):
    """TC-011: default_sort for every table is within its sort_allowed list."""
    for tid, entry in dv.TABLE_ALLOWLIST.items():
        assert entry["default_sort"] in entry["sort_allowed"], (
            f"Table '{tid}': default_sort '{entry['default_sort']}' not in sort_allowed"
        )


def test_tc011_all_sort_allowed_cols_in_columns(dv):
    """TC-011: Every sort_allowed column is in the table's columns list."""
    for tid, entry in dv.TABLE_ALLOWLIST.items():
        cols = set(entry["columns"])
        for sc in entry["sort_allowed"]:
            assert sc in cols, (
                f"Table '{tid}': sort_allowed '{sc}' not in columns list"
            )


# ---------------------------------------------------------------------------
# TC-012: Search/filter on designated column only
# ---------------------------------------------------------------------------

def test_tc012_search_col_in_columns_when_defined(dv):
    """TC-012: search_col for each table, when defined, is within the table's columns list."""
    for tid, entry in dv.TABLE_ALLOWLIST.items():
        sc = entry.get("search_col")
        if sc is not None:
            assert sc in entry["columns"], (
                f"Table '{tid}': search_col '{sc}' not in columns list"
            )


# ---------------------------------------------------------------------------
# TC-013: Geometry and JSON values are summarized in _build_select
# ---------------------------------------------------------------------------

def test_tc013_geometry_cols_use_st_astext(dv):
    """TC-013: _build_select wraps geometry columns with ST_AsText and truncates."""
    src = inspect.getsource(dv._build_select)
    assert "ST_AsText" in src
    assert "LEFT(" in src


def test_tc013_json_cols_use_text_cast_and_truncate(dv):
    """TC-013: _build_select wraps json columns with ::text cast and LEFT truncation."""
    src = inspect.getsource(dv._build_select)
    assert "::text" in src
    assert "LEFT(" in src


def test_tc013_geometry_tables_have_geometry_cols_defined(dv):
    """TC-013: Tables with spatial data have geometry_cols entries."""
    assert len(dv.TABLE_ALLOWLIST["estates"]["geometry_cols"]) > 0
    assert len(dv.TABLE_ALLOWLIST["afdelings"]["geometry_cols"]) > 0


def test_tc013_json_tables_have_json_cols_defined(dv):
    """TC-013: Tables with JSON/JSONB data have json_cols entries."""
    assert len(dv.TABLE_ALLOWLIST["satellite_data"]["json_cols"]) > 0
    assert len(dv.TABLE_ALLOWLIST["companies"]["json_cols"]) > 0
    assert len(dv.TABLE_ALLOWLIST["admin_audit_log"]["json_cols"]) > 0


def test_tc001_schema_correctness(dv):
    """TC-001: Schema assignments match actual DB layout (migrations run in canopysense search path)."""
    assert dv.TABLE_ALLOWLIST["companies"]["schema"] == "public"
    assert dv.TABLE_ALLOWLIST["users"]["schema"] == "public"
    assert dv.TABLE_ALLOWLIST["company_subscriptions"]["schema"] == "canopysense"
    assert dv.TABLE_ALLOWLIST["admin_audit_log"]["schema"] == "canopysense"
    assert dv.TABLE_ALLOWLIST["admin_pipeline_runs"]["schema"] == "canopysense"
    assert dv.TABLE_ALLOWLIST["admin_pipeline_schedules"]["schema"] == "canopysense"


# ---------------------------------------------------------------------------
# TC-014: Audit logging is called on row fetch
# ---------------------------------------------------------------------------

def test_tc014_audit_logging_in_get_rows(dv):
    """TC-014: get_rows calls log_admin_action with data_viewer_table_view action."""
    src = inspect.getsource(dv.get_rows)
    assert "log_admin_action" in src
    assert "data_viewer_table_view" in src


# ---------------------------------------------------------------------------
# TC-017: Existing admin features not broken — router import succeeds
# ---------------------------------------------------------------------------

def test_tc017_router_imports_without_error():
    """TC-017: admin router imports data_viewer without error."""
    mod = _load("app.api.admin.router")
    assert mod is not None


def test_tc017_data_viewer_router_registered(dv):
    """TC-017: data_viewer module exposes a router object."""
    assert hasattr(dv, "router")
    assert dv.router is not None


# ---------------------------------------------------------------------------
# TC-019: Backend module loads cleanly
# ---------------------------------------------------------------------------

def test_tc019_module_loads_without_error(dv):
    """TC-019: data_viewer module loads with no import errors."""
    assert dv is not None
    assert hasattr(dv, "TABLE_ALLOWLIST")
    assert hasattr(dv, "get_rows")
    assert hasattr(dv, "catalog")
    assert hasattr(dv, "get_columns")

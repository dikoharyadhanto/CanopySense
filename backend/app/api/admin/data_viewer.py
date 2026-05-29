from datetime import date, datetime
from decimal import Decimal

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.admin.audit_log import log_admin_action
from app.api.deps import get_current_super_admin
from app.database import get_db_pool

router = APIRouter()

MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 20

# Server-side allowlist — client input never controls table, column, or sort identifiers.
# Columns listed here are the only ones that appear in SELECT.
# Redacted columns (password_hash, setup_token_hash, etc.) are simply absent from each entry's
# "columns" list and never referenced in any query.
TABLE_ALLOWLIST: dict = {
    "companies": {
        "schema": "public",
        "table": "companies",
        "display": "Companies",
        "columns": ["id", "company_id", "company_name", "created_at", "metadata"],
        "geometry_cols": [],
        "json_cols": ["metadata"],
        "default_sort": "id",
        "sort_allowed": ["id", "company_name", "created_at"],
        "search_col": "company_name",
    },
    "users": {
        "schema": "public",
        "table": "users",
        "display": "Users",
        # password_hash, setup_token_hash, setup_token_expires_at are excluded
        "columns": [
            "id", "company_id", "email", "full_name", "username", "phone_number",
            "is_global_admin", "is_admin", "is_active", "setup_required",
            "created_at", "updated_at",
        ],
        "geometry_cols": [],
        "json_cols": [],
        "default_sort": "id",
        "sort_allowed": ["id", "username", "email", "created_at"],
        "search_col": "username",
    },
    "company_subscriptions": {
        "schema": "canopysense",
        "table": "company_subscriptions",
        "display": "Company Subscriptions",
        "columns": [
            "id", "company_id", "tier", "status", "billing_interval",
            "subscription_starts_at", "subscription_ends_at",
            "timelapse_enabled", "timelapse_period_months",
            "raster_serving_mode", "updated_at",
        ],
        "geometry_cols": [],
        "json_cols": [],
        "default_sort": "id",
        "sort_allowed": ["id", "company_id", "tier", "status"],
        "search_col": None,
    },
    "admin_audit_log": {
        "schema": "canopysense",
        "table": "admin_audit_log",
        "display": "Audit Log",
        "columns": ["id", "actor_id", "action", "target_type", "target_id", "metadata", "created_at"],
        "geometry_cols": [],
        "json_cols": ["metadata"],
        "default_sort": "id",
        "sort_allowed": ["id", "action", "target_type", "created_at"],
        "search_col": "action",
    },
    "admin_pipeline_runs": {
        "schema": "canopysense",
        "table": "admin_pipeline_runs",
        "display": "Pipeline Runs",
        "columns": [
            "id", "run_id", "actor_id", "mode", "company_id", "estate_id", "afdeling_id",
            "status", "date_start", "date_end", "sanitized_error", "exit_code",
            "started_at", "finished_at", "created_at",
        ],
        "geometry_cols": [],
        "json_cols": [],
        "default_sort": "id",
        "sort_allowed": ["id", "status", "mode", "created_at"],
        "search_col": "status",
    },
    "admin_pipeline_schedules": {
        "schema": "canopysense",
        "table": "admin_pipeline_schedules",
        "display": "Pipeline Schedules",
        "columns": [
            "id", "created_by", "mode", "company_id", "estate_id", "afdeling_id",
            "cadence", "timezone", "date_start", "date_end", "enabled",
            "next_run", "last_run", "created_at", "updated_at",
        ],
        "geometry_cols": [],
        "json_cols": [],
        "default_sort": "id",
        "sort_allowed": ["id", "mode", "cadence", "enabled", "next_run", "created_at"],
        "search_col": None,
    },
    "estates": {
        "schema": "canopysense",
        "table": "estates",
        "display": "Estates",
        "columns": ["id", "company_id", "name", "code", "geometry", "area_ha", "is_valid", "created_at", "updated_at"],
        "geometry_cols": ["geometry"],
        "json_cols": [],
        "default_sort": "id",
        "sort_allowed": ["id", "name", "code", "area_ha", "created_at"],
        "search_col": "name",
    },
    "afdelings": {
        "schema": "canopysense",
        "table": "afdelings",
        "display": "Afdelings",
        "columns": ["id", "estate_id", "company_id", "name", "code", "geometry"],
        "geometry_cols": ["geometry"],
        "json_cols": [],
        "default_sort": "id",
        "sort_allowed": ["id", "name", "code", "estate_id"],
        "search_col": "name",
    },
    "blocks": {
        "schema": "canopysense",
        "table": "blocks",
        "display": "Blocks",
        "columns": ["id", "afdeling_id", "company_id", "name", "code", "plant_year", "clone_type", "area_ha"],
        "geometry_cols": [],
        "json_cols": [],
        "default_sort": "id",
        "sort_allowed": ["id", "name", "code", "afdeling_id", "plant_year"],
        "search_col": "name",
    },
    "satellite_data": {
        "schema": "canopysense",
        "table": "satellite_data",
        "display": "Satellite Data",
        "columns": [
            "id", "block_id", "acquisition_date", "sensor", "cloud_cover",
            "ndvi", "evi", "ndre", "savi", "gndvi", "features", "created_at",
        ],
        "geometry_cols": [],
        "json_cols": ["features"],
        "default_sort": "id",
        "sort_allowed": ["id", "block_id", "acquisition_date", "sensor"],
        "search_col": None,
    },
    "patcher_run_log": {
        "schema": "canopysense",
        "table": "patcher_run_log",
        "display": "Patcher Run Log",
        "columns": [
            "id", "run_id", "trigger_mode", "afdeling_id", "block_id",
            "batch_fingerprint", "status", "rows_inserted", "error_detail",
            "api_version", "started_at", "triggered_at",
        ],
        "geometry_cols": [],
        "json_cols": [],
        "default_sort": "id",
        "sort_allowed": ["id", "status", "trigger_mode", "triggered_at"],
        "search_col": "status",
    },
}


def _get_entry(table_id: str) -> dict:
    entry = TABLE_ALLOWLIST.get(table_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Table '{table_id}' not found")
    return entry


def _serialize_value(v):
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, bytes):
        return v.hex()
    return v


def _serialize_row(row) -> dict:
    return {k: _serialize_value(v) for k, v in dict(row).items()}


def _build_select(entry: dict) -> str:
    """Build SELECT clause from allowlist — no client input reaches identifier positions."""
    parts = []
    for col in entry["columns"]:
        if col in entry["geometry_cols"]:
            parts.append(f"LEFT(ST_AsText({col}), 200) AS {col}")
        elif col in entry["json_cols"]:
            parts.append(f"LEFT({col}::text, 300) AS {col}")
        else:
            parts.append(col)
    return ", ".join(parts)


@router.get("/catalog")
async def catalog(
    admin=Depends(get_current_super_admin),
):
    tables = [
        {"id": tid, "display": e["display"], "schema": e["schema"], "table": e["table"]}
        for tid, e in TABLE_ALLOWLIST.items()
    ]
    return {"tables": tables}


@router.get("/{table_id}/columns")
async def get_columns(
    table_id: str,
    admin=Depends(get_current_super_admin),
):
    entry = _get_entry(table_id)
    cols = [
        {
            "name": c,
            "is_geometry": c in entry["geometry_cols"],
            "is_json_summary": c in entry["json_cols"],
        }
        for c in entry["columns"]
    ]
    return {
        "table_id": table_id,
        "display": entry["display"],
        "search_col": entry.get("search_col"),
        "sort_allowed": entry["sort_allowed"],
        "columns": cols,
    }


@router.get("/{table_id}/rows")
async def get_rows(
    table_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    sort_col: str = Query(default=""),
    sort_dir: str = Query(default="DESC"),
    filter_col: str = Query(default=""),
    filter_val: str = Query(default=""),
    admin=Depends(get_current_super_admin),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    entry = _get_entry(table_id)

    # Sort identifiers come from server-side allowlist only
    effective_sort = sort_col if sort_col in entry["sort_allowed"] else entry["default_sort"]
    effective_dir = "DESC" if sort_dir.upper() == "DESC" else "ASC"

    # Filter column must match the table's designated search column
    params: list = []
    where_sql = ""
    if filter_col and filter_val:
        allowed_search = entry.get("search_col")
        if not allowed_search or filter_col != allowed_search:
            raise HTTPException(
                status_code=422,
                detail=f"Filtering on '{filter_col}' is not allowed for this table",
            )
        params.append(f"%{filter_val}%")
        where_sql = f"WHERE {filter_col} ILIKE ${len(params)}"

    fqt = f"{entry['schema']}.{entry['table']}"
    select_expr = _build_select(entry)
    offset = (page - 1) * page_size

    async with pool.acquire() as conn:
        total = await conn.fetchval(f"SELECT COUNT(*) FROM {fqt} {where_sql}", *params)

        data_rows = await conn.fetch(
            f"""
            SELECT {select_expr}
            FROM {fqt}
            {where_sql}
            ORDER BY {effective_sort} {effective_dir}
            LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}
            """,
            *params, page_size, offset,
        )

        await log_admin_action(
            conn,
            admin["id"],
            "data_viewer_table_view",
            table_id,
            None,
            {"page": page, "page_size": page_size, "filter_col": filter_col or None},
        )

    return {
        "table_id": table_id,
        "display": entry["display"],
        "total": total,
        "page": page,
        "page_size": page_size,
        "columns": entry["columns"],
        "rows": [_serialize_row(r) for r in data_rows],
    }

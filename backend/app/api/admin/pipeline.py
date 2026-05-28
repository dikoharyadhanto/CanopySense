"""
pipeline.py — Admin pipeline trigger, run history, and schedule endpoints.

Permission model:
  - Admin + Super-admin: POST /trigger, GET /runs, GET /runs/{id}, GET /schedules
  - Super-admin only:    POST /schedules, PATCH /schedules/{id}
  - Manager:            403 on all routes (enforced by get_current_admin dep)
"""
from __future__ import annotations

import json
import uuid as uuid_lib
from datetime import datetime, timezone, timedelta
from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_current_admin, get_current_super_admin
from app.api.admin.audit_log import log_admin_action
from app.database import get_db_pool
from app.services.pipeline_dispatcher import (
    validate_trigger_request,
    validate_date_window,
    check_concurrency,
    create_run_record,
    dispatch_trigger,
    ALLOWED_MODES,
    ALLOWED_CADENCES,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class TriggerRequest(BaseModel):
    mode: str
    company_id: int
    estate_id: int
    afdeling_id: Optional[int] = None
    date_start: Optional[str] = None
    date_end: Optional[str] = None


class ScheduleCreate(BaseModel):
    mode: str
    company_id: int
    estate_id: int
    afdeling_id: Optional[int] = None
    cadence: str
    timezone: str = "UTC"
    date_start: Optional[str] = None
    date_end: Optional[str] = None
    first_run_at: Optional[datetime] = None


class ScheduleUpdate(BaseModel):
    enabled: Optional[bool] = None
    cadence: Optional[str] = None
    timezone: Optional[str] = None
    date_start: Optional[str] = None
    date_end: Optional[str] = None


# ---------------------------------------------------------------------------
# Scope lookup helpers
# ---------------------------------------------------------------------------

@router.get("/scopes/estates")
async def list_estates_for_company(
    company_id: int,
    user: dict = Depends(get_current_admin),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    """Return estates belonging to a company (used by trigger form scope selector)."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, name, code FROM canopysense.estates WHERE company_id=$1 ORDER BY name",
            company_id,
        )
    return {"items": [dict(r) for r in rows]}


@router.get("/scopes/afdelings")
async def list_afdelings_for_estate(
    estate_id: int,
    user: dict = Depends(get_current_admin),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    """Return afdelings belonging to an estate (used by trigger form scope selector)."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, name, code FROM canopysense.afdelings WHERE estate_id=$1 ORDER BY name",
            estate_id,
        )
    return {"items": [dict(r) for r in rows]}


# ---------------------------------------------------------------------------
# Trigger
# ---------------------------------------------------------------------------

@router.post("/trigger")
async def trigger_pipeline(
    req: TriggerRequest,
    user: dict = Depends(get_current_admin),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    error, status_code = await validate_trigger_request(
        pool, req.mode, req.company_id, req.estate_id,
        req.afdeling_id, req.date_start, req.date_end,
    )
    if error:
        raise HTTPException(status_code=status_code, detail=error)

    if await check_concurrency(pool, req.mode, req.company_id, req.estate_id, req.afdeling_id):
        raise HTTPException(status_code=409, detail="A run for this scope is already in progress.")

    run_id = await create_run_record(
        pool, user["id"], req.mode, req.company_id,
        req.estate_id, req.afdeling_id, req.date_start, req.date_end,
    )

    async with pool.acquire() as conn:
        await log_admin_action(
            conn, user["id"], "pipeline_trigger", "pipeline_run", None,
            {"run_id": run_id, "mode": req.mode,
             "company_id": req.company_id, "estate_id": req.estate_id},
        )

    await dispatch_trigger(
        pool, run_id, req.mode,
        req.estate_id, req.afdeling_id, req.date_start, req.date_end,
    )

    return {"run_id": run_id, "status": "accepted"}


# ---------------------------------------------------------------------------
# Run history
# ---------------------------------------------------------------------------

@router.get("/runs")
async def list_runs(
    page: int = 1,
    page_size: int = 20,
    user: dict = Depends(get_current_admin),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    page_size = min(max(1, page_size), 100)
    offset = (page - 1) * page_size
    is_super = user["is_global_admin"]

    async with pool.acquire() as conn:
        if is_super:
            rows = await conn.fetch(
                """SELECT r.id, r.run_id, r.mode, r.company_id, r.estate_id, r.afdeling_id,
                          r.status, r.date_start, r.date_end, r.exit_code,
                          r.sanitized_error, r.started_at, r.finished_at, r.created_at,
                          u.username AS actor_username
                   FROM admin_pipeline_runs r
                   JOIN users u ON r.actor_id = u.id
                   ORDER BY r.created_at DESC
                   LIMIT $1 OFFSET $2""",
                page_size, offset,
            )
            total = await conn.fetchval("SELECT COUNT(*) FROM admin_pipeline_runs")
        else:
            rows = await conn.fetch(
                """SELECT r.id, r.run_id, r.mode, r.company_id, r.estate_id, r.afdeling_id,
                          r.status, r.date_start, r.date_end, r.exit_code,
                          r.sanitized_error, r.started_at, r.finished_at, r.created_at,
                          u.username AS actor_username
                   FROM admin_pipeline_runs r
                   JOIN users u ON r.actor_id = u.id
                   WHERE r.actor_id = $3
                   ORDER BY r.created_at DESC
                   LIMIT $1 OFFSET $2""",
                page_size, offset, user["id"],
            )
            total = await conn.fetchval(
                "SELECT COUNT(*) FROM admin_pipeline_runs WHERE actor_id=$1",
                user["id"],
            )

    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/runs/{run_id}")
async def get_run(
    run_id: str,
    user: dict = Depends(get_current_admin),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    try:
        run_uuid = uuid_lib.UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run_id format")

    is_super = user["is_global_admin"]

    async with pool.acquire() as conn:
        if is_super:
            run = await conn.fetchrow(
                """SELECT r.*, u.username AS actor_username
                   FROM admin_pipeline_runs r
                   JOIN users u ON r.actor_id = u.id
                   WHERE r.run_id = $1""",
                run_uuid,
            )
        else:
            run = await conn.fetchrow(
                """SELECT r.*, u.username AS actor_username
                   FROM admin_pipeline_runs r
                   JOIN users u ON r.actor_id = u.id
                   WHERE r.run_id = $1 AND r.actor_id = $2""",
                run_uuid, user["id"],
            )

        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")

        batches = await conn.fetch(
            """SELECT id, trigger_mode, afdeling_id, block_id, status,
                      rows_inserted, api_version, triggered_at, started_at,
                      estate_id, date_start, date_end
               FROM canopysense.patcher_run_log
               WHERE run_id = $1
               ORDER BY id""",
            run_uuid,
        )

    return {"run": dict(run), "batches": [dict(b) for b in batches]}


# ---------------------------------------------------------------------------
# Schedules
# ---------------------------------------------------------------------------

@router.get("/schedules")
async def list_schedules(
    user: dict = Depends(get_current_admin),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT s.*, u.username AS created_by_username
               FROM admin_pipeline_schedules s
               JOIN users u ON s.created_by = u.id
               ORDER BY s.created_at DESC"""
        )
    return {"items": [dict(r) for r in rows]}


@router.post("/schedules")
async def create_schedule(
    req: ScheduleCreate,
    user: dict = Depends(get_current_super_admin),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    if req.mode not in ALLOWED_MODES:
        raise HTTPException(
            status_code=400,
            detail=f"mode must be one of: {', '.join(sorted(ALLOWED_MODES))}",
        )
    if req.cadence not in ALLOWED_CADENCES:
        raise HTTPException(
            status_code=400,
            detail=f"cadence must be one of: {', '.join(sorted(ALLOWED_CADENCES))}",
        )

    error, status_code = await validate_trigger_request(
        pool, req.mode, req.company_id, req.estate_id,
        req.afdeling_id, req.date_start, req.date_end,
    )
    if error:
        raise HTTPException(status_code=status_code, detail=error)

    first_run = req.first_run_at or (datetime.now(timezone.utc) + timedelta(hours=1))

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO admin_pipeline_schedules
               (created_by, mode, company_id, estate_id, afdeling_id, cadence,
                timezone, date_start, date_end, enabled, next_run, created_at, updated_at)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,TRUE,$10,NOW(),NOW())
               RETURNING id""",
            user["id"], req.mode, req.company_id, req.estate_id, req.afdeling_id,
            req.cadence, req.timezone, req.date_start, req.date_end, first_run,
        )
        await log_admin_action(
            conn, user["id"], "schedule_create", "pipeline_schedule", row["id"],
            {"mode": req.mode, "cadence": req.cadence, "company_id": req.company_id},
        )

    return {"id": row["id"], "status": "created"}


@router.patch("/schedules/{schedule_id}")
async def update_schedule(
    schedule_id: int,
    req: ScheduleUpdate,
    user: dict = Depends(get_current_super_admin),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT id, mode, date_start, date_end FROM admin_pipeline_schedules WHERE id=$1",
            schedule_id,
        )
        if existing is None:
            raise HTTPException(status_code=404, detail="Schedule not found")

    updates: dict = {}
    if req.enabled is not None:
        updates["enabled"] = req.enabled
    if req.cadence is not None:
        if req.cadence not in ALLOWED_CADENCES:
            raise HTTPException(
                status_code=400,
                detail=f"cadence must be one of: {', '.join(sorted(ALLOWED_CADENCES))}",
            )
        updates["cadence"] = req.cadence
    if req.timezone is not None:
        updates["timezone"] = req.timezone
    if req.date_start is not None:
        updates["date_start"] = req.date_start
    if req.date_end is not None:
        updates["date_end"] = req.date_end

    if not updates:
        return {"id": schedule_id, "status": "no_change"}

    # Validate merged date window if any date field is being patched
    if "date_start" in updates or "date_end" in updates:
        merged_start = updates.get("date_start", existing["date_start"])
        merged_end = updates.get("date_end", existing["date_end"])
        err, err_status = validate_date_window(existing["mode"], merged_start, merged_end)
        if err:
            raise HTTPException(status_code=err_status, detail=err)

    updates["updated_at"] = datetime.now(timezone.utc)
    set_parts = [f"{k}=${i + 2}" for i, k in enumerate(updates)]
    values = [schedule_id, *updates.values()]

    async with pool.acquire() as conn:
        await conn.execute(
            f"UPDATE admin_pipeline_schedules SET {', '.join(set_parts)} WHERE id=$1",
            *values,
        )
        audit_changes = {k: str(v) for k, v in updates.items() if k != "updated_at"}
        await log_admin_action(
            conn, user["id"], "schedule_update", "pipeline_schedule",
            schedule_id, {"changes": audit_changes},
        )

    return {"id": schedule_id, "status": "updated"}

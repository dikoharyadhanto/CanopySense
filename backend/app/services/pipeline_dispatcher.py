"""
pipeline_dispatcher.py — Safe subprocess dispatch for admin-triggered pipeline runs.

Validates trigger requests, checks concurrency, creates admin_pipeline_runs records,
and launches patcher_local.py as an asyncio subprocess (shell=False, no command injection).
"""
from __future__ import annotations

import asyncio
import logging
import os
import pathlib
import re
import sys
import uuid as uuid_lib
from typing import Optional

import asyncpg

from app.database import settings

logger = logging.getLogger(__name__)

ALLOWED_MODES = frozenset({"scheduled", "backfill"})
ALLOWED_CADENCES = frozenset({"daily", "weekly", "monthly"})
_YM_RE = re.compile(r'^\d{4}-(0[1-9]|1[0-2])$')
MAX_BACKFILL_MONTHS = 48

# Resolved once at module load — never user-supplied
PATCHER_LOCAL_PATH = (
    pathlib.Path(__file__).parent.parent.parent.parent / "src" / "patcher_local.py"
)


def validate_date_window(
    mode: str,
    date_start: Optional[str],
    date_end: Optional[str],
) -> tuple[Optional[str], Optional[int]]:
    """Validate backfill date range only. Returns (error, status) or (None, None)."""
    if mode != "backfill":
        return None, None

    for field, val in [("date_start", date_start), ("date_end", date_end)]:
        if val is None:
            return f"{field} is required for backfill mode", 400
        if not _YM_RE.match(val):
            return f"{field} must be YYYY-MM format", 400

    start_y, start_m = int(date_start[:4]), int(date_start[5:])  # type: ignore[index]
    end_y, end_m = int(date_end[:4]), int(date_end[5:])          # type: ignore[index]
    if (start_y * 12 + start_m) > (end_y * 12 + end_m):
        return "date_start must not be after date_end", 400
    if (end_y * 12 + end_m) - (start_y * 12 + start_m) > MAX_BACKFILL_MONTHS:
        return f"Backfill range exceeds maximum of {MAX_BACKFILL_MONTHS} months", 400

    return None, None


async def validate_trigger_request(
    pool: asyncpg.Pool,
    mode: str,
    company_id: int,
    estate_id: int,
    afdeling_id: Optional[int],
    date_start: Optional[str],
    date_end: Optional[str],
) -> tuple[Optional[str], Optional[int]]:
    """Returns (error_message, http_status) or (None, None) if valid."""
    if mode not in ALLOWED_MODES:
        return f"mode must be one of: {', '.join(sorted(ALLOWED_MODES))}", 400

    async with pool.acquire() as conn:
        estate = await conn.fetchrow(
            "SELECT id FROM canopysense.estates WHERE id = $1 AND company_id = $2",
            estate_id, company_id,
        )
        if estate is None:
            return f"estate_id={estate_id} not found for company_id={company_id}", 400

        if afdeling_id is not None:
            afd = await conn.fetchrow(
                "SELECT id FROM canopysense.afdelings WHERE id = $1 AND estate_id = $2",
                afdeling_id, estate_id,
            )
            if afd is None:
                return f"afdeling_id={afdeling_id} not found for estate_id={estate_id}", 400

    return validate_date_window(mode, date_start, date_end)


async def check_concurrency(
    pool: asyncpg.Pool,
    mode: str,
    company_id: int,
    estate_id: int,
    afdeling_id: Optional[int],
) -> bool:
    """Returns True if a run with matching scope is already running."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT id FROM admin_pipeline_runs
               WHERE status = 'running'
                 AND mode = $1
                 AND company_id = $2
                 AND estate_id = $3
                 AND (afdeling_id = $4 OR afdeling_id IS NULL OR $4 IS NULL)
               LIMIT 1""",
            mode, company_id, estate_id, afdeling_id,
        )
    return row is not None


async def create_run_record(
    pool: asyncpg.Pool,
    actor_id: int,
    mode: str,
    company_id: int,
    estate_id: int,
    afdeling_id: Optional[int],
    date_start: Optional[str],
    date_end: Optional[str],
) -> str:
    """Insert a pending admin_pipeline_runs row. Returns the run_id string."""
    run_id = uuid_lib.uuid4()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO admin_pipeline_runs
               (run_id, actor_id, mode, company_id, estate_id, afdeling_id,
                date_start, date_end, status, created_at)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'pending', NOW())""",
            run_id, actor_id, mode, company_id, estate_id, afdeling_id,
            date_start, date_end,
        )
    return str(run_id)


async def dispatch_trigger(
    pool: asyncpg.Pool,
    run_id: str,
    mode: str,
    estate_id: int,
    afdeling_id: Optional[int],
    date_start: Optional[str],
    date_end: Optional[str],
) -> None:
    """Schedule subprocess launch as a background asyncio task. Returns immediately."""
    args = [sys.executable, str(PATCHER_LOCAL_PATH)]

    if mode == "backfill":
        args.append("--backfill")
        if date_start:
            args += ["--date-start", date_start]
        if date_end:
            args += ["--date-end", date_end]

    if estate_id is not None:
        args += ["--estate-id", str(estate_id)]
    if afdeling_id is not None:
        args += ["--afdeling-id", str(afdeling_id)]

    args += ["--run-id", run_id]

    patcher_env = {
        **os.environ,
        "CLOUD_FUNCTION_URL":        settings.CLOUD_FUNCTION_URL,
        "PATCHER_API_KEY":           settings.PATCHER_API_KEY,
        "CONTRACTOR_ID":             settings.CONTRACTOR_ID,
        "PGHOST":                    settings.PGHOST,
        "PGPORT":                    str(settings.PGPORT),
        "PGUSER":                    settings.PGUSER,
        "PGPASSWORD":                settings.PGPASSWORD,
        "PGDATABASE":                settings.PGDATABASE,
        "PGSCHEMA":                  settings.PGSCHEMA,
        "FUNCTION_TIMEOUT_SECONDS":  str(settings.FUNCTION_TIMEOUT_SECONDS),
        "PATCHER_API_VERSION":       settings.PATCHER_API_VERSION,
    }

    asyncio.create_task(_run_subprocess(pool, run_id, args, patcher_env))


async def _run_subprocess(
    pool: asyncpg.Pool, run_id: str, args: list[str], env: dict[str, str]
) -> None:
    """Background task: run patcher_local subprocess and update run record on finish."""
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE admin_pipeline_runs SET status='running', started_at=NOW() WHERE run_id=$1",
            uuid_lib.UUID(run_id),
        )

    exit_code = -1
    sanitized_error: Optional[str] = None
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr_bytes = await proc.communicate()
        exit_code = proc.returncode or 0
        if exit_code != 0 and stderr_bytes:
            raw = stderr_bytes.decode("utf-8", errors="replace")
            sanitized_error = raw[-500:].strip() or None
    except asyncio.CancelledError:
        logger.warning("Pipeline run %s cancelled", run_id)
        sanitized_error = "Run cancelled (server shutdown)"
        exit_code = -1
    except Exception as exc:
        logger.error("Pipeline subprocess error run_id=%s: %s", run_id, exc)
        sanitized_error = str(exc)[:500]
        exit_code = -1

    status = "succeeded" if exit_code == 0 else "failed"
    async with pool.acquire() as conn:
        await conn.execute(
            """UPDATE admin_pipeline_runs
               SET status=$1, exit_code=$2, sanitized_error=$3, finished_at=NOW()
               WHERE run_id=$4""",
            status, exit_code, sanitized_error, uuid_lib.UUID(run_id),
        )
    logger.info("Pipeline run %s finished status=%s exit_code=%d", run_id, status, exit_code)

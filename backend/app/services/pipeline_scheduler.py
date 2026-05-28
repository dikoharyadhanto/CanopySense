"""
pipeline_scheduler.py — asyncio background loop that fires due pipeline schedules.

Runs inside the FastAPI process at a 60-second tick. Truthful for staging: schedules
execute only while the server is running. Production hand-off to Cloud Scheduler or
system cron is Stage 1.13 scope.
"""
from __future__ import annotations

import asyncio
import logging
import uuid as uuid_lib
from datetime import datetime, timezone, timedelta
from typing import Optional

import asyncpg

from app.services.pipeline_dispatcher import (
    check_concurrency,
    create_run_record,
    dispatch_trigger,
)

logger = logging.getLogger(__name__)

_TICK_SECONDS = 60


def _next_run_after(cadence: str, from_time: datetime) -> datetime:
    if cadence == "weekly":
        return from_time + timedelta(weeks=1)
    if cadence == "monthly":
        month = from_time.month % 12 + 1
        year = from_time.year + (1 if from_time.month == 12 else 0)
        try:
            return from_time.replace(year=year, month=month)
        except ValueError:
            # Handle e.g. Jan 31 → Feb 28
            import calendar
            last_day = calendar.monthrange(year, month)[1]
            return from_time.replace(year=year, month=month, day=last_day)
    # default: daily
    return from_time + timedelta(days=1)


async def run_scheduler_loop(pool: asyncpg.Pool) -> None:
    logger.info("Pipeline scheduler started (tick=%ds)", _TICK_SECONDS)
    while True:
        try:
            await asyncio.sleep(_TICK_SECONDS)
            await _fire_due_schedules(pool)
        except asyncio.CancelledError:
            logger.info("Pipeline scheduler stopped")
            break
        except Exception as exc:
            logger.error("Scheduler loop error: %s", exc, exc_info=True)


async def _fire_due_schedules(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        schedules = await conn.fetch(
            """SELECT id, created_by, mode, company_id, estate_id, afdeling_id,
                      cadence, date_start, date_end
               FROM admin_pipeline_schedules
               WHERE enabled = TRUE AND next_run <= NOW()"""
        )

    for sched in schedules:
        sched_id: int = sched["id"]
        try:
            if await check_concurrency(
                pool, sched["mode"], sched["company_id"],
                sched["estate_id"], sched["afdeling_id"],
            ):
                logger.info("Schedule %d skipped — conflicting run in progress", sched_id)
                _advance_next_run(pool, sched_id, sched["cadence"])
                continue

            run_id = await create_run_record(
                pool, sched["created_by"], sched["mode"],
                sched["company_id"], sched["estate_id"], sched["afdeling_id"],
                sched["date_start"], sched["date_end"],
            )

            await dispatch_trigger(
                pool, run_id, sched["mode"],
                sched["estate_id"], sched["afdeling_id"],
                sched["date_start"], sched["date_end"],
            )

            next_run = _next_run_after(sched["cadence"], datetime.now(timezone.utc))
            async with pool.acquire() as conn:
                await conn.execute(
                    """UPDATE admin_pipeline_schedules
                       SET last_run=NOW(),
                           last_admin_run_id=(
                               SELECT id FROM admin_pipeline_runs
                               WHERE run_id=$1 LIMIT 1
                           ),
                           next_run=$2
                       WHERE id=$3""",
                    uuid_lib.UUID(run_id), next_run, sched_id,
                )
            logger.info("Schedule %d fired → run_id=%s next_run=%s", sched_id, run_id, next_run)

        except Exception as exc:
            logger.error("Failed to fire schedule %d: %s", sched_id, exc)


def _advance_next_run(pool: asyncpg.Pool, sched_id: int, cadence: str) -> None:
    """Fire-and-forget: advance next_run for a skipped schedule."""
    async def _do():
        next_run = _next_run_after(cadence, datetime.now(timezone.utc))
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE admin_pipeline_schedules SET next_run=$1 WHERE id=$2",
                next_run, sched_id,
            )
    asyncio.create_task(_do())

from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from app.api.deps import get_current_admin
from app.api.admin.audit_log import log_admin_action
from app.database import get_db_pool
import asyncpg
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

VALID_TIERS = {"basic", "premium"}
VALID_STATUSES = {"trialing", "active", "past_due", "cancelled", "expired"}
VALID_RASTER_MODES = {"gee_mapid", "maps_platform"}
VALID_BILLING_INTERVALS = {"monthly", "yearly", "fixed_period", None}


class SubscriptionUpdate(BaseModel):
    tier: Optional[str] = None
    status: Optional[str] = None
    billing_interval: Optional[str] = None
    subscription_starts_at: Optional[date] = None
    subscription_ends_at: Optional[date] = None
    timelapse_enabled: Optional[bool] = None
    timelapse_period_months: Optional[int] = None
    raster_serving_mode: Optional[str] = None


@router.get("/{company_id}")
async def get_subscription(
    company_id: int,
    admin=Depends(get_current_admin),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM company_subscriptions WHERE company_id = $1", company_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Subscription not found")
    return dict(row)


@router.patch("/{company_id}")
async def update_subscription(
    company_id: int,
    body: SubscriptionUpdate,
    admin=Depends(get_current_admin),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    if body.tier is not None and body.tier not in VALID_TIERS:
        raise HTTPException(status_code=422, detail=f"Invalid tier. Allowed: {VALID_TIERS}")
    if body.status is not None and body.status not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail=f"Invalid status. Allowed: {VALID_STATUSES}")
    if body.raster_serving_mode is not None and body.raster_serving_mode not in VALID_RASTER_MODES:
        raise HTTPException(status_code=422, detail=f"Invalid raster_serving_mode. Allowed: {VALID_RASTER_MODES}")

    async with pool.acquire() as conn:
        existing = await conn.fetchval(
            "SELECT id FROM company_subscriptions WHERE company_id = $1", company_id
        )
        if not existing:
            raise HTTPException(status_code=404, detail="Subscription not found")

        updates = []
        params: list = []
        idx = 1
        for field in (
            "tier", "status", "billing_interval",
            "timelapse_enabled", "timelapse_period_months", "raster_serving_mode",
        ):
            val = getattr(body, field)
            if val is not None:
                updates.append(f"{field} = ${idx}")
                params.append(val)
                idx += 1

        for field in ("subscription_starts_at", "subscription_ends_at"):
            val = getattr(body, field)
            if val is not None:
                updates.append(f"{field} = ${idx}")
                params.append(val)
                idx += 1

        if not updates:
            raise HTTPException(status_code=422, detail="No fields to update")

        updates.append(f"updated_at = NOW()")
        params.append(company_id)
        sql = f"UPDATE company_subscriptions SET {', '.join(updates)} WHERE company_id = ${idx} RETURNING *"
        row = await conn.fetchrow(sql, *params)

        await log_admin_action(conn, admin["id"], "update_subscription", "company", company_id,
                               body.model_dump(mode='json', exclude_none=True))
    return dict(row)

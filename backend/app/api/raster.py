"""
Raster endpoints — subscription-aware GEE tile routing via Cloud Function [v1.9].

GET /api/raster/frames
  Returns available timelapse frames for Premium users.
  Frame dates sourced from satellite_data (quality-gated by patcher pipeline).
  Only acquisition dates with valid data for the requested index are returned.
  Premium-only. Basic users receive 403.

GET /api/raster/metadata
  Reads company_subscriptions from DB for the current user's company.
  Routes to gee_mapid (basic) or maps_platform (premium) serving mode.
  Delegates actual GEE credential access to Cloud Function via HTTP.
  Accepts frame_id (ISO date) for timelapse frame selection — converts to
  exact 1-day GEE window. date_start/date_end retained for backward compat.
  Returns RasterMetadata JSON contract for Explore Map UI consumption.

Backend is the sole authority for subscription routing.
JWT values are used only for user identity; billing tier always comes from DB.
GEE service account remains in Secret Manager; FastAPI never holds it.
"""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
import asyncpg

from app.api.deps import get_current_user
from app.api.raster_cache import build_cache_key, get_cached_metadata, set_cached_metadata
from app.database import get_db_pool, get_redis, settings

logger = logging.getLogger(__name__)

router = APIRouter()

_SUPPORTED_INDICES: tuple[str, ...] = ("ndvi", "evi", "savi", "gndvi", "ndre")


class BoundsModel(BaseModel):
    west: float
    south: float
    east: float
    north: float


class RasterMetadataResponse(BaseModel):
    schema_version: str
    serving_mode: str
    subscription_tier: str
    index: str
    sensor: str
    date_acquired: str
    date_window_start: str
    date_window_end: str
    valid_pixel_ratio: float
    low_quality: bool
    bounds: BoundsModel
    resolution_m: int
    palette: list[str]
    viz_min: float
    viz_max: float
    tile_url_format: str
    tile_url_expires_note: str
    cloud_nodata_note: str
    generated_at_utc: str


class RasterFrameItem(BaseModel):
    frame_id: str   # "YYYY-MM-DD" — actual acquisition date from satellite_data
    label: str      # "14 Oct 2026"
    sensor: str     # "S2", "L8", "L9"


class RasterFrameListResponse(BaseModel):
    frames: list[RasterFrameItem]
    default_frame_id: Optional[str]
    total_frames: int


class _SubscriptionDateError(Exception):
    pass


def _resolve_date_window(
    serving_mode: str,
    subscription_tier: str,
    timelapse_period_months: int | None,
    date_start: str | None,
    date_end: str | None,
) -> tuple[str, str]:
    """Resolve raster search window for cache key. Raises _SubscriptionDateError if out of range."""
    today = date.today()

    if serving_mode == "gee_mapid" or subscription_tier == "basic":
        end = today
        start = today - timedelta(days=7)
        return start.isoformat(), end.isoformat()

    end_date = date.fromisoformat(date_end) if date_end else today
    start_date = date.fromisoformat(date_start) if date_start else end_date - timedelta(days=7)

    if timelapse_period_months is not None:
        earliest_allowed = today - timedelta(days=timelapse_period_months * 30)
        if start_date < earliest_allowed:
            raise _SubscriptionDateError(
                f"Requested start date {start_date.isoformat()} is outside the allowed timelapse "
                f"window of {timelapse_period_months} months. "
                f"Earliest allowed: {earliest_allowed.isoformat()}."
            )

    return start_date.isoformat(), end_date.isoformat()


@router.get("/raster/frames", response_model=RasterFrameListResponse)
async def get_raster_frames(
    index: str = Query(default="ndvi", description="Vegetation index: ndvi, evi, savi, gndvi, ndre"),
    current_user: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    """
    Return available timelapse frame dates for the current user's company estate.

    Frames are sourced from satellite_data (quality-gated by patcher pipeline).
    Only acquisition dates with valid data for the requested index are returned.
    Premium-only. Basic users receive 403.
    """
    company_id: int = current_user.get("company_id")
    if company_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not associated with a company.",
        )

    async with pool.acquire() as conn:
        sub = await conn.fetchrow(
            """
            SELECT tier, status, timelapse_enabled, timelapse_period_months
            FROM company_subscriptions
            WHERE company_id = $1
            """,
            company_id,
        )

    if sub is None:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="No active subscription found for your company. Contact your account manager.",
        )

    if sub["status"] not in ("active", "trialing"):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Subscription is not active (status: {sub['status']}). Contact your account manager.",
        )

    if sub["tier"] != "premium" or not sub["timelapse_enabled"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Timelapse is a Premium feature. Upgrade your subscription to access frame history.",
        )

    if index not in _SUPPORTED_INDICES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported index: {index!r}. Supported: {_SUPPORTED_INDICES}",
        )

    timelapse_period_months: int = sub["timelapse_period_months"] or 12
    lookback_start = date.today() - timedelta(days=timelapse_period_months * 30)

    # index is whitelisted against _SUPPORTED_INDICES — safe for column name interpolation
    query = f"""
        SELECT sd.acquisition_date,
               MIN(sd.sensor)      AS sensor,
               AVG(sd.cloud_cover) AS cloud_cover_avg
        FROM canopysense.satellite_data sd
        JOIN canopysense.blocks b ON sd.block_id = b.id
        WHERE b.company_id = $1
          AND sd.acquisition_date >= $2
          AND sd.{index} IS NOT NULL
        GROUP BY sd.acquisition_date
        ORDER BY sd.acquisition_date DESC
    """

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, company_id, lookback_start)

    frames = []
    for row in rows:
        frame_date = row["acquisition_date"]
        label = f"{frame_date.day} {frame_date.strftime('%b %Y')}"
        frames.append(
            RasterFrameItem(
                frame_id=frame_date.isoformat(),
                label=label,
                sensor=row["sensor"] or "unknown",
            )
        )

    return RasterFrameListResponse(
        frames=frames,
        default_frame_id=frames[0].frame_id if frames else None,
        total_frames=len(frames),
    )


@router.get("/raster/metadata", response_model=RasterMetadataResponse)
async def get_raster_metadata(
    index: str = Query(default="ndvi", description="Vegetation index: ndvi, evi, savi, gndvi, ndre"),
    date_start: Optional[str] = Query(default=None, description="ISO date — premium timelapse start (ignored for basic)"),
    date_end: Optional[str] = Query(default=None, description="ISO date — premium timelapse end (ignored for basic)"),
    frame_id: Optional[str] = Query(default=None, description="ISO date YYYY-MM-DD — timelapse frame selection (takes precedence over date_start/date_end)"),
    current_user: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    """
    Return raster tile metadata for the current user's company estate.

    Subscription tier is read from DB (company_subscriptions) on each request.
    JWT is used only for user identity — subscription routing is never trusted from JWT.
    GEE credentials are accessed via Cloud Function → Secret Manager only.
    """
    company_id: int = current_user.get("company_id")
    if company_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not associated with a company.",
        )

    # Re-read subscription from DB on each request — backend is the authority
    async with pool.acquire() as conn:
        sub = await conn.fetchrow(
            """
            SELECT tier, status, timelapse_enabled, timelapse_period_months, raster_serving_mode
            FROM company_subscriptions
            WHERE company_id = $1
            """,
            company_id,
        )

    if sub is None:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="No active subscription found for your company. Contact your account manager.",
        )

    if sub["status"] not in ("active", "trialing"):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Subscription is not active (status: {sub['status']}). Contact your account manager.",
        )

    subscription_tier: str = sub["tier"]
    serving_mode: str = sub["raster_serving_mode"]
    timelapse_period_months: int | None = sub["timelapse_period_months"]

    # Fetch AOI from estate blocks for this company
    async with pool.acquire() as conn:
        aoi_row = await conn.fetchrow(
            """
            SELECT ST_AsGeoJSON(ST_Union(b.geometry)) AS aoi_geojson
            FROM canopysense.blocks b
            WHERE b.company_id = $1
            """,
            company_id,
        )

    if aoi_row is None or aoi_row["aoi_geojson"] is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No estate blocks found for your company.",
        )

    aoi_geojson = json.loads(aoi_row["aoi_geojson"])

    if index not in _SUPPORTED_INDICES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported index: {index!r}. Supported: {_SUPPORTED_INDICES}",
        )

    # frame_id takes precedence: convert to exact 1-day GEE window
    # GEE filterDate() is exclusive on the end date, so date_end = frame_date + 1 day
    if frame_id is not None:
        try:
            frame_date = date.fromisoformat(frame_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid frame_id: {frame_id!r}. Expected ISO date YYYY-MM-DD.",
            )
        date_start = frame_date.isoformat()
        date_end = (frame_date + timedelta(days=1)).isoformat()

    # Resolve date window for cache key; validates premium date range before hitting CF
    try:
        resolved_start, resolved_end = _resolve_date_window(
            serving_mode=serving_mode,
            subscription_tier=subscription_tier,
            timelapse_period_months=timelapse_period_months,
            date_start=date_start,
            date_end=date_end,
        )
    except _SubscriptionDateError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))

    # Check company-scoped raster cache
    redis = await get_redis()
    cache_key = build_cache_key(
        company_id=company_id,
        index=index,
        date_start=resolved_start,
        date_end=resolved_end,
        serving_mode=serving_mode,
        frame_id=frame_id,
    )
    cached = await get_cached_metadata(redis, cache_key)
    if cached is not None:
        return cached

    cf_url = settings.CLOUD_FUNCTION_URL
    cf_key = settings.PATCHER_API_KEY
    if not cf_url or not cf_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Raster service is not configured. Contact your administrator.",
        )

    cf_payload = {
        "mode": "raster_metadata",
        "aoi_geojson": aoi_geojson,
        "index": index,
        "serving_mode": serving_mode,
        "subscription_tier": subscription_tier,
        "timelapse_period_months": timelapse_period_months,
        "date_start": date_start,
        "date_end": date_end,
    }

    try:
        async with httpx.AsyncClient(timeout=float(settings.RASTER_CLOUD_TIMEOUT_SECONDS)) as client:
            cf_response = await client.post(
                cf_url,
                json=cf_payload,
                headers={"X-API-Key": cf_key},
            )
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Raster service timed out. Try again later.",
        )
    except httpx.RequestError as exc:
        logger.error("Cloud Function request error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Raster service is unavailable. Try again later.",
        )

    if cf_response.status_code == 200:
        cf_data = cf_response.json()
        metadata_dict = cf_data.get("metadata", {})
    elif cf_response.status_code == 403:
        cf_data = cf_response.json()
        error_detail = cf_data.get("error", "Access denied.")
        # Strip CF status prefix before surfacing to client
        if ": " in error_detail:
            error_detail = error_detail.split(": ", 1)[1].strip()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_detail)
    else:
        cf_data = cf_response.json()
        logger.error(
            "Cloud Function raster error %s: %s",
            cf_response.status_code,
            cf_data.get("error", ""),
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Raster service is unavailable. Try again later.",
        )

    await set_cached_metadata(redis, cache_key, metadata_dict, settings.RASTER_CACHE_TTL_SECONDS)
    return metadata_dict

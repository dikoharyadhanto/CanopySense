"""
Raster metadata endpoint — subscription-aware GEE tile routing [v1.6].

GET /api/raster/metadata
  Reads company_subscriptions from DB for the current user's company.
  Routes to gee_mapid (basic) or maps_platform (premium) serving mode.
  Returns RasterMetadata JSON contract for v1.7 Explore Map UI consumption.

Backend is the sole authority for subscription routing.
JWT values are used only for user identity; billing tier always comes from DB.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
import asyncpg

from app.api.deps import get_current_user
from app.api.raster_cache import build_cache_key, get_cached_metadata, set_cached_metadata
from app.database import get_db_pool, get_redis, settings

logger = logging.getLogger(__name__)

router = APIRouter()


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


@router.get("/raster/metadata", response_model=RasterMetadataResponse)
async def get_raster_metadata(
    index: str = Query(default="ndvi", description="Vegetation index: ndvi, evi, savi, gndvi, ndre"),
    date_start: Optional[str] = Query(default=None, description="ISO date — premium timelapse start (ignored for basic)"),
    date_end: Optional[str] = Query(default=None, description="ISO date — premium timelapse end (ignored for basic)"),
    current_user: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    """
    Return raster tile metadata for the current user's company estate.

    Subscription tier is read from DB (company_subscriptions) on each request.
    JWT is used only for user identity — subscription routing is never trusted from JWT.

    Basic tier: always returns latest 7-day scene; date params ignored.
    Premium tier: accepts date window within timelapse_period_months.
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
    # blocks.company_id is a direct FK — no join through estates needed
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

    # Import raster engine (deferred — avoids ee.* at module load time)
    _add_src_to_path()
    try:
        from raster_engine import (
            generate_metadata,
            RasterEngineError,
            SubscriptionAccessError,
            SUPPORTED_INDICES,
        )
    except ImportError as exc:
        logger.error("raster_engine import failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Raster engine is not available. Check server configuration.",
        )

    if index not in SUPPORTED_INDICES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported index: {index!r}. Supported: {SUPPORTED_INDICES}",
        )

    # Resolve date window first (needed for cache key) — subscription validation inside engine
    from raster_engine import _resolve_date_window, SubscriptionAccessError as _SAE
    try:
        resolved_start, resolved_end = _resolve_date_window(
            serving_mode=serving_mode,
            subscription_tier=subscription_tier,
            timelapse_period_months=timelapse_period_months,
            date_start=date_start,
            date_end=date_end,
        )
    except _SAE as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))

    # Check company-scoped raster cache (TC-024)
    redis = await get_redis()
    cache_key = build_cache_key(
        company_id=company_id,
        index=index,
        date_start=resolved_start,
        date_end=resolved_end,
        serving_mode=serving_mode,
    )
    cached = await get_cached_metadata(redis, cache_key)
    if cached is not None:
        return cached

    try:
        metadata = generate_metadata(
            index=index,
            serving_mode=serving_mode,
            subscription_tier=subscription_tier,
            timelapse_period_months=timelapse_period_months,
            aoi_geojson=aoi_geojson,
            date_start=date_start,
            date_end=date_end,
        )
    except SubscriptionAccessError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        )
    except RasterEngineError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )

    metadata_dict = metadata.to_dict()
    await set_cached_metadata(redis, cache_key, metadata_dict, settings.RASTER_CACHE_TTL_SECONDS)
    return metadata_dict


def _add_src_to_path() -> None:
    """Ensure src/ directory is on sys.path for raster_engine import.

    Tries 4 parents (host: backend/app/api/raster.py → repo root → src/)
    then 3 parents (Docker: /app/app/api/raster.py → /app → /app/src via volume mount).
    """
    import pathlib
    here = pathlib.Path(__file__).resolve()
    for n_parents in (4, 3):
        candidate = here
        for _ in range(n_parents):
            candidate = candidate.parent
        src_dir = candidate / "src"
        if src_dir.is_dir():
            src_str = str(src_dir)
            if src_str not in sys.path:
                sys.path.insert(0, src_str)
            return
    logger.warning("src/ not found relative to %s; raster_engine import will fail", __file__)

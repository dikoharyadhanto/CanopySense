"""
Company-scoped raster metadata cache [v1.6 — TASK-014].

Stores and retrieves RasterMetadata JSON in Redis, keyed by:
  company_id + index + date_start + date_end + serving_mode

Multiple users in the same company sharing an identical raster request
receive the cached metadata without triggering a duplicate provider call.

Cache is non-fatal: Redis errors log a warning and return None (cache miss),
so the endpoint always falls back to live generation.

TTL is configured via RASTER_CACHE_TTL_SECONDS (default 43200s / 12h).
This value references GEE's empirical ~48h getMapId window — it is NOT
asserted as a product guarantee. Adjust via env var without code changes.

Tile images are NOT stored — only the metadata JSON contract is cached.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_CACHE_KEY_PREFIX = "raster:v1"


def build_cache_key(
    company_id: int,
    index: str,
    date_start: str,
    date_end: str,
    serving_mode: str,
    frame_id: str | None = None,
) -> str:
    """
    Build a deterministic company-scoped cache key for raster metadata.

    When frame_id is provided (timelapse frame selection), the key uses
    the frame's acquisition date as its time dimension to ensure two different
    frames never share a cache entry.

    Returns a string suitable for use as a Redis key.
    """
    if frame_id is not None:
        return f"{_CACHE_KEY_PREFIX}:{company_id}:{index}:frame:{frame_id}:{serving_mode}"
    return f"{_CACHE_KEY_PREFIX}:{company_id}:{index}:{date_start}:{date_end}:{serving_mode}"


async def get_cached_metadata(
    redis_client,
    cache_key: str,
) -> Optional[dict]:
    """
    Retrieve cached raster metadata from Redis.

    Returns the deserialized metadata dict on cache hit, None on miss or error.
    Redis errors are logged as warnings and treated as cache misses.
    """
    if redis_client is None:
        return None
    try:
        raw = await redis_client.get(cache_key)
        if raw is None:
            logger.debug("Raster cache MISS: %s", cache_key)
            return None
        logger.info("Raster cache HIT: %s", cache_key)
        return json.loads(raw)
    except Exception as exc:
        logger.warning("Raster cache GET error (non-fatal, treating as miss): %s", exc)
        return None


async def set_cached_metadata(
    redis_client,
    cache_key: str,
    metadata_dict: dict,
    ttl_seconds: int,
) -> None:
    """
    Store raster metadata in Redis with a provider-referenced TTL.

    ttl_seconds comes from settings.RASTER_CACHE_TTL_SECONDS (configurable).
    Redis errors are logged as warnings and do not affect the response.
    """
    if redis_client is None:
        return
    try:
        await redis_client.setex(cache_key, ttl_seconds, json.dumps(metadata_dict))
        logger.info("Raster cache SET: %s (TTL=%ds)", cache_key, ttl_seconds)
    except Exception as exc:
        logger.warning("Raster cache SET error (non-fatal): %s", exc)

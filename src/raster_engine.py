"""
Dual-mode raster engine — on-demand raster metadata contract [v1.6].

Serving modes (controlled by company_subscriptions.raster_serving_mode):
  gee_mapid      → basic tier: latest 7-day scene, getMapId() tile URL (~48h expiry)
  maps_platform  → premium tier: timelapse-capable, date param validated against
                    timelapse_period_months, getMapId() tile URL per specified date

This module is a thin contract layer on top of existing core_engine primitives.
It does NOT duplicate scene selection, harmonization, cloud masking, or index formulas.

GEE credentials are required at runtime. For offline contract tests, import only
RasterMetadata, RasterEngineError, SubscriptionAccessError, SUPPORTED_INDICES,
and SERVING_MODES — no ee.* calls are triggered at import time.
"""

from __future__ import annotations

import dataclasses
import logging
import pathlib
import sys
from datetime import date, timedelta

logger = logging.getLogger(__name__)

# Allow imports from src/ (same pattern as engine_launcher.py)
_SRC_DIR = pathlib.Path(__file__).parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

SUPPORTED_INDICES: tuple[str, ...] = ("ndvi", "evi", "savi", "gndvi", "ndre")
SERVING_MODES: tuple[str, ...] = ("gee_mapid", "maps_platform")

# Viz params — identical to map_previewer._VIZ_PARAMS (single source of truth kept in map_previewer)
_VIZ_PARAMS: dict[str, dict] = {
    "ndvi":  {"min": -0.2, "max": 0.9, "palette": ["red", "yellow", "green"]},
    "evi":   {"min": -0.2, "max": 0.9, "palette": ["red", "yellow", "green"]},
    "ndre":  {"min": -0.2, "max": 0.9, "palette": ["purple", "white", "green"]},
    "savi":  {"min": -0.2, "max": 0.9, "palette": ["#8B4513", "yellow", "green"]},
    "gndvi": {"min": -0.2, "max": 0.9, "palette": ["red", "yellow", "darkgreen"]},
}


@dataclasses.dataclass
class RasterMetadata:
    """
    Deterministic metadata artifact for a single raster product request.

    This is the v1.7 UI consumption contract — Explore Map must build against
    this schema. All fields are required and typed; no optional/nullable fields
    in the core contract.
    """
    schema_version: str          # "1.0"
    serving_mode: str            # "gee_mapid" or "maps_platform"
    subscription_tier: str       # "basic" or "premium"
    index: str                   # "ndvi", "evi", "savi", "gndvi", "ndre"
    sensor: str                  # "S2", "L8", or "L9"
    date_acquired: str           # ISO date — best scene acquisition date
    date_window_start: str       # ISO date — search window start
    date_window_end: str         # ISO date — search window end
    valid_pixel_ratio: float     # 0.0–1.0 fraction of clear pixels
    low_quality: bool            # True if Landsat with ratio in [0.2, 0.6)
    bounds: dict                 # {"west": float, "south": float, "east": float, "north": float}
    resolution_m: int            # 10 for S2, 30 for Landsat
    palette: list[str]           # Viz palette matching viz_min/viz_max
    viz_min: float
    viz_max: float
    tile_url_format: str         # GEE tile URL — ~48h expiry for getMapId
    tile_url_expires_note: str   # Human-readable expiry notice for v1.7 UI
    cloud_nodata_note: str       # Cloud/nodata masking explanation
    generated_at_utc: str        # ISO 8601 timestamp of metadata generation

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


class RasterEngineError(Exception):
    """Raised when the raster engine cannot produce a valid artifact."""


class SubscriptionAccessError(RasterEngineError):
    """Raised when the request violates subscription tier constraints."""


def generate_metadata(
    *,
    index: str,
    serving_mode: str,
    subscription_tier: str,
    timelapse_period_months: int | None,
    aoi_geojson: dict,
    date_start: str | None = None,
    date_end: str | None = None,
) -> RasterMetadata:
    """
    Generate raster tile metadata for the given index and subscription tier.

    Requires live GEE credentials initialized before calling. Load credentials
    from tests/.env using core_engine.ee_init.initialize_ee() before calling.

    For basic (gee_mapid): date_start/date_end are ignored — latest 7-day window used.
    For premium (maps_platform): date params must be within timelapse_period_months.

    Args:
        index:                   Vegetation index ("ndvi", "evi", "savi", "gndvi", "ndre").
        serving_mode:            "gee_mapid" or "maps_platform".
        subscription_tier:       "basic" or "premium".
        timelapse_period_months: Max lookback in months for premium (None for basic).
        aoi_geojson:             GeoJSON geometry or FeatureCollection of the estate AOI.
        date_start:              ISO date — premium timelapse window start (optional).
        date_end:                ISO date — premium timelapse window end (optional).

    Returns:
        RasterMetadata with tile URL and full v1.7 contract fields.

    Raises:
        ValueError:              Invalid index or serving_mode.
        SubscriptionAccessError: Date outside allowed timelapse window.
        RasterEngineError:       No valid scene found or GEE error.
    """
    from datetime import datetime, timezone

    if index not in SUPPORTED_INDICES:
        raise ValueError(
            f"Unsupported index: {index!r}. Supported: {SUPPORTED_INDICES}"
        )
    if serving_mode not in SERVING_MODES:
        raise ValueError(
            f"Unknown serving_mode: {serving_mode!r}. Supported: {SERVING_MODES}"
        )

    actual_start, actual_end = _resolve_date_window(
        serving_mode=serving_mode,
        subscription_tier=subscription_tier,
        timelapse_period_months=timelapse_period_months,
        date_start=date_start,
        date_end=date_end,
    )

    # Deferred GEE imports — avoids import ee at module load time (offline contract tests).
    # Maps ImportError → RasterEngineError so endpoint returns 503 instead of 500.
    try:
        import ee  # noqa: F401
        from core_engine.ee_init import initialize_ee
        from core_engine.scene_selector import select_best_scene
        from core_engine.cloud_masking import apply_cloud_mask
        from core_engine.harmonization import prepare_image
        from core_engine.index_calculator import calculate_indices
    except ImportError as exc:
        raise RasterEngineError(
            f"GEE runtime dependencies unavailable: {exc}. "
            "Ensure earthengine-api is installed and src/ is on sys.path."
        ) from exc

    # Initialize GEE — idempotent. Reads EE_SERVICE_ACCOUNT_KEY or EE_SERVICE_ACCOUNT_KEY_JSON.
    try:
        initialize_ee()
    except Exception as exc:
        raise RasterEngineError(
            f"GEE initialization failed: {exc}. "
            "Set EE_SERVICE_ACCOUNT_KEY or EE_SERVICE_ACCOUNT_KEY_JSON environment variable."
        ) from exc

    aoi_ee = _build_aoi(aoi_geojson)

    scene = select_best_scene(aoi_ee, actual_start, actual_end)
    if scene.skip:
        raise RasterEngineError(
            f"No valid scene found for window {actual_start} – {actual_end}. "
            f"Reason: {scene.reason}"
        )

    if index == "ndre" and scene.sensor in ("L8", "L9"):
        raise RasterEngineError(
            "NDRE requires Sentinel-2 (Red Edge band). "
            "The selected scene is Landsat. Try NDVI, EVI, SAVI, or GNDVI instead, "
            "or wait for a Sentinel-2 scene in the requested window."
        )

    image = apply_cloud_mask(scene.image, scene.sensor)
    image = prepare_image(image, scene.sensor)
    image = calculate_indices(image, scene.sensor)

    clipped = image.select(index).clip(aoi_ee)
    viz = _VIZ_PARAMS[index]
    map_id_obj = clipped.getMapId(viz)
    tile_url = map_id_obj["tile_fetcher"].url_format

    bounds = _compute_bounds(aoi_ee)
    resolution_m = 10 if scene.sensor == "S2" else 30

    return RasterMetadata(
        schema_version="1.0",
        serving_mode=serving_mode,
        subscription_tier=subscription_tier,
        index=index,
        sensor=scene.sensor,
        date_acquired=actual_end,
        date_window_start=actual_start,
        date_window_end=actual_end,
        valid_pixel_ratio=scene.valid_pixel_ratio,
        low_quality=scene.low_quality,
        bounds=bounds,
        resolution_m=resolution_m,
        palette=viz["palette"],
        viz_min=viz["min"],
        viz_max=viz["max"],
        tile_url_format=tile_url,
        tile_url_expires_note=(
            "~48 hours from generation (GEE getMapId limitation). "
            "v1.7 UI must call this endpoint on each page load to get a fresh URL."
        ),
        cloud_nodata_note=(
            "Cloudy and shadowed pixels are masked. "
            "Unmasked pixels represent clear-sky surface reflectance. "
            "Masked pixels render as transparent."
        ),
        generated_at_utc=datetime.now(timezone.utc).isoformat(),
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_date_window(
    *,
    serving_mode: str,
    subscription_tier: str,
    timelapse_period_months: int | None,
    date_start: str | None,
    date_end: str | None,
) -> tuple[str, str]:
    """
    Resolve the actual search date window.

    Basic / gee_mapid: always latest 7-day window, date params ignored.
    Premium / maps_platform: validates requested window against timelapse_period_months.
    """
    today = date.today()

    if serving_mode == "gee_mapid" or subscription_tier == "basic":
        end = today
        start = today - timedelta(days=7)
        return start.isoformat(), end.isoformat()

    # Premium timelapse — parse and validate
    end = date.fromisoformat(date_end) if date_end else today
    start = date.fromisoformat(date_start) if date_start else end - timedelta(days=7)

    if timelapse_period_months is not None:
        earliest_allowed = today - timedelta(days=timelapse_period_months * 30)
        if start < earliest_allowed:
            raise SubscriptionAccessError(
                f"Requested start date {start.isoformat()} is outside the allowed timelapse "
                f"window of {timelapse_period_months} months. "
                f"Earliest allowed: {earliest_allowed.isoformat()}."
            )

    return start.isoformat(), end.isoformat()


def _build_aoi(aoi_geojson: dict) -> "ee.Geometry":
    """Convert a GeoJSON dict (Geometry or FeatureCollection) to ee.Geometry."""
    import ee
    if aoi_geojson.get("type") == "FeatureCollection":
        features = aoi_geojson.get("features", [])
        if not features:
            raise RasterEngineError("AOI FeatureCollection contains no features.")
        geometries = [ee.Geometry(f["geometry"]) for f in features]
        merged = ee.Geometry.MultiPolygon(
            [g.coordinates().getInfo() for g in geometries]
        )
        return merged.dissolve(maxError=1)
    return ee.Geometry(aoi_geojson)


def _compute_bounds(aoi_ee: "ee.Geometry") -> dict:
    """Extract WGS84 bounding box from ee.Geometry."""
    bbox_coords = aoi_ee.bounds(maxError=1).coordinates().getInfo()[0]
    lons = [p[0] for p in bbox_coords]
    lats = [p[1] for p in bbox_coords]
    return {
        "west": min(lons),
        "south": min(lats),
        "east": max(lons),
        "north": max(lats),
    }

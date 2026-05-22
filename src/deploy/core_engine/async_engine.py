"""
Async export engine [FR-06 / FR-08].

Exports mean spectral index values per estate polygon to Google Cloud Storage (GCS)
via ee.batch.Export.table.toCloudStorage(), processing estates in sub-chunks.

Sub-chunking:
  Estates are split into batches of up to 2,000 polygons per export task
  to stay within GEE memory and quota limits.

Retry logic (3 retries with exponential backoff):
  wait = base_wait_seconds * (2 ** attempt)  — e.g., 30s, 60s, 120s
  Targets transient GEE errors: quotaExceeded, computeTimeout,
  and transient network failures (ConnectionError, Timeout).

Export schema (CSV, one row per estate) — aligned to satellite_data PostGIS table [FR-08]:
  block_id          — INTEGER FK to blocks.id (must exist in input GeoDataFrame).
  acquisition_date  — ISO date string of the selected scene.
  sensor            — Full sensor name: "sentinel-2", "landsat-8", "landsat-9".
  cloud_cover       — (1 - valid_pixel_ratio) * 100, as percentage NUMERIC(5,2).
  ndvi              — Mean NDVI (valid pixels only).
  evi               — Mean EVI.
  ndre              — Mean NDRE (S2 only; null for Landsat per FR-07).
  savi              — Mean SAVI.
  gndvi             — Mean GNDVI.
  features          — JSONB string: {"valid_pixel_ratio": <float>, "low_quality": <bool>}.
                      valid_pixel_ratio and low_quality are NOT top-level columns [FR-08].

Quality gate (FR-03):
  Estates with valid_pixel_ratio < 0.2 are filtered out server-side before export.
  They are not ingested; no carry-forward occurs.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import ee
import geopandas as gpd

from .quality_gate import build_valid_mask_band, VALID_PIXEL_RATIO_THRESHOLD

logger = logging.getLogger(__name__)

# Export engine tuning constants
DEFAULT_CHUNK_SIZE    = 2000
MAX_RETRIES           = 3
BASE_WAIT_SECONDS     = 30.0    # Exponential backoff base (seconds)
POLL_INTERVAL_SECONDS = 30.0    # Task status polling interval (seconds)

# Spatial resolution for reduceRegions
_SCALE_S2 = 10    # S2 native resolution (meters)
_SCALE_LS = 30    # Landsat native resolution (meters)

# FR-08: Full sensor name normalization for satellite_data DB table
_SENSOR_NAMES: dict[str, str] = {
    "S2": "sentinel-2",
    "L8": "landsat-8",
    "L9": "landsat-9",
}

# GEE error keywords that indicate transient / retryable failures
_TRANSIENT_KEYWORDS = ("quotaExceeded", "computeTimeout", "Too Many Requests")


@dataclass
class ChunkResult:
    """Result of a single sub-chunk export task."""
    chunk_index: int
    chunk_size: int
    status: str          # "COMPLETED" | "FAILED"
    export_file: str     # GCS file description string (fileNamePrefix)
    errors: list[str] = field(default_factory=list)


def run_export(
    image: ee.Image,
    estates_gdf: gpd.GeoDataFrame,
    gcs_bucket: str,
    acquisition_date: str,
    sensor: str,
    scene_low_quality: bool,
    id_column: str = "block_id",
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    max_retries: int = MAX_RETRIES,
    base_wait: float = BASE_WAIT_SECONDS,
) -> list[ChunkResult]:
    """
    Export mean spectral index values per estate polygon to Google Cloud Storage.

    The exported CSV schema is aligned to the satellite_data PostGIS table [FR-08].
    Input GeoDataFrame must contain a 'block_id' column (INTEGER FK to blocks.id).

    Args:
        image:             Prepared image with index bands (from calculate_indices).
        estates_gdf:       GeoDataFrame of estate polygons in WGS84 (EPSG:4326).
                           Must contain a `block_id` column.
        gcs_bucket:        Google Cloud Storage bucket name (e.g. 'canopy-sense-data').
        acquisition_date:  ISO date string of the selected scene (e.g. "2025-01-01").
        sensor:            Sensor identifier — "S2", "L8", or "L9".
        scene_low_quality: Scene-level low_quality flag (FR-07). True if Landsat
                           with 0.2 <= scene valid_pixel_ratio < 0.6.
        id_column:         Column in estates_gdf used as block identifier (default "block_id").
        chunk_size:        Max polygons per export sub-chunk (default 2000).
        max_retries:       Max retry attempts per chunk on transient errors (default 3).
        base_wait:         Base backoff wait in seconds (default 30s).

    Returns:
        List of ChunkResult, one entry per sub-chunk processed.
    """
    if sensor not in _SENSOR_NAMES:
        raise ValueError(f"Unknown sensor: {sensor!r}. Expected 'S2', 'L8', or 'L9'.")

    # Attach valid_mask band for per-estate valid_pixel_ratio computation (FR-03)
    image_with_mask = build_valid_mask_band(image)

    scale = _SCALE_S2 if sensor == "S2" else _SCALE_LS

    # Index bands to reduce over estate geometries
    index_bands = ["valid_mask", "ndvi", "evi", "savi", "gndvi"]
    if sensor == "S2":
        index_bands.append("ndre")   # NDRE uses S2 Red Edge B5 — not available on Landsat (FR-07)

    chunks = _split_into_chunks(estates_gdf, chunk_size)
    logger.info(
        "Export started: %d estates → %d chunks of ≤%d polygons | sensor=%s date=%s",
        len(estates_gdf), len(chunks), chunk_size, sensor, acquisition_date,
    )

    results: list[ChunkResult] = []
    for i, chunk_gdf in enumerate(chunks):
        logger.info(
            "Processing chunk %d/%d (%d estates).", i + 1, len(chunks), len(chunk_gdf)
        )
        result = _export_chunk_with_retry(
            chunk_index=i,
            chunk_gdf=chunk_gdf,
            image=image_with_mask,
            index_bands=index_bands,
            scale=scale,
            sensor=sensor,
            scene_low_quality=scene_low_quality,
            acquisition_date=acquisition_date,
            gcs_bucket=gcs_bucket,
            id_column=id_column,
            max_retries=max_retries,
            base_wait=base_wait,
        )
        results.append(result)

    _log_summary(results)
    return results


# ---------------------------------------------------------------------------
# Internal: chunk export with retry/backoff
# ---------------------------------------------------------------------------

def _export_chunk_with_retry(
    chunk_index: int,
    chunk_gdf: gpd.GeoDataFrame,
    image: ee.Image,
    index_bands: list[str],
    scale: int,
    sensor: str,
    scene_low_quality: bool,
    acquisition_date: str,
    gcs_bucket: str,
    id_column: str,
    max_retries: int,
    base_wait: float,
) -> ChunkResult:
    """
    Submit and poll a single chunk export task, retrying up to max_retries times
    on transient errors with exponential backoff.

    Backoff formula: wait = base_wait * (2 ** attempt)
      attempt 0 → immediate
      attempt 1 → base_wait * 1  (e.g., 30s)
      attempt 2 → base_wait * 2  (e.g., 60s)
      attempt 3 → base_wait * 4  (e.g., 120s)
    """
    last_error = ""

    for attempt in range(max_retries + 1):
        if attempt > 0:
            wait = base_wait * (2 ** (attempt - 1))
            logger.warning(
                "Chunk %d: retry %d/%d — waiting %.0fs (last error: %s)",
                chunk_index, attempt, max_retries, wait, last_error,
            )
            time.sleep(wait)

        try:
            file_desc = f"canopy_sense_{acquisition_date}_chunk{chunk_index:04d}"
            task = _submit_chunk_export(
                chunk_gdf=chunk_gdf,
                image=image,
                index_bands=index_bands,
                scale=scale,
                sensor=sensor,
                scene_low_quality=scene_low_quality,
                acquisition_date=acquisition_date,
                gcs_bucket=gcs_bucket,
                id_column=id_column,
                file_desc=file_desc,
            )
            _poll_until_done(task, file_desc)
            return ChunkResult(
                chunk_index=chunk_index,
                chunk_size=len(chunk_gdf),
                status="COMPLETED",
                export_file=file_desc,
            )

        except Exception as exc:
            last_error = str(exc)
            if _is_transient(exc) and attempt < max_retries:
                logger.warning(
                    "Chunk %d: transient error on attempt %d — %s",
                    chunk_index, attempt, last_error,
                )
                continue   # retry

            # Non-transient error or retries exhausted
            logger.error(
                "Chunk %d FAILED after %d attempt(s): %s",
                chunk_index, attempt + 1, last_error,
            )
            return ChunkResult(
                chunk_index=chunk_index,
                chunk_size=len(chunk_gdf),
                status="FAILED",
                export_file="",
                errors=[last_error],
            )

    # Defensive fallback (unreachable under normal flow)
    return ChunkResult(
        chunk_index=chunk_index,
        chunk_size=len(chunk_gdf),
        status="FAILED",
        export_file="",
        errors=[last_error],
    )


def _submit_chunk_export(
    chunk_gdf: gpd.GeoDataFrame,
    image: ee.Image,
    index_bands: list[str],
    scale: int,
    sensor: str,
    scene_low_quality: bool,
    acquisition_date: str,
    gcs_bucket: str,
    id_column: str,
    file_desc: str,
) -> ee.batch.Task:
    """
    Build and start an ee.batch.Export.table.toCloudStorage task for one chunk.

    Steps:
      1. Convert chunk GDF to ee.FeatureCollection (block_id as integer).
      2. Run reduceRegions → mean index values + valid_mask per estate.
      3. Apply FR-03 quality gate: filter estates with valid_mask < 0.2.
      4. Map each feature to FR-08 schema:
           a. Compute cloud_cover = (1 - valid_mask) * 100.
           b. Build features JSONB string: {"valid_pixel_ratio": X, "low_quality": Y}.
           c. Normalize sensor name (e.g., "S2" → "sentinel-2").
           d. Set acquisition_date.
           e. Clear valid_mask (not a top-level export column per FR-08).
           f. Set ndre = null for Landsat (FR-07).
      5. Export with FR-08 column order.
    """
    ee_features = _gdf_to_ee_feature_collection(chunk_gdf, id_column)

    # Compute mean of each index band (+ valid_mask) over each estate polygon
    reduced = image.select(index_bands).reduceRegions(
        collection=ee_features,
        reducer=ee.Reducer.mean(),
        scale=scale,
        tileScale=4,   # reduces memory pressure for large or complex polygons
    )

    # FR-03: Hard quality gate — exclude estates below valid_pixel_ratio threshold.
    # valid_mask mean = valid_pixel_ratio at this point (before rename/packaging).
    reduced = reduced.filter(
        ee.Filter.gte("valid_mask", VALID_PIXEL_RATIO_THRESHOLD)
    )

    # FR-08: Build DB-aligned export schema in a single server-side map pass.
    sensor_name    = _SENSOR_NAMES[sensor]
    low_quality_js = "true" if scene_low_quality else "false"   # Python-side, scene-level

    def _apply_fr08_schema(f: ee.Feature) -> ee.Feature:
        valid_ratio = ee.Number(f.get("valid_mask"))

        # cloud_cover = (1 - valid_pixel_ratio) * 100  [NUMERIC(5,2) in DB]
        cloud_cover = ee.Number(1).subtract(valid_ratio).multiply(100)

        # features JSONB: pack valid_pixel_ratio + low_quality (not top-level per FR-08)
        # low_quality is a scene-level flag — same value for all features in this chunk.
        features_json = (
            ee.String('{"valid_pixel_ratio":')
            .cat(valid_ratio.format("%.6f"))
            .cat(',"low_quality":' + low_quality_js + '}')
        )

        return f.set({
            "acquisition_date": acquisition_date,
            "sensor":           sensor_name,
            "cloud_cover":      cloud_cover,
            "features":         features_json,
            "valid_mask":       None,   # cleared — packed into features JSONB
        })

    reduced = reduced.map(_apply_fr08_schema)

    # FR-07: explicitly set ndre = null for Landsat (no Red Edge band on Landsat)
    if sensor in ("L8", "L9"):
        reduced = reduced.map(lambda f: f.set("ndre", None))

    # FR-08: Final column order matching satellite_data PostGIS table exactly
    selectors = [
        id_column,        # block_id
        "acquisition_date",
        "sensor",
        "cloud_cover",
        "ndvi",
        "evi",
        "ndre",
        "savi",
        "gndvi",
        "features",       # JSONB string: {valid_pixel_ratio, low_quality}
    ]

    task = ee.batch.Export.table.toCloudStorage(
        collection=reduced,
        description=file_desc,
        bucket=gcs_bucket,
        fileNamePrefix=file_desc,
        fileFormat="CSV",
        selectors=selectors,
    )
    task.start()
    logger.info("Export task started to GCS: %s (task_id=%s)", file_desc, task.id)
    return task


# ---------------------------------------------------------------------------
# Internal: task polling
# ---------------------------------------------------------------------------

def _poll_until_done(task: ee.batch.Task, description: str) -> None:
    """
    Poll the GEE export task status until it reaches COMPLETED or FAILED.

    Raises:
        RuntimeError: If the task fails or is cancelled.
    """
    while True:
        status = task.status()
        state = status.get("state", "UNKNOWN")

        if state == "COMPLETED":
            logger.info("Task '%s' COMPLETED.", description)
            return

        if state == "FAILED":
            error_msg = status.get("error_message", "Unknown error")
            raise RuntimeError(
                f"GEE task '{description}' FAILED: {error_msg}"
            )

        if state in ("CANCEL_REQUESTED", "CANCELLED"):
            raise RuntimeError(f"GEE task '{description}' was CANCELLED.")

        logger.debug(
            "Task '%s' state=%s — polling in %.0fs.",
            description, state, POLL_INTERVAL_SECONDS,
        )
        time.sleep(POLL_INTERVAL_SECONDS)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _is_transient(exc: Exception) -> bool:
    """
    Return True if the exception represents a transient GEE or network error
    that is safe to retry.

    Targets:
      - GEE quota/timeout errors (quotaExceeded, computeTimeout)
      - HTTP 429 / Too Many Requests
      - Network-level failures (ConnectionError, Timeout)
    """
    error_msg = str(exc)
    for keyword in _TRANSIENT_KEYWORDS:
        if keyword.lower() in error_msg.lower():
            return True

    try:
        import requests.exceptions
        if isinstance(exc, (requests.exceptions.ConnectionError,
                             requests.exceptions.Timeout)):
            return True
    except ImportError:
        pass

    return False


def _gdf_to_ee_feature_collection(
    gdf: gpd.GeoDataFrame, id_column: str
) -> ee.FeatureCollection:
    """
    Convert a GeoDataFrame to an ee.FeatureCollection.
    block_id is stored as integer to match the INTEGER FK in satellite_data [FR-08].
    """
    features = []
    for _, row in gdf.iterrows():
        geom = ee.Geometry(row.geometry.__geo_interface__)
        props = {id_column: int(row[id_column])}   # integer FK per FR-08
        features.append(ee.Feature(geom, props))
    return ee.FeatureCollection(features)


def _split_into_chunks(
    gdf: gpd.GeoDataFrame, chunk_size: int
) -> list[gpd.GeoDataFrame]:
    """Split a GeoDataFrame into sub-chunks of at most chunk_size rows."""
    return [
        gdf.iloc[i: i + chunk_size]
        for i in range(0, len(gdf), chunk_size)
    ]


def _log_summary(results: list[ChunkResult]) -> None:
    completed = sum(1 for r in results if r.status == "COMPLETED")
    failed    = sum(1 for r in results if r.status == "FAILED")
    total     = sum(r.chunk_size for r in results)
    logger.info(
        "Export summary: %d/%d chunks COMPLETED | %d FAILED | %d total estates processed.",
        completed, len(results), failed, total,
    )

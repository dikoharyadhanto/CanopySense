"""
historical_backfill.py — CanopySense Historical Data Seeder [WO-002-v0.5].

DEPRECATED — Use patcher_local.py --backfill instead.
  patcher_local.py --backfill                          # all estates, 3-year default
  patcher_local.py --backfill --estate-id 1            # estate scope
  patcher_local.py --backfill --date-start 2024-01 --date-end 2024-03  # custom range

This standalone script is retained as a documented fallback and reference.
It bypasses the Cloud Function route and runs GEE directly — do not use
for routine operational backfill once the integrated route is verified.

Loops week-by-week from April 2023 to April 2026 (~156 chunks of 7 days each),
extracts the best available satellite scene per week, and inserts the
resulting vegetation index statistics into canopysense.satellite_data.

Design rationale:
  The live autoscheduler runs every 7 days and picks the best scene in that
  7-day window. Historical backfill must use identical 7-day windows so that
  the time-series frequency is consistent — a prerequisite for STL seasonal
  decomposition and anomaly detection. Monthly chunks were rejected because
  they produce 1 observation/month historically vs ~4 observations/month
  from the live system, creating a regime change that breaks STL models.

  One best scene per 7-day chunk via the existing select_best_scene()
  priority logic (S2 Tier 1 → S2 Tier 2 → Landsat → Skip). Blocks that fail
  the FR-03 cloud gate for that scene remain blank for that week — no carry-
  forward, consistent with the live engine behavior.

Chunking:
  7-day windows starting from start_date. Each chunk is independent — the
  script is fully restartable. ON CONFLICT (block_id, acquisition_date, sensor)
  DO NOTHING ensures PostGIS is never corrupted by a re-run.

Output:
  CSV backups → 04_Test/result_output/historical/canopysense_{date}.csv
  PostGIS     → canopysense.satellite_data (via ingest_to_postgis.run_ingestion)

Usage:
  python 03_Build/historical_backfill.py

  Optional flags:
    --start  YYYY-MM   Start month (default: 2023-04)
    --end    YYYY-MM   End month   (default: current month)
    --dry-run          Parse and validate without writing to DB
"""

from __future__ import annotations

import argparse
import calendar
import json
import logging
import os
import pathlib
import sys
from datetime import date, timedelta

import ee
import geopandas as gpd
import pandas as pd
import psycopg2
from shapely.geometry import mapping

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_BUILD_DIR    = pathlib.Path(__file__).parent
_PROJECT_ROOT = _BUILD_DIR.parent
sys.path.insert(0, str(_BUILD_DIR))

from core_engine.ee_init import initialize_ee
from core_engine.scene_selector import select_best_scene
from core_engine.cloud_masking import apply_cloud_mask
from core_engine.harmonization import prepare_image
from core_engine.index_calculator import calculate_indices
from core_engine.quality_gate import build_valid_mask_band, VALID_PIXEL_RATIO_THRESHOLD
from ingestion.ingest_to_postgis import run_ingestion

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_HISTORICAL_OUTPUT_DIR = _PROJECT_ROOT / "tests" / "result_output" / "historical"
_ENV_FILE              = _PROJECT_ROOT / "tests" / ".env"

_DEFAULT_START = "2023-04"
_DEFAULT_END   = date.today().strftime("%Y-%m")

_SENSOR_NAMES: dict[str, str] = {
    "S2": "sentinel-2",
    "L8": "landsat-8",
    "L9": "landsat-9",
}

_SCALE_S2 = 10
_SCALE_LS = 30


# ---------------------------------------------------------------------------
# Main backfill runner
# ---------------------------------------------------------------------------

def run_backfill(
    start_ym: str = _DEFAULT_START,
    end_ym:   str = _DEFAULT_END,
    dry_run:  bool = False,
) -> None:
    """
    Run the full historical backfill pipeline with resume/caching support.

    Resume behaviour (three-layer guard):
      1. Has-data check  — if satellite_data already has rows for this window's
                           acquisition date, the window is silently skipped.
      2. Backlog check   — if the window is recorded in backfill_skipped, it is
                           permanently skipped (no GEE call made).
      3. Backlog write   — if GEE returns no scene OR all blocks fail FR-03, the
                           window is written to backfill_skipped so future reruns
                           do not waste API quota retrying it.

    Args:
        start_ym: Start month in YYYY-MM format (inclusive).
        end_ym:   End month in YYYY-MM format (inclusive).
        dry_run:  If True, extract and validate data but do not write to DB or backlog.
    """
    chunks = _generate_weekly_chunks(start_ym, end_ym)
    logger.info(
        "Historical backfill: %d weekly chunks | %s → %s | dry_run=%s",
        len(chunks), start_ym, end_ym, dry_run,
    )

    # Keep a single DB connection open for the entire run (backlog + block load)
    conn = _get_db_connection()

    try:
        # Ensure backlog table exists
        _ensure_backlog_table(conn)

        # Load blocks from DB
        logger.info("Loading blocks from canopysense.blocks...")
        blocks_gdf = _load_blocks_from_db(conn)

        if blocks_gdf.empty:
            logger.error(
                "No blocks found in canopysense.blocks. "
                "Run engine_launcher.py --seed-shapefile first."
            )
            return

        logger.info("Loaded %d blocks.", len(blocks_gdf))

        # Initialize GEE once
        logger.info("Initializing GEE...")
        initialize_ee()

        # Build AOI from block union
        aoi_ee = _build_aoi(blocks_gdf)

        # Create historical output directory
        _HISTORICAL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        # --- Main loop ---
        total_inserted   = 0
        total_skipped    = 0
        chunks_with_data = 0
        chunks_no_scene  = 0
        chunks_resumed   = 0
        chunks_backlogged = 0

        for idx, (date_start, date_end, label) in enumerate(chunks, start=1):
            logger.info("─── Week %d/%d: %s ───", idx, len(chunks), label)

            # Layer 1: Has-data check — skip if satellite_data already has
            # rows whose acquisition_date falls inside this 7-day window.
            if not dry_run and _has_existing_data(conn, date_start, date_end):
                logger.info("  Already in DB — resuming past this week.")
                chunks_resumed += 1
                continue

            # Layer 2: Backlog check — skip permanently clouded-out windows.
            if _is_in_backlog(conn, date_start, date_end):
                logger.info("  In backlog (permanent skip) — no GEE call made.")
                chunks_backlogged += 1
                chunks_no_scene += 1
                continue

            # Layer 3: GEE scene selection
            scene = select_best_scene(aoi_ee, date_start, date_end)

            if scene.skip:
                logger.info("  No valid scene for this week — recording to backlog.")
                chunks_no_scene += 1
                if not dry_run:
                    _write_to_backlog(conn, date_start, date_end, "no_scene")
                continue

            logger.info(
                "  Scene selected: sensor=%s | valid_pixel_ratio=%.3f | low_quality=%s",
                scene.sensor, scene.valid_pixel_ratio, scene.low_quality,
            )

            # Image processing pipeline
            image = apply_cloud_mask(scene.image, scene.sensor)
            image = prepare_image(image, scene.sensor)
            image = calculate_indices(image, scene.sensor)

            # Actual acquisition date from scene metadata
            acquisition_date: str = scene.image.date().format("YYYY-MM-dd").getInfo()
            logger.info("  Acquisition date: %s", acquisition_date)

            # Extract stats → CSV
            csv_path, n_passed, n_skipped = _extract_to_csv(
                image=image,
                blocks_gdf=blocks_gdf,
                sensor=scene.sensor,
                acquisition_date=acquisition_date,
                scene_low_quality=scene.low_quality,
            )

            logger.info(
                "  Blocks: %d passed FR-03 gate | %d skipped (cloud cover)",
                n_passed, n_skipped,
            )

            if not csv_path:
                # Scene found but every block failed FR-03 — record to backlog.
                logger.info(
                    "  No valid blocks for %s — recording to backlog.", label
                )
                chunks_no_scene += 1
                if not dry_run:
                    _write_to_backlog(conn, date_start, date_end, "fr03_all_failed")
                continue

            chunks_with_data += 1

            # Ingest CSV → PostGIS
            if dry_run:
                logger.info("  [DRY-RUN] Skipping PostGIS insert for %s.", label)
            else:
                summary = run_ingestion(input_dir=str(_HISTORICAL_OUTPUT_DIR))
                inserted = summary["rows_loaded"]
                total_inserted += inserted
                total_skipped  += summary["rows_skipped"]
                logger.info(
                    "  PostGIS: %d inserted | %d skipped (conflict) | %d errors",
                    inserted, summary["rows_skipped"], len(summary["errors"]),
                )

    finally:
        conn.close()

    # --- Final summary ---
    logger.info("=" * 60)
    logger.info("Backfill complete.")
    logger.info("  Weeks total      : %d", len(chunks))
    logger.info("  Weeks resumed    : %d (already in DB)", chunks_resumed)
    logger.info("  Weeks backlogged : %d (permanent skip, no GEE call)", chunks_backlogged)
    logger.info("  Weeks no scene   : %d (cloud/gap → written to backlog)", chunks_no_scene)
    logger.info("  Weeks with data  : %d", chunks_with_data)
    if not dry_run:
        logger.info("  Rows inserted    : %d", total_inserted)
        logger.info("  Rows skipped     : %d (ON CONFLICT DO NOTHING)", total_skipped)
    logger.info("  CSV output dir   : %s", _HISTORICAL_OUTPUT_DIR)
    logger.info("=" * 60)


# ---------------------------------------------------------------------------
# Backlog table helpers
# ---------------------------------------------------------------------------

_BACKLOG_DDL = """
CREATE TABLE IF NOT EXISTS canopysense.backfill_skipped (
    id           SERIAL PRIMARY KEY,
    window_start DATE        NOT NULL,
    window_end   DATE        NOT NULL,
    batch_fp     TEXT        NOT NULL DEFAULT '',
    skip_reason  TEXT        NOT NULL,
    skipped_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (window_start, window_end, batch_fp)
);
COMMENT ON TABLE canopysense.backfill_skipped IS
    'Permanent record of 7-day windows where no usable satellite scene was '
    'found (no_scene) or every block failed the FR-03 quality gate '
    '(fr03_all_failed). historical_backfill.py checks this table before '
    'making GEE API calls so reruns do not waste quota on known-bad windows. '
    'batch_fp=empty-string is used by historical_backfill.py (legacy fallback).';
"""


def _ensure_backlog_table(conn: psycopg2.extensions.connection) -> None:
    """Create canopysense.backfill_skipped if it does not already exist."""
    with conn.cursor() as cur:
        cur.execute(_BACKLOG_DDL)
    conn.commit()
    logger.info("Backlog table ready: canopysense.backfill_skipped")


def _has_existing_data(
    conn: psycopg2.extensions.connection,
    date_start: str,
    date_end: str,
) -> bool:
    """
    Return True if satellite_data already contains at least one row whose
    acquisition_date falls within [date_start, date_end].

    Used as Layer 1 of the resume guard: if the window already produced data
    in a previous run, skip GEE entirely.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1 FROM canopysense.satellite_data
            WHERE acquisition_date BETWEEN %s AND %s
            LIMIT 1
            """,
            (date_start, date_end),
        )
        return cur.fetchone() is not None


def _is_in_backlog(
    conn: psycopg2.extensions.connection,
    date_start: str,
    date_end: str,
) -> bool:
    """
    Return True if this window is recorded in backfill_skipped.

    Used as Layer 2 of the resume guard: permanently clouded-out windows
    are never retried, preserving GEE API quota.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1 FROM canopysense.backfill_skipped
            WHERE window_start = %s AND window_end = %s
            LIMIT 1
            """,
            (date_start, date_end),
        )
        return cur.fetchone() is not None


def _write_to_backlog(
    conn: psycopg2.extensions.connection,
    date_start: str,
    date_end: str,
    reason: str,
) -> None:
    """
    Insert a skip record into backfill_skipped.

    Args:
        conn:       Active psycopg2 connection.
        date_start: Window start date (ISO string).
        date_end:   Window end date (ISO string).
        reason:     "no_scene" | "fr03_all_failed"
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO canopysense.backfill_skipped
                (window_start, window_end, batch_fp, skip_reason)
            VALUES (%s, %s, '', %s)
            ON CONFLICT (window_start, window_end, batch_fp) DO NOTHING
            """,
            (date_start, date_end, reason),
        )
    conn.commit()
    logger.debug(
        "Backlog: recorded %s → %s (%s)", date_start, date_end, reason
    )


# ---------------------------------------------------------------------------
# Weekly chunk generator
# ---------------------------------------------------------------------------

def _generate_weekly_chunks(
    start_ym: str,
    end_ym: str,
) -> list[tuple[str, str, str]]:
    """
    Generate a list of (date_start, date_end, label) tuples for consecutive
    7-day windows from the first day of start_ym to the last day of end_ym.

    Matches the live engine's 7-day search window exactly, ensuring historical
    and live data share the same temporal sampling frequency for STL analysis.

    Args:
        start_ym: "YYYY-MM" start month — first day used as window start.
        end_ym:   "YYYY-MM" end month — last day used as window end (inclusive).

    Returns:
        List of (date_start, date_end, label) tuples in chronological order.
        Example entry: ("2023-04-01", "2023-04-07", "01 Apr 2023 → 07 Apr 2023")
        Final window may be shorter than 7 days if period end falls mid-week.
    """
    start_year, start_month = int(start_ym[:4]), int(start_ym[5:7])
    end_year,   end_month   = int(end_ym[:4]),   int(end_ym[5:7])

    _, last_day = calendar.monthrange(end_year, end_month)
    period_start = date(start_year, start_month, 1)
    period_end   = date(end_year, end_month, last_day)

    chunks: list[tuple[str, str, str]] = []
    current = period_start

    while current <= period_end:
        chunk_end = min(current + timedelta(days=6), period_end)
        label = (
            f"{current.strftime('%d %b %Y')} → {chunk_end.strftime('%d %b %Y')}"
        )
        chunks.append((
            current.strftime("%Y-%m-%d"),
            chunk_end.strftime("%Y-%m-%d"),
            label,
        ))
        current += timedelta(days=7)

    return chunks


# ---------------------------------------------------------------------------
# GEE extraction → local CSV
# ---------------------------------------------------------------------------

def _extract_to_csv(
    image: ee.Image,
    blocks_gdf: gpd.GeoDataFrame,
    sensor: str,
    acquisition_date: str,
    scene_low_quality: bool,
) -> tuple[str, int, int]:
    """
    Compute mean vegetation index values per block via synchronous
    reduceRegions().getInfo() and write results to a historical CSV.

    Applies FR-03 quality gate (valid_pixel_ratio >= 0.2) in Python.
    Applies FR-08 schema: columns match canopysense.satellite_data DDL.
    FR-07: ndre is None for Landsat records.

    Args:
        image:             Processed image with all index bands.
        blocks_gdf:        GeoDataFrame with block_id + geometry columns.
        sensor:            "S2", "L8", or "L9".
        acquisition_date:  Actual scene acquisition date (ISO string).
        scene_low_quality: Scene-level low_quality flag (FR-07).

    Returns:
        Tuple of (csv_path, n_passed, n_skipped).
        csv_path is empty string if no blocks passed FR-03.
    """
    scale       = _SCALE_S2 if sensor == "S2" else _SCALE_LS
    sensor_name = _SENSOR_NAMES[sensor]

    image_with_mask = build_valid_mask_band(image)

    index_bands = ["valid_mask", "ndvi", "evi", "savi", "gndvi"]
    if sensor == "S2":
        index_bands.append("ndre")

    # Build EE FeatureCollection
    ee_features = [
        ee.Feature(
            ee.Geometry(mapping(row["geometry"])),
            {"block_id": int(row["block_id"])},
        )
        for _, row in blocks_gdf.iterrows()
    ]
    ee_collection = ee.FeatureCollection(ee_features)

    # Server-side reduceRegions
    reduced = (
        image_with_mask.select(index_bands)
        .reduceRegions(
            collection=ee_collection,
            reducer=ee.Reducer.mean(),
            scale=scale,
            tileScale=4,
        )
    )

    result_info = reduced.getInfo()
    features    = result_info.get("features", [])

    # Apply FR-03 + FR-08 schema
    rows: list[dict] = []
    n_skipped = 0

    for feat in features:
        props       = feat.get("properties", {})
        block_id    = props.get("block_id")
        valid_ratio = props.get("valid_mask")

        if valid_ratio is None or valid_ratio < VALID_PIXEL_RATIO_THRESHOLD:
            n_skipped += 1
            continue

        cloud_cover   = round((1.0 - valid_ratio) * 100, 2)
        features_json = json.dumps({
            "valid_pixel_ratio": round(valid_ratio, 6),
            "low_quality":       scene_low_quality,
        })

        rows.append({
            "block_id":         block_id,
            "acquisition_date": acquisition_date,
            "sensor":           sensor_name,
            "cloud_cover":      cloud_cover,
            "ndvi":             props.get("ndvi"),
            "evi":              props.get("evi"),
            "ndre":             props.get("ndre") if sensor == "S2" else None,
            "savi":             props.get("savi"),
            "gndvi":            props.get("gndvi"),
            "features":         features_json,
        })

    n_passed = len(rows)

    if not rows:
        return "", n_passed, n_skipped

    column_order = [
        "block_id", "acquisition_date", "sensor", "cloud_cover",
        "ndvi", "evi", "ndre", "savi", "gndvi", "features",
    ]
    csv_path = _HISTORICAL_OUTPUT_DIR / f"canopysense_{acquisition_date}.csv"
    pd.DataFrame(rows, columns=column_order).to_csv(csv_path, index=False)

    return str(csv_path), n_passed, n_skipped


# ---------------------------------------------------------------------------
# Block loader
# ---------------------------------------------------------------------------

def _load_blocks_from_db(
    conn: psycopg2.extensions.connection,
) -> gpd.GeoDataFrame:
    """Load all blocks from canopysense.blocks with geometry."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id AS block_id, ST_AsGeoJSON(geometry) AS geojson
            FROM canopysense.blocks
            ORDER BY id
            """
        )
        rows = cur.fetchall()

    if not rows:
        return gpd.GeoDataFrame(columns=["block_id", "geometry"])

    from shapely.geometry import shape

    records = [
        {"block_id": block_id, "geometry": shape(json.loads(geojson))}
        for block_id, geojson in rows
    ]
    return gpd.GeoDataFrame(records, crs="EPSG:4326")


# ---------------------------------------------------------------------------
# AOI builder
# ---------------------------------------------------------------------------

def _build_aoi(blocks_gdf: gpd.GeoDataFrame) -> ee.Geometry:
    """Build an ee.Geometry from the union of all block geometries."""
    return ee.Geometry(mapping(blocks_gdf.geometry.union_all()))


# ---------------------------------------------------------------------------
# DB connection
# ---------------------------------------------------------------------------

def _get_db_connection() -> psycopg2.extensions.connection:
    """Build psycopg2 connection, loading 04_Test/.env if present."""
    if _ENV_FILE.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(_ENV_FILE, override=False)
        except ImportError:
            pass

    host     = os.environ.get("PGHOST", "localhost")
    port     = int(os.environ.get("PGPORT", 5432))
    database = os.environ.get("PGDATABASE", "canopysense")
    user     = os.environ.get("PGUSER", "postgres")
    password = os.environ.get("PGPASSWORD", "")

    logger.info("Connecting to PostGIS: %s@%s:%d/%s", user, host, port, database)
    conn = psycopg2.connect(
        host=host, port=port, dbname=database, user=user, password=password,
    )
    conn.autocommit = False
    return conn


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "CanopySense Historical Backfill — "
            "seeds satellite_data with up to 3 years of monthly GEE extracts."
        )
    )
    parser.add_argument(
        "--start",
        metavar="YYYY-MM",
        default=_DEFAULT_START,
        help=f"Start month, inclusive (default: {_DEFAULT_START})",
    )
    parser.add_argument(
        "--end",
        metavar="YYYY-MM",
        default=_DEFAULT_END,
        help=f"End month, inclusive (default: {_DEFAULT_END} — current month)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Extract and validate data without writing to the database.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )

    args = _parse_args()
    run_backfill(
        start_ym=args.start,
        end_ym=args.end,
        dry_run=args.dry_run,
    )

"""
engine_launcher.py — CanopySense Master Orchestrator [WO-001-v0.4 Task 6].

Chains the full end-to-end pipeline:
  1. (Optional) Seed canopysense.estates/afdelings/blocks from a shapefile
  2. Load all blocks from canopysense.blocks table
  3. Initialize GEE + compute last-7-day date window
  4. Select best satellite scene (S2 priority → Landsat fallback)
  5. Cloud mask → harmonize → calculate indices
  6. Extract mean index stats per block (synchronous, no GCS)
  7. Save results as local CSV in 04_Test/result_output/
  8. Generate Leaflet HTML map preview (getMapId — no ee.batch.Export.image)
  9. Ingest CSV into canopysense.satellite_data (PostGIS Docker)

Usage:
  # First run — seed DB from shapefile, then run pipeline:
  python 03_Build/engine_launcher.py --seed-shapefile /path/to/blocks.shp

  # All subsequent / scheduled runs — reads blocks directly from DB:
  python 03_Build/engine_launcher.py

Scheduler:
  Set SCHEDULER_ENABLED=true in 04_Test/.env to activate weekly automation.
  When enabled, the process stays alive and triggers the pipeline every 7 days.
  Default: SCHEDULER_ENABLED=false (single-shot execution).

Seeder column expectations (shapefile):
  estate    — estate name (str)
  AfdelName — afdeling name (str)
  Afdeling  — afdeling number (int)
  Blok      — block name/label (str)
  OBJECTID  — unique feature ID (int) — used to generate block.code
  Tahun     — planting year (int)
  Existing  — clone type (str, nullable)
  geometry  — Polygon or MultiPolygon (any CRS; reprojected to EPSG:4326)
"""

from __future__ import annotations

import argparse
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
import psycopg2.extras
from shapely.geometry import mapping

# ---------------------------------------------------------------------------
# Path setup — allow imports from 03_Build/
# ---------------------------------------------------------------------------

_BUILD_DIR   = pathlib.Path(__file__).parent
_PROJECT_ROOT = _BUILD_DIR.parent
sys.path.insert(0, str(_BUILD_DIR))

from core_engine.ee_init import initialize_ee
from core_engine.scene_selector import select_best_scene
from core_engine.cloud_masking import apply_cloud_mask
from core_engine.harmonization import prepare_image
from core_engine.index_calculator import calculate_indices
from core_engine.quality_gate import build_valid_mask_band, VALID_PIXEL_RATIO_THRESHOLD
from core_engine.map_previewer import generate_preview
from ingestion.ingest_to_postgis import run_ingestion

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_OUTPUT_DIR = _PROJECT_ROOT / "tests" / "result_output"
_ENV_FILE   = _PROJECT_ROOT / "tests" / ".env"

# Sensor name normalization (FR-08)
_SENSOR_NAMES: dict[str, str] = {
    "S2": "sentinel-2",
    "L8": "landsat-8",
    "L9": "landsat-9",
}

# Spatial resolution for reduceRegions (meters)
_SCALE_S2 = 10
_SCALE_LS = 30


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_pipeline(seed_shapefile: str | None = None) -> None:
    """
    Execute the full CanopySense data extraction and ingestion pipeline.

    Args:
        seed_shapefile: Path to a block shapefile for one-time DB seeding.
                        If None, blocks are read directly from the DB.
    """
    conn = _get_db_connection()
    try:
        # Step 0 — optional DB seeding from shapefile
        if seed_shapefile:
            logger.info("=== Step 0: Seeding DB from shapefile ===")
            _seed_blocks_from_shapefile(seed_shapefile, conn)

        # Step 1 — load all blocks from DB
        logger.info("=== Step 1: Loading blocks from DB ===")
        blocks_gdf = _load_blocks_from_db(conn)

        if blocks_gdf.empty:
            logger.error(
                "canopysense.blocks is empty. "
                "Run with --seed-shapefile <path> to populate the DB first."
            )
            return

        logger.info("Loaded %d blocks from canopysense.blocks.", len(blocks_gdf))

        # Step 2 — GEE initialization + date window
        logger.info("=== Step 2: Initializing GEE ===")
        initialize_ee()

        date_end   = date.today().isoformat()
        date_start = (date.today() - timedelta(days=7)).isoformat()
        logger.info("Scene search window: %s → %s", date_start, date_end)

        # Step 3 — scene selection
        logger.info("=== Step 3: Scene selection ===")
        aoi_ee = _build_aoi(blocks_gdf)
        scene  = select_best_scene(aoi_ee, date_start, date_end)

        if scene.skip:
            logger.warning(
                "No valid scene found for window %s – %s. Pipeline aborted.",
                date_start, date_end,
            )
            return

        logger.info(
            "Scene selected: sensor=%s | valid_pixel_ratio=%.3f | low_quality=%s",
            scene.sensor, scene.valid_pixel_ratio, scene.low_quality,
        )

        # Step 4 — image processing
        logger.info("=== Step 4: Cloud mask → harmonize → calculate indices ===")
        image = apply_cloud_mask(scene.image, scene.sensor)
        image = prepare_image(image, scene.sensor)
        image = calculate_indices(image, scene.sensor)

        # Retrieve actual scene acquisition date (fixes v0.1 tech debt)
        acquisition_date: str = scene.image.date().format("YYYY-MM-dd").getInfo()
        logger.info("Actual acquisition date: %s", acquisition_date)

        # Step 5 — synchronous GEE extraction → local CSV
        logger.info("=== Step 5: Extracting index statistics to local CSV ===")
        csv_path, passed_block_ids = _extract_to_local_csv(
            image=image,
            blocks_gdf=blocks_gdf,
            sensor=scene.sensor,
            acquisition_date=acquisition_date,
            scene_low_quality=scene.low_quality,
        )

        if not csv_path:
            logger.warning("No blocks passed the quality gate. Skipping preview and ingestion.")
            return

        logger.info("CSV written: %s", csv_path)

        # Step 6 — HTML map preview
        logger.info("=== Step 6: Generating HTML map preview ===")
        date_label    = f"{date_start} \u2192 {date_end}  (acquired: {acquisition_date})"
        blocks_geojson = _build_blocks_geojson(blocks_gdf, passed_block_ids)
        html_path     = generate_preview(
            image=image,
            sensor=scene.sensor,
            aoi_ee=aoi_ee,
            date_label=date_label,
            blocks_geojson=blocks_geojson,
        )
        logger.info("HTML preview written: %s", html_path)

        # Step 7 — PostGIS ingestion
        logger.info("=== Step 7: Ingesting CSV into canopysense.satellite_data ===")
        summary = run_ingestion(input_dir=str(_OUTPUT_DIR))
        logger.info(
            "Ingestion complete — loaded: %d | skipped (conflict): %d | errors: %d",
            summary["rows_loaded"], summary["rows_skipped"], len(summary["errors"]),
        )
        if summary["errors"]:
            for err in summary["errors"]:
                logger.error("  Ingestion error: %s", err)

        logger.info("=== Pipeline complete ===")

    finally:
        conn.close()


# ---------------------------------------------------------------------------
# DB seeder — Option A: seed estates → afdelings → blocks from shapefile
# ---------------------------------------------------------------------------

def _seed_blocks_from_shapefile(
    shp_path: str,
    conn: psycopg2.extensions.connection,
) -> None:
    """
    Idempotent seeder: inserts estate, afdeling, and block records from a shapefile.
    Safe to re-run — existing records (matched by code) are skipped.

    MultiPolygon features are reduced to their largest polygon component
    to satisfy the blocks table CHECK (GeometryType = 'POLYGON') constraint.
    All geometries are reprojected to EPSG:4326 before insertion.
    """
    logger.info("Reading shapefile: %s", shp_path)
    gdf = gpd.read_file(shp_path)
    logger.info("Loaded %d features | CRS: %s", len(gdf), gdf.crs)

    # Reproject to EPSG:4326 if needed
    if gdf.crs is None or gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)
        logger.info("Reprojected to EPSG:4326.")

    # Flatten any MultiPolygon → largest polygon component
    def _to_polygon(geom):
        if geom.geom_type == "MultiPolygon":
            largest = max(geom.geoms, key=lambda g: g.area)
            logger.warning(
                "MultiPolygon detected — using largest component (area=%.8f deg²).", largest.area
            )
            return largest
        return geom

    gdf = gdf.copy()
    gdf["geometry"] = gdf["geometry"].apply(_to_polygon)

    with conn.cursor() as cur:

        # --- Estate ---
        estate_name = str(gdf["estate"].iloc[0])
        estate_code = "PPKS-SEMBAWA"

        cur.execute(
            "SELECT id FROM canopysense.estates WHERE code = %s",
            (estate_code,),
        )
        existing_estate = cur.fetchone()

        if existing_estate:
            estate_id = existing_estate[0]
            logger.info("Estate already in DB (id=%d): %s", estate_id, estate_name)
        else:
            estate_union_wkt = gdf.geometry.union_all().wkt
            cur.execute(
                """
                INSERT INTO canopysense.estates (name, code, geometry)
                VALUES (
                    %s,
                    %s,
                    ST_Force3D(ST_Multi(ST_GeomFromText(%s, 4326)))
                )
                RETURNING id
                """,
                (estate_name, estate_code, estate_union_wkt),
            )
            estate_id = cur.fetchone()[0]
            logger.info("Estate inserted (id=%d): %s", estate_id, estate_name)

        # --- Afdelings ---
        afdeling_id_map: dict[str, int] = {}   # AfdelName → afdelings.id

        for afdel_name, afdel_group in gdf.groupby("AfdelName"):
            afdel_num  = int(afdel_group["Afdeling"].iloc[0])
            afdel_code = f"AFL-{afdel_num}"

            cur.execute(
                """
                SELECT id FROM canopysense.afdelings
                WHERE estate_id = %s AND name = %s
                """,
                (estate_id, str(afdel_name)),
            )
            existing_afdel = cur.fetchone()

            if existing_afdel:
                afdel_id = existing_afdel[0]
                logger.info("Afdeling already in DB (id=%d): %s", afdel_id, afdel_name)
            else:
                afdel_union_wkt = afdel_group.geometry.union_all().wkt
                cur.execute(
                    """
                    INSERT INTO canopysense.afdelings (estate_id, name, code, geometry)
                    VALUES (
                        %s, %s, %s,
                        ST_Multi(ST_GeomFromText(%s, 4326))
                    )
                    RETURNING id
                    """,
                    (estate_id, str(afdel_name), afdel_code, afdel_union_wkt),
                )
                afdel_id = cur.fetchone()[0]
                logger.info("Afdeling inserted (id=%d): %s", afdel_id, afdel_name)

            afdeling_id_map[str(afdel_name)] = afdel_id

        # --- Blocks ---
        inserted = 0
        skipped  = 0

        for _, row in gdf.iterrows():
            block_code  = f"BLK-{int(row['OBJECTID']):03d}"
            block_name  = str(row["Blok"])
            plant_year  = int(row["Tahun"]) if pd.notna(row["Tahun"]) else None
            clone_type  = str(row["Existing"]) if pd.notna(row.get("Existing")) else None
            afdel_id    = afdeling_id_map[str(row["AfdelName"])]
            geom_wkt    = row["geometry"].wkt

            cur.execute(
                "SELECT id FROM canopysense.blocks WHERE code = %s",
                (block_code,),
            )
            if cur.fetchone():
                skipped += 1
                continue

            cur.execute(
                """
                INSERT INTO canopysense.blocks
                    (afdeling_id, name, code, geometry, plant_year, clone_type)
                VALUES (
                    %s, %s, %s,
                    ST_GeomFromText(%s, 4326),
                    %s, %s
                )
                """,
                (afdel_id, block_name, block_code, geom_wkt, plant_year, clone_type),
            )
            inserted += 1

        conn.commit()
        logger.info(
            "Block seeding done: %d inserted | %d already existed.", inserted, skipped
        )


# ---------------------------------------------------------------------------
# Block loader
# ---------------------------------------------------------------------------

def _load_blocks_from_db(
    conn: psycopg2.extensions.connection,
) -> gpd.GeoDataFrame:
    """
    Load all blocks from canopysense.blocks including display attributes.
    Returns GeoDataFrame with columns:
      block_id, name, code, plant_year, clone_type, geometry (EPSG:4326).
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                id          AS block_id,
                name,
                code,
                plant_year,
                clone_type,
                ST_AsGeoJSON(geometry) AS geojson
            FROM canopysense.blocks
            ORDER BY id
            """
        )
        rows = cur.fetchall()

    if not rows:
        return gpd.GeoDataFrame(columns=["block_id", "name", "code", "plant_year", "clone_type", "geometry"])

    from shapely.geometry import shape

    records = [
        {
            "block_id":   block_id,
            "name":       name,
            "code":       code,
            "plant_year": plant_year,
            "clone_type": clone_type,
            "geometry":   shape(json.loads(geojson)),
        }
        for block_id, name, code, plant_year, clone_type, geojson in rows
    ]
    return gpd.GeoDataFrame(records, crs="EPSG:4326")


# ---------------------------------------------------------------------------
# AOI builder
# ---------------------------------------------------------------------------

def _build_aoi(blocks_gdf: gpd.GeoDataFrame) -> ee.Geometry:
    """Build an ee.Geometry from the union of all block geometries."""
    union = blocks_gdf.geometry.union_all()
    return ee.Geometry(mapping(union))


# ---------------------------------------------------------------------------
# Blocks GeoJSON builder — for HTML map overlay
# ---------------------------------------------------------------------------

def _build_blocks_geojson(
    blocks_gdf: gpd.GeoDataFrame,
    passed_block_ids: set[int],
) -> dict:
    """
    Build a GeoJSON FeatureCollection from the blocks GeoDataFrame.
    Each feature includes display properties and a `has_data` flag
    indicating whether that block passed the FR-03 quality gate.

    Args:
        blocks_gdf:       GeoDataFrame with block_id, name, code, plant_year,
                          clone_type, geometry columns.
        passed_block_ids: Set of block_id integers that passed FR-03 and
                          have data in satellite_data.

    Returns:
        GeoJSON FeatureCollection dict — safe to embed in HTML as a JS variable.
    """
    features = []
    for _, row in blocks_gdf.iterrows():
        block_id = int(row["block_id"])
        features.append({
            "type": "Feature",
            "geometry": mapping(row["geometry"]),
            "properties": {
                "block_id":   block_id,
                "code":       row.get("code") or "",
                "name":       row.get("name") or "",
                "plant_year": int(row["plant_year"]) if row.get("plant_year") is not None and str(row.get("plant_year")) != "nan" else None,
                "clone_type": row.get("clone_type") or "—",
                "has_data":   block_id in passed_block_ids,
            },
        })
    return {"type": "FeatureCollection", "features": features}


# ---------------------------------------------------------------------------
# Synchronous GEE extraction → local CSV (no GCS)
# ---------------------------------------------------------------------------

def _extract_to_local_csv(
    image: ee.Image,
    blocks_gdf: gpd.GeoDataFrame,
    sensor: str,
    acquisition_date: str,
    scene_low_quality: bool,
) -> tuple[str, set[int]]:
    """
    Compute mean vegetation index values per block via synchronous
    reduceRegions().getInfo() and write results as a local CSV.

    No GCS or ee.batch.Export is used. Data flows:
      GEE server-side reduceRegions → Python .getInfo() → pandas → CSV

    FR-03 quality gate (valid_pixel_ratio >= 0.2) applied in Python.
    FR-08 schema applied: all columns match canopysense.satellite_data DDL.
    FR-07: ndre is None for Landsat records.

    Args:
        image:             Processed image with all index bands.
        blocks_gdf:        GeoDataFrame with block_id + geometry columns.
        sensor:            "S2", "L8", or "L9".
        acquisition_date:  Actual scene acquisition date (ISO string).
        scene_low_quality: Scene-level low_quality flag (FR-07).

    Returns:
        Tuple of (csv_path, passed_block_ids).
        csv_path is empty string if no valid blocks passed the quality gate.
        passed_block_ids is the set of block_id integers that passed FR-03.
    """
    scale       = _SCALE_S2 if sensor == "S2" else _SCALE_LS
    sensor_name = _SENSOR_NAMES[sensor]

    # Attach valid_mask band for per-block valid_pixel_ratio (FR-03)
    image_with_mask = build_valid_mask_band(image)

    index_bands = ["valid_mask", "ndvi", "evi", "savi", "gndvi"]
    if sensor == "S2":
        index_bands.append("ndre")

    # Build EE FeatureCollection — one feature per block with block_id property
    ee_features = [
        ee.Feature(
            ee.Geometry(mapping(row["geometry"])),
            {"block_id": int(row["block_id"])},
        )
        for _, row in blocks_gdf.iterrows()
    ]
    ee_collection = ee.FeatureCollection(ee_features)

    logger.info(
        "Running reduceRegions: %d blocks | sensor=%s | scale=%dm",
        len(blocks_gdf), sensor, scale,
    )

    reduced = (
        image_with_mask.select(index_bands)
        .reduceRegions(
            collection=ee_collection,
            reducer=ee.Reducer.mean(),
            scale=scale,
            tileScale=4,
        )
    )

    # Pull all results to Python in a single .getInfo() call
    result_info = reduced.getInfo()
    features    = result_info.get("features", [])
    logger.info("reduceRegions returned %d features.", len(features))

    # Apply FR-03 quality gate + build FR-08 schema rows
    rows: list[dict] = []
    skipped = 0

    for feat in features:
        props      = feat.get("properties", {})
        block_id   = props.get("block_id")
        valid_ratio = props.get("valid_mask")

        if valid_ratio is None or valid_ratio < VALID_PIXEL_RATIO_THRESHOLD:
            logger.debug(
                "Block %s skipped — valid_pixel_ratio=%s (threshold=%.1f).",
                block_id, valid_ratio, VALID_PIXEL_RATIO_THRESHOLD,
            )
            skipped += 1
            continue

        cloud_cover  = round((1.0 - valid_ratio) * 100, 2)
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

    logger.info(
        "Quality gate result: %d blocks passed | %d skipped (valid_pixel_ratio < %.1f).",
        len(rows), skipped, VALID_PIXEL_RATIO_THRESHOLD,
    )

    passed_block_ids: set[int] = {int(r["block_id"]) for r in rows}

    if not rows:
        return "", set()

    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = _OUTPUT_DIR / f"canopysense_{acquisition_date}.csv"

    column_order = [
        "block_id", "acquisition_date", "sensor", "cloud_cover",
        "ndvi", "evi", "ndre", "savi", "gndvi", "features",
    ]
    df = pd.DataFrame(rows, columns=column_order)
    df.to_csv(csv_path, index=False)
    logger.info("CSV saved: %s (%d rows)", csv_path.name, len(df))
    return str(csv_path), passed_block_ids


# ---------------------------------------------------------------------------
# DB connection
# ---------------------------------------------------------------------------

def _get_db_connection() -> psycopg2.extensions.connection:
    """
    Build a psycopg2 connection, loading 04_Test/.env first if present.
    Required env vars: PGDATABASE, PGUSER, PGPASSWORD.
    Optional env vars: PGHOST (default: localhost), PGPORT (default: 5432).
    """
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
# Scheduler stub (SCHEDULER_ENABLED=false by default)
# ---------------------------------------------------------------------------

def _run_scheduler() -> None:
    """
    Weekly scheduler — keeps the process alive and triggers run_pipeline()
    every 7 days. Activated by setting SCHEDULER_ENABLED=true in .env.

    To enable on a server:
      1. Set SCHEDULER_ENABLED=true in 04_Test/.env
      2. Ensure blocks table is already seeded (run with --seed-shapefile once)
      3. Run: python 03_Build/engine_launcher.py
         The process stays alive and fires every 7 days automatically.
    """
    import time

    try:
        import schedule
    except ImportError:
        logger.error(
            "'schedule' package is not installed. "
            "Run: pip install schedule"
        )
        sys.exit(1)

    logger.info("Scheduler mode ACTIVE — pipeline will run every 7 days.")

    # Register the weekly job
    schedule.every(7).days.do(run_pipeline)

    # Run immediately on startup, then follow the schedule
    logger.info("Running pipeline immediately on scheduler startup...")
    run_pipeline()

    logger.info("Entering scheduler loop — next run in 7 days.")
    while True:
        schedule.run_pending()
        time.sleep(3600)   # wake up every hour to check the schedule


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "CanopySense Engine Launcher — "
            "full GEE extraction → HTML preview → PostGIS ingestion pipeline."
        )
    )
    parser.add_argument(
        "--seed-shapefile",
        metavar="PATH",
        default=None,
        help=(
            "Path to a block-level shapefile for one-time DB seeding. "
            "Seeds canopysense.estates, afdelings, and blocks, then runs the pipeline. "
            "Omit on all subsequent runs — blocks are read from the DB."
        ),
    )
    return parser.parse_args()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )

    args = _parse_args()

    # Load .env early so SCHEDULER_ENABLED is available
    if _ENV_FILE.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(_ENV_FILE, override=False)
        except ImportError:
            pass

    scheduler_enabled = os.environ.get("SCHEDULER_ENABLED", "false").lower() == "true"

    if scheduler_enabled:
        _run_scheduler()
    else:
        run_pipeline(seed_shapefile=args.seed_shapefile)

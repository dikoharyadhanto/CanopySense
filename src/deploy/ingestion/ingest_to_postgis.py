"""
ingest_to_postgis.py — Phase II: Data Ingestion Pipeline [FR-08].

Reads exported GCS CSV files (downloaded to a local directory) and inserts
records into the PostGIS `satellite_data` table.

CSV schema (exported by async_engine.py, aligned to satellite_data DDL):
  block_id         — INTEGER FK to blocks.id
  acquisition_date — ISO date string (YYYY-MM-DD)
  sensor           — "sentinel-2" | "landsat-8" | "landsat-9"
  cloud_cover      — NUMERIC(5,2) percentage
  ndvi             — FLOAT (DOUBLE PRECISION)
  evi              — FLOAT
  ndre             — FLOAT | NULL (Landsat records have empty string → NULL)
  savi             — FLOAT
  gndvi            — FLOAT
  features         — JSONB string: {"valid_pixel_ratio": <float>, "low_quality": <bool>}

DB Connection (read from environment variables or .env file):
  PGHOST      — PostgreSQL host       (default: localhost)
  PGPORT      — PostgreSQL port       (default: 5432)
  PGDATABASE  — Database name
  PGUSER      — DB username
  PGPASSWORD  — DB password

Conflict strategy:
  ON CONFLICT (block_id, acquisition_date) DO NOTHING.
  Assumes a UNIQUE constraint exists on (block_id, acquisition_date) in
  satellite_data. Re-running the script is idempotent.

Usage:
  python 03_Build/ingestion/ingest_to_postgis.py \\
      --input-dir 04_Test/result_output \\
      [--dry-run]

  Or call run_ingestion() programmatically.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import pathlib
import sys

import pandas as pd
import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# DB table target
# ---------------------------------------------------------------------------

_TABLE = "satellite_data"

# Ordered columns for the INSERT — must match FR-08 DDL exactly.
_COLUMNS = [
    "block_id",
    "acquisition_date",
    "sensor",
    "cloud_cover",
    "ndvi",
    "evi",
    "ndre",
    "savi",
    "gndvi",
    "features",
]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_ingestion(
    input_dir: str | pathlib.Path,
    dry_run: bool = False,
) -> dict:
    """
    Ingest all CSV files in input_dir into the PostGIS satellite_data table.

    Args:
        input_dir: Directory containing exported CSV files
                   (e.g. 04_Test/result_output/).
        dry_run:   If True, parse and validate data but do not write to DB.

    Returns:
        Summary dict: {"files_processed", "rows_loaded", "rows_skipped", "errors"}.
    """
    input_dir = pathlib.Path(input_dir)
    if not input_dir.is_dir():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    csv_files = sorted(input_dir.glob("*.csv"))
    if not csv_files:
        logger.warning("No CSV files found in: %s", input_dir)
        return {"files_processed": 0, "rows_loaded": 0, "rows_skipped": 0, "errors": []}

    logger.info("Found %d CSV file(s) in %s", len(csv_files), input_dir)

    # Load and merge all CSVs
    frames: list[pd.DataFrame] = []
    for csv_path in csv_files:
        logger.info("  Reading: %s", csv_path.name)
        df = _read_csv(csv_path)
        frames.append(df)

    combined = pd.concat(frames, ignore_index=True)
    logger.info("Total rows loaded from CSV: %d", len(combined))

    rows = _build_rows(combined)
    logger.info("Rows after parsing/validation: %d", len(rows))

    if dry_run:
        logger.info("[DRY-RUN] Skipping DB write. First 3 rows preview:")
        for row in rows[:3]:
            logger.info("  %s", row)
        return {
            "files_processed": len(csv_files),
            "rows_loaded": len(rows),
            "rows_skipped": len(combined) - len(rows),
            "errors": [],
        }

    conn = _get_db_connection()
    try:
        loaded, errors = _insert_rows(conn, rows)
    finally:
        conn.close()

    skipped = len(combined) - loaded - len(errors)
    summary = {
        "files_processed": len(csv_files),
        "rows_loaded": loaded,
        "rows_skipped": skipped,
        "errors": errors,
    }
    logger.info(
        "Ingestion complete: %d loaded | %d skipped (conflict) | %d errors",
        loaded, skipped, len(errors),
    )
    return summary


# ---------------------------------------------------------------------------
# Internal: CSV reading and row construction
# ---------------------------------------------------------------------------

def _read_csv(path: pathlib.Path) -> pd.DataFrame:
    """Read a single exported CSV, preserving empty strings for nullable columns."""
    df = pd.read_csv(path, dtype=str, keep_default_na=False)

    # Validate required columns are present
    missing = set(_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"CSV {path.name} is missing columns: {missing}")

    return df


def _build_rows(df: pd.DataFrame) -> list[tuple]:
    """
    Parse and cast each DataFrame row into a tuple matching _COLUMNS order.

    Type conversions:
      block_id         → int
      acquisition_date → str (psycopg2 accepts ISO date strings)
      sensor           → str
      cloud_cover      → float, rounded to 2 decimal places (NUMERIC(5,2))
      ndvi/evi/savi/gndvi → float
      ndre             → float | None (empty string → NULL for Landsat)
      features         → dict (parsed from JSON string → psycopg2.extras.Json)
    """
    rows: list[tuple] = []

    for idx, row in df.iterrows():
        try:
            block_id         = int(row["block_id"])
            acquisition_date = str(row["acquisition_date"]).strip()
            sensor           = str(row["sensor"]).strip()
            cloud_cover      = round(float(row["cloud_cover"]), 2)
            ndvi             = float(row["ndvi"])
            evi              = float(row["evi"])
            ndre             = _parse_nullable_float(row["ndre"])
            savi             = float(row["savi"])
            gndvi            = float(row["gndvi"])
            features_raw     = str(row["features"]).strip()
            features         = psycopg2.extras.Json(json.loads(features_raw))

            rows.append((
                block_id, acquisition_date, sensor, cloud_cover,
                ndvi, evi, ndre, savi, gndvi, features,
            ))

        except Exception as exc:
            logger.warning("Skipping row %d — parse error: %s | row=%s", idx, exc, dict(row))

    return rows


def _parse_nullable_float(value: str) -> float | None:
    """Return None for empty/null strings; otherwise parse as float."""
    stripped = str(value).strip()
    if stripped in ("", "None", "null", "NULL"):
        return None
    return float(stripped)


# ---------------------------------------------------------------------------
# Internal: DB connection and insert
# ---------------------------------------------------------------------------

def _get_db_connection() -> psycopg2.extensions.connection:
    """
    Build a psycopg2 connection from environment variables.
    Loads a .env file from 04_Test/.env if present (for local dev convenience).

    Required env vars: PGDATABASE, PGUSER, PGPASSWORD
    Optional env vars: PGHOST (default: localhost), PGPORT (default: 5432)
    """
    _load_dotenv_if_present()

    host     = os.environ.get("PGHOST", "localhost")
    port     = int(os.environ.get("PGPORT", 5432))
    database = os.environ.get("PGDATABASE", "")
    user     = os.environ.get("PGUSER", "")
    password = os.environ.get("PGPASSWORD", "")

    if not database or not user:
        raise EnvironmentError(
            "Missing required DB environment variables: PGDATABASE and PGUSER must be set."
        )

    logger.info("Connecting to PostGIS: %s@%s:%d/%s", user, host, port, database)
    conn = psycopg2.connect(
        host=host, port=port, dbname=database, user=user, password=password,
    )
    conn.autocommit = False
    return conn


def _load_dotenv_if_present() -> None:
    """
    Attempt to load 04_Test/.env for local development.
    Silently skipped if python-dotenv is not installed or file not found.
    """
    # Walk up from this file's location to find the project root
    project_root = pathlib.Path(__file__).parent.parent.parent
    env_file = project_root / "tests" / ".env"

    if not env_file.exists():
        return

    try:
        from dotenv import load_dotenv
        load_dotenv(env_file, override=False)   # override=False: env vars win over .env
        logger.debug("Loaded .env from: %s", env_file)
    except ImportError:
        pass  # python-dotenv not installed — rely on shell env vars


def _insert_rows(
    conn: psycopg2.extensions.connection,
    rows: list[tuple],
) -> tuple[int, list[str]]:
    """
    Bulk-insert rows into satellite_data using ON CONFLICT DO NOTHING.

    Uses execute_values for efficiency.
    Returns (rows_inserted, error_list).
    """
    col_list = ", ".join(_COLUMNS)

    inserted = 0
    errors: list[str] = []

    try:
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(
                cur,
                f"INSERT INTO {_TABLE} ({col_list}) VALUES %s"
                f" ON CONFLICT (block_id, acquisition_date, sensor) DO NOTHING",
                rows,
                page_size=500,
            )
            inserted = cur.rowcount if cur.rowcount >= 0 else len(rows)
        conn.commit()
        logger.info("Committed %d row(s) to %s.", inserted, _TABLE)

    except psycopg2.Error as exc:
        conn.rollback()
        error_msg = f"DB insert failed: {exc.pgcode} — {exc.pgerror}"
        logger.error(error_msg)
        errors.append(error_msg)

    return inserted, errors


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="CanopySense Phase II: Ingest GCS CSV exports into PostGIS satellite_data."
    )
    parser.add_argument(
        "--input-dir",
        default=str(pathlib.Path(__file__).parent.parent.parent / "tests" / "result_output"),
        help="Directory containing exported CSV files. "
             "Default: <project_root>/tests/result_output/",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and validate data without writing to the database.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )

    args = _parse_args()
    try:
        summary = run_ingestion(input_dir=args.input_dir, dry_run=args.dry_run)
        print("\n=== Ingestion Summary ===")
        print(f"  Files processed : {summary['files_processed']}")
        print(f"  Rows loaded     : {summary['rows_loaded']}")
        print(f"  Rows skipped    : {summary['rows_skipped']}")
        print(f"  Errors          : {len(summary['errors'])}")
        if summary["errors"]:
            for err in summary["errors"]:
                print(f"    ! {err}")
        sys.exit(0 if not summary["errors"] else 1)
    except Exception as exc:
        logger.error("Ingestion FAILED: %s", exc)
        sys.exit(1)

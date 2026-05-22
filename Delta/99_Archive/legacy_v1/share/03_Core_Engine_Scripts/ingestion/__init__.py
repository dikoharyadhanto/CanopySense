"""
CanopySense — Data Ingestion Pipeline (Phase II).

Reads exported CSV files from GCS (downloaded to local result_output/) and
inserts records into the PostGIS satellite_data table.
"""

from .ingest_to_postgis import run_ingestion

__all__ = ["run_ingestion"]

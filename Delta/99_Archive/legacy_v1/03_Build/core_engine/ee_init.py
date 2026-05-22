"""GEE initialization module.

Credential resolution order:
  1. EE_SERVICE_ACCOUNT_KEY      — path to Service Account JSON key file
  2. EE_SERVICE_ACCOUNT_KEY_JSON — SA JSON content as env-var string
  3. Fallback to OAuth (application default / ee.Authenticate)

Project ID resolution:
  - Caller argument → EE_PROJECT_ID env var → GEE default

No credentials are hard-coded in source code per security constraint.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile

import ee

logger = logging.getLogger(__name__)

_INITIALIZED = False


def initialize_ee(project: str | None = None) -> None:
    """
    Initialize Google Earth Engine. Idempotent — safe to call multiple times.

    Args:
        project: GEE Cloud project ID. Falls back to EE_PROJECT_ID env var.

    Raises:
        RuntimeError: If credentials are invalid or initialization fails.
    """
    global _INITIALIZED
    if _INITIALIZED:
        return

    project_id: str | None = project or os.environ.get("EE_PROJECT_ID")

    # --- Service Account: key file path ---
    key_path = os.environ.get("EE_SERVICE_ACCOUNT_KEY")
    if key_path:
        _init_from_key_file(key_path, project_id)
        _INITIALIZED = True
        return

    # --- Service Account: inline JSON string ---
    key_json_str = os.environ.get("EE_SERVICE_ACCOUNT_KEY_JSON")
    if key_json_str:
        _init_from_key_json(key_json_str, project_id)
        _INITIALIZED = True
        return

    # --- OAuth fallback ---
    _init_oauth(project_id)
    _INITIALIZED = True


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _init_from_key_file(key_path: str, project_id: str | None) -> None:
    """Initialize EE using a Service Account key file path."""
    with open(key_path, "r", encoding="utf-8") as fh:
        sa_data = json.load(fh)

    service_email = sa_data.get("client_email")
    if not service_email:
        raise RuntimeError(
            f"Service Account JSON at '{key_path}' is missing 'client_email'."
        )

    credentials = ee.ServiceAccountCredentials(email=service_email, key_file=key_path)
    _do_initialize(credentials, project_id)
    logger.info("EE initialized via Service Account key file.")


def _init_from_key_json(key_json_str: str, project_id: str | None) -> None:
    """
    Initialize EE using a Service Account JSON string (from env var).
    ServiceAccountCredentials requires a file path, so the JSON is written
    to a temporary file that is deleted immediately after initialization.
    """
    sa_data = json.loads(key_json_str)
    service_email = sa_data.get("client_email")
    if not service_email:
        raise RuntimeError(
            "EE_SERVICE_ACCOUNT_KEY_JSON is missing 'client_email'."
        )

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
        json.dump(sa_data, tmp)
        tmp_path = tmp.name

    try:
        credentials = ee.ServiceAccountCredentials(
            email=service_email, key_file=tmp_path
        )
        _do_initialize(credentials, project_id)
    finally:
        os.unlink(tmp_path)

    logger.info("EE initialized via Service Account inline JSON env var.")


def _init_oauth(project_id: str | None) -> None:
    """Initialize EE using OAuth (application default) credentials."""
    if project_id:
        ee.Initialize(project=project_id)
    else:
        ee.Initialize()
    logger.info("EE initialized via OAuth credentials.")


def _do_initialize(credentials, project_id: str | None) -> None:
    if project_id:
        ee.Initialize(credentials=credentials, project=project_id)
    else:
        ee.Initialize(credentials=credentials)

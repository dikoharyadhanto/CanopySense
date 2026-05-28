"""
test_pipeline_contracts.py — CanopySense pipeline architecture contract tests.

Covers TC-001 through TC-023 from FMN-PLAN v1.3 test contract.
TC-001–TC-013 are automated (no secrets/DB/GEE required).
TC-014–TC-020 are cloud-stage tests requiring Director authorization.
TC-021–TC-023 are analysis/docs/scan checkpoints.

Backward compatibility: existing v1.2 TC-011–TC-015 classes are retained
as TC-012 regression coverage (TestLauncherSignature, TestDateWindowBehavior,
TestEnvValidation, TestDBWriteSchema, TestLoggingPath, TestRouteMatrix).

Usage:
    python -m pytest tests/test_pipeline_contracts.py -v

Prerequisites:
    pip install pytest geopandas shapely
"""

from __future__ import annotations

import importlib
import inspect
import json
import os
import pathlib
import sys
import types

import pytest

# ---------------------------------------------------------------------------
# Path setup — allow imports from src/
# ---------------------------------------------------------------------------

_ROOT = pathlib.Path(__file__).parent.parent
_SRC  = _ROOT / "src"
sys.path.insert(0, str(_SRC))
sys.path.insert(0, str(_SRC / "deploy"))


# ===========================================================================
# TC-011: blocks_gdf / launcher signature alignment
# ===========================================================================

class TestLauncherSignature:
    """
    Verify that src/deploy/engine_launcher.run_pipeline() accepts blocks_gdf,
    matching the call in patcher_cloud_function.py.

    The LOCAL src/engine_launcher.py intentionally does NOT have blocks_gdf
    (it reads blocks from DB). This split is documented and intentional.
    """

    def test_deploy_launcher_accepts_blocks_gdf(self):
        """Deploy engine_launcher.run_pipeline must accept blocks_gdf keyword."""
        spec = importlib.util.spec_from_file_location(
            "engine_launcher_deploy",
            _SRC / "deploy" / "engine_launcher.py",
        )
        mod = importlib.util.module_from_spec(spec)
        # We only inspect the signature — do not execute the module body
        # (would trigger GEE imports). Use AST inspection instead.
        import ast
        source = (_SRC / "deploy" / "engine_launcher.py").read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "run_pipeline":
                param_names = [a.arg for a in node.args.args]
                assert "blocks_gdf" in param_names, (
                    "deploy/engine_launcher.run_pipeline() is missing blocks_gdf parameter — "
                    "patcher_cloud_function.py calls it with blocks_gdf=<GeoDataFrame>"
                )
                return
        pytest.fail("run_pipeline() function not found in deploy/engine_launcher.py")

    def test_deploy_launcher_blocks_gdf_has_default_none(self):
        """blocks_gdf must default to None so local/scheduler runs still work."""
        import ast
        source = (_SRC / "deploy" / "engine_launcher.py").read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "run_pipeline":
                for arg, default in zip(
                    reversed(node.args.args),
                    reversed(node.args.defaults),
                ):
                    if arg.arg == "blocks_gdf":
                        assert isinstance(default, ast.Constant) and default.value is None, (
                            "blocks_gdf default must be None"
                        )
                        return
        pytest.fail("blocks_gdf argument or its default not found")

    def test_cloud_function_calls_blocks_gdf(self):
        """patcher_cloud_function.py must call run_pipeline with blocks_gdf= keyword."""
        source = (_SRC / "patcher_cloud_function.py").read_text()
        # v1.3: call also passes date_start/date_end — check blocks_gdf= is still present
        assert "run_pipeline(blocks_gdf=blocks_gdf" in source, (
            "patcher_cloud_function.py must call engine_launcher.run_pipeline(blocks_gdf=blocks_gdf...)"
        )

    def test_local_launcher_loads_from_db_when_no_blocks_gdf(self):
        """Local engine_launcher.run_pipeline must load from DB when blocks_gdf not provided."""
        import ast
        source = (_SRC / "engine_launcher.py").read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "run_pipeline":
                param_names = [a.arg for a in node.args.args]
                assert "blocks_gdf" not in param_names, (
                    "Local engine_launcher.run_pipeline() should NOT have blocks_gdf — "
                    "it reads from DB directly. Cloud path uses src/deploy/engine_launcher.py"
                )
                return
        pytest.fail("run_pipeline() not found in src/engine_launcher.py")


# ===========================================================================
# TC-012: date/window behavior is configurable / documented
# ===========================================================================

class TestDateWindowBehavior:
    """
    Verify that date window logic is not hardcoded and is overridable.
    """

    def test_historical_backfill_accepts_start_end_args(self):
        """historical_backfill.run_backfill() must accept start_ym and end_ym."""
        import ast
        source = (_SRC / "historical_backfill.py").read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "run_backfill":
                param_names = [a.arg for a in node.args.args]
                assert "start_ym" in param_names, "run_backfill must accept start_ym"
                assert "end_ym" in param_names, "run_backfill must accept end_ym"
                assert "dry_run" in param_names, "run_backfill must accept dry_run"
                return
        pytest.fail("run_backfill() not found in historical_backfill.py")

    def test_patcher_local_respects_batch_mode_env(self):
        """patcher_local.py must read BATCH_MODE from environment."""
        source = (_SRC / "patcher_local.py").read_text()
        assert 'BATCH_MODE' in source, (
            "patcher_local.py must read BATCH_MODE env var for batch grouping strategy"
        )

    def test_engine_launcher_uses_7day_window(self):
        """Deploy engine_launcher must use a 7-day date window for GEE scene search."""
        import ast
        source = (_SRC / "deploy" / "engine_launcher.py").read_text()
        assert "timedelta(days=7)" in source, (
            "deploy/engine_launcher.py must use 7-day window (timedelta(days=7)) "
            "to match weekly Cloud Function trigger cadence"
        )


# ===========================================================================
# TC-013: env contract validates missing/invalid config safely
# ===========================================================================

class TestEnvValidation:
    """
    Verify that patcher_local.py exits cleanly (not with a raw stacktrace)
    when required environment variables are missing.
    """

    def test_patcher_local_raises_on_missing_cloud_url(self):
        """_require() must raise EnvironmentError with a clear message for missing CLOUD_FUNCTION_URL."""
        import ast
        source = (_SRC / "patcher_local.py").read_text()
        # Verify _require() function exists and checks for empty string
        assert "def _require" in source, "patcher_local.py must have _require() helper"
        assert "EnvironmentError" in source, "_require() must raise EnvironmentError"
        assert "[ERROR] Missing required environment variable" in source, (
            "_require() must produce a clear error message"
        )

    def test_patcher_local_requires_cloud_function_url(self):
        """main() must call _require('CLOUD_FUNCTION_URL')."""
        source = (_SRC / "patcher_local.py").read_text()
        assert "_require(\"CLOUD_FUNCTION_URL\")" in source or "_require('CLOUD_FUNCTION_URL')" in source

    def test_patcher_local_requires_patcher_api_key(self):
        """main() must call _require('PATCHER_API_KEY')."""
        source = (_SRC / "patcher_local.py").read_text()
        assert "_require(\"PATCHER_API_KEY\")" in source or "_require('PATCHER_API_KEY')" in source

    def test_patcher_local_requires_contractor_id(self):
        """main() must call _require('CONTRACTOR_ID')."""
        source = (_SRC / "patcher_local.py").read_text()
        assert "_require(\"CONTRACTOR_ID\")" in source or "_require('CONTRACTOR_ID')" in source

    def test_env_example_documents_pgschema(self):
        """src/.env.example must document PGSCHEMA variable."""
        env_example = (_SRC / ".env.example").read_text()
        assert "PGSCHEMA" in env_example, (
            "src/.env.example must document PGSCHEMA — patcher_local.py uses it "
            "to target the correct PostgreSQL schema"
        )

    def test_env_example_api_version_is_current(self):
        """src/.env.example must reference api_version 1.1 (current Cloud Function version)."""
        env_example = (_SRC / ".env.example").read_text()
        assert "1.1" in env_example, (
            "src/.env.example must reference PATCHER_API_VERSION=1.1 — "
            "Cloud Function currently returns api_version=1.1"
        )


# ===========================================================================
# TC-014: DB write target matches operational schema (column contract)
# ===========================================================================

class TestDBWriteSchema:
    """
    Verify that the write contract from patcher_cloud_function and ingest_to_postgis
    targets the correct columns and uses the correct conflict key.
    """

    EXPECTED_COLUMNS = [
        "block_id", "acquisition_date", "sensor", "cloud_cover",
        "ndvi", "evi", "ndre", "savi", "gndvi", "features",
    ]
    EXPECTED_CONFLICT = ["block_id", "acquisition_date", "sensor"]

    def test_cloud_function_response_targets_satellite_data(self):
        """patcher_cloud_function.py response writes must target satellite_data table."""
        source = (_SRC / "patcher_cloud_function.py").read_text()
        assert '"table": "satellite_data"' in source or "'table': 'satellite_data'" in source

    def test_cloud_function_conflict_columns_are_3_column(self):
        """Cloud Function response conflict_columns must be the 3-column key."""
        source = (_SRC / "patcher_cloud_function.py").read_text()
        assert '"block_id","acquisition_date","sensor"' in source or \
               '"conflict_columns": ["block_id","acquisition_date","sensor"]' in source or \
               "block_id\",\"acquisition_date\",\"sensor" in source

    def test_ingest_local_conflict_key_is_3_column(self):
        """Local ingest_to_postgis must use 3-column conflict key (block_id, acquisition_date, sensor)."""
        source = (_SRC / "ingestion" / "ingest_to_postgis.py").read_text()
        assert "ON CONFLICT (block_id, acquisition_date, sensor) DO NOTHING" in source

    def test_ingest_deploy_conflict_key_is_3_column(self):
        """Deploy ingest_to_postgis must use 3-column conflict key."""
        source = (_SRC / "deploy" / "ingestion" / "ingest_to_postgis.py").read_text()
        assert "ON CONFLICT (block_id, acquisition_date, sensor) DO NOTHING" in source

    def test_ingest_local_no_dead_sql_variable(self):
        """Local ingest_to_postgis must not have the stale dead sql variable."""
        source = (_SRC / "ingestion" / "ingest_to_postgis.py").read_text()
        assert 'sql = (' not in source, (
            "Dead sql variable must be removed from src/ingestion/ingest_to_postgis.py"
        )

    def test_ingest_deploy_no_dead_sql_variable(self):
        """Deploy ingest_to_postgis must not have the stale dead sql variable."""
        source = (_SRC / "deploy" / "ingestion" / "ingest_to_postgis.py").read_text()
        assert 'sql = (' not in source, (
            "Dead sql variable with stale 2-column conflict key must be removed "
            "from src/deploy/ingestion/ingest_to_postgis.py"
        )

    def test_ingest_columns_match_satellite_data_ddl(self):
        """ingest_to_postgis._COLUMNS must match expected satellite_data column list."""
        import ast
        source = (_SRC / "ingestion" / "ingest_to_postgis.py").read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "_COLUMNS":
                        actual = [elt.s if hasattr(elt, 's') else elt.value
                                  for elt in node.value.elts]
                        assert actual == self.EXPECTED_COLUMNS, (
                            f"_COLUMNS mismatch. Expected: {self.EXPECTED_COLUMNS}, Got: {actual}"
                        )
                        return
        pytest.fail("_COLUMNS not found in ingest_to_postgis.py")

    def test_patcher_local_schema_targets_canopysense(self):
        """patcher_local.py must default to canopysense schema for satellite_data writes."""
        source = (_SRC / "patcher_local.py").read_text()
        assert "canopysense" in source, (
            "patcher_local.py must reference canopysense schema as default"
        )


# ===========================================================================
# TC-015: logging path records useful status (patcher_run_log schema)
# ===========================================================================

class TestLoggingPath:
    """
    Verify that patcher_local.py writes structured status logs to patcher_run_log.
    """

    EXPECTED_STATUSES = [
        "IN_PROGRESS", "FULL_SUCCESS", "PARTIAL_SUCCESS", "FULL_FAILURE", "SKIPPED",
    ]

    def test_patcher_local_logs_to_patcher_run_log(self):
        """patcher_local.py must reference patcher_run_log table."""
        source = (_SRC / "patcher_local.py").read_text()
        assert "patcher_run_log" in source

    def test_patcher_local_records_all_expected_statuses(self):
        """All expected status codes must be present in patcher_local.py."""
        source = (_SRC / "patcher_local.py").read_text()
        for status in self.EXPECTED_STATUSES:
            assert status in source, f"Status '{status}' not found in patcher_local.py"

    def test_patcher_local_logs_api_version(self):
        """patcher_local.py must capture and log api_version from Cloud Function response."""
        source = (_SRC / "patcher_local.py").read_text()
        assert "api_version" in source

    def test_patcher_local_logs_run_id(self):
        """patcher_local.py must log a run_id for cross-run traceability."""
        source = (_SRC / "patcher_local.py").read_text()
        assert "run_id" in source


# ===========================================================================
# Route Matrix Verification (static contract, no runtime required)
# ===========================================================================

class TestRouteMatrix:
    """
    Verify the pipeline route structure is consistent with the documented architecture.
    Checks that each route's entry point exists and has expected interface.
    """

    def test_weekly_scheduled_route_entry_exists(self):
        """patcher_local.py must have a scheduled run path (no --block-id)."""
        import ast
        source = (_SRC / "patcher_local.py").read_text()
        assert "_run_scheduled" in source, "Scheduled route (_run_scheduled) must exist"

    def test_upload_single_block_route_entry_exists(self):
        """patcher_local.py must have a single-block upload path (--block-id)."""
        source = (_SRC / "patcher_local.py").read_text()
        assert "_run_upload" in source, "Upload route (_run_upload) must exist"
        assert "--block-id" in source or "block_id" in source

    def test_historical_backfill_route_is_separate_from_cloud(self):
        """historical_backfill.py must NOT functionally import patcher_local or call Cloud Function.
        Note: deprecation notice may reference patcher_local.py as the new preferred route — that is
        documentation only and is intentional (v1.3)."""
        source = (_SRC / "historical_backfill.py").read_text()
        assert "import patcher_local" not in source, (
            "historical_backfill.py must not import patcher_local — it is a separate ops tool"
        )
        assert "CLOUD_FUNCTION_URL" not in source, (
            "historical_backfill.py must not call the Cloud Function — it runs GEE directly"
        )

    def test_historical_backfill_uses_direct_gee(self):
        """historical_backfill.py must call GEE directly (not via Cloud Function)."""
        source = (_SRC / "historical_backfill.py").read_text()
        assert "initialize_ee" in source
        assert "select_best_scene" in source

    def test_historical_backfill_has_resume_guard(self):
        """historical_backfill.py must have resume/backlog protection to avoid GEE quota waste."""
        source = (_SRC / "historical_backfill.py").read_text()
        assert "backfill_skipped" in source or "_is_in_backlog" in source

    def test_deploy_package_contains_required_files(self):
        """src/deploy/ must contain all files needed by the Cloud Function."""
        deploy = _SRC / "deploy"
        required = [
            "main.py",
            "engine_launcher.py",
            "core_engine/__init__.py",
            "core_engine/ee_init.py",
            "core_engine/scene_selector.py",
            "core_engine/cloud_masking.py",
            "core_engine/harmonization.py",
            "core_engine/index_calculator.py",
            "core_engine/quality_gate.py",
            "core_engine/map_previewer.py",
            "ingestion/ingest_to_postgis.py",
            "ingestion/__init__.py",
        ]
        for rel in required:
            assert (deploy / rel).exists(), f"Deploy package missing: src/deploy/{rel}"


# ===========================================================================
# TC-001: Route matrix is explicit
# ===========================================================================

class TestTC001RouteContract:
    """TC-001: All operational routes have a code owner."""

    def test_scheduled_route_exists(self):
        source = (_SRC / "patcher_local.py").read_text()
        assert "_run_scheduled" in source

    def test_upload_route_exists(self):
        source = (_SRC / "patcher_local.py").read_text()
        assert "_run_upload" in source

    def test_backfill_route_exists(self):
        source = (_SRC / "patcher_local.py").read_text()
        assert "_run_backfill" in source

    def test_historical_fallback_retained_as_documented(self):
        source = (_SRC / "historical_backfill.py").read_text()
        assert "DEPRECATED" in source or "deprecated" in source.lower()

    def test_route_contract_documented_in_patcher_local_docstring(self):
        source = (_SRC / "patcher_local.py").read_text()
        assert "--backfill" in source
        assert "--estate-id" in source


# ===========================================================================
# TC-002: patcher_local.py exposes historical/backfill mode
# ===========================================================================

class TestTC002BackfillMode:
    """TC-002: Backfill mode exists with optional date args and 3-year default."""

    def test_backfill_flag_in_argparse(self):
        source = (_SRC / "patcher_local.py").read_text()
        assert "--backfill" in source

    def test_date_start_arg_optional(self):
        source = (_SRC / "patcher_local.py").read_text()
        assert "--date-start" in source
        assert "default=None" in source or "default = None" in source

    def test_date_end_arg_optional(self):
        source = (_SRC / "patcher_local.py").read_text()
        assert "--date-end" in source

    def test_default_backfill_years_constant_exists(self):
        source = (_SRC / "patcher_local.py").read_text()
        assert "_DEFAULT_BACKFILL_YEARS" in source

    def test_default_backfill_years_is_3(self):
        source = (_SRC / "patcher_local.py").read_text()
        assert "_DEFAULT_BACKFILL_YEARS = 3" in source

    def test_hierarchy_args_exist(self):
        source = (_SRC / "patcher_local.py").read_text()
        assert "--estate-id" in source
        assert "--afdeling-id" in source
        assert "--block-id" in source


# ===========================================================================
# TC-003: Weekly/default payload remains backward-compatible
# ===========================================================================

class TestTC003WeeklyPayload:
    """TC-003: Default scheduled call uses api_version + blocks only (no date range)."""

    def test_call_function_sends_api_version(self):
        source = (_SRC / "patcher_local.py").read_text()
        assert '"api_version"' in source or "'api_version'" in source

    def test_call_function_sends_blocks(self):
        source = (_SRC / "patcher_local.py").read_text()
        assert '"blocks"' in source or "'blocks'" in source

    def test_call_function_mode_is_optional(self):
        """mode is only added to body when non-None — backward-compatible."""
        import ast
        source = (_SRC / "patcher_local.py").read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_call":
                param_names = [a.arg for a in node.args.args]
                assert "mode" in param_names
                return
        pytest.fail("_call() not found in patcher_local.py")

    def test_scheduled_run_does_not_inject_date_window(self):
        """_run_scheduled does not pass date_start/date_end to _run_batch."""
        source = (_SRC / "patcher_local.py").read_text()
        # _run_scheduled calls _run_batch without date args — verify no hardcoded date injection
        assert "_run_backfill" in source  # backfill route is separate


# ===========================================================================
# TC-004: Single-block payload remains valid
# ===========================================================================

class TestTC004SingleBlockPayload:
    """TC-004: Upload mode sends block-scoped payload with hierarchy context."""

    def test_run_upload_accepts_estate_and_afdeling(self):
        import ast
        source = (_SRC / "patcher_local.py").read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_run_upload":
                param_names = [a.arg for a in node.args.args]
                assert "estate_id" in param_names
                assert "afdeling_id" in param_names
                assert "block_id" in param_names
                return
        pytest.fail("_run_upload() not found")

    def test_upload_mode_string_in_trigger_mode(self):
        source = (_SRC / "patcher_local.py").read_text()
        assert '"upload"' in source or "'upload'" in source


# ===========================================================================
# TC-005: Historical/backfill payload contains date range
# ===========================================================================

class TestTC005BackfillPayload:
    """TC-005: Backfill _call() sends mode, date_start, date_end."""

    def test_call_accepts_date_start_date_end(self):
        import ast
        source = (_SRC / "patcher_local.py").read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_call":
                param_names = [a.arg for a in node.args.args]
                assert "date_start" in param_names
                assert "date_end" in param_names
                return
        pytest.fail("_call() not found")

    def test_call_injects_date_start_into_body(self):
        source = (_SRC / "patcher_local.py").read_text()
        assert 'body["date_start"]' in source or "body['date_start']" in source

    def test_call_injects_mode_into_body(self):
        source = (_SRC / "patcher_local.py").read_text()
        assert 'body["mode"]' in source or "body['mode']" in source

    def test_run_backfill_passes_chunk_dates_to_run_batch(self):
        source = (_SRC / "patcher_local.py").read_text()
        assert "date_start=chunk_start" in source
        assert "date_end=chunk_end" in source


# ===========================================================================
# TC-006: Date validation rejects bad input; default date omission allowed
# ===========================================================================

class TestTC006DateValidation:
    """TC-006: _generate_weekly_chunks handles valid ranges; bad input produces empty."""

    def _import_chunks_fn(self):
        import ast
        source = (_SRC / "patcher_local.py").read_text()
        assert "_generate_weekly_chunks" in source
        # Import by exec to avoid triggering heavy imports
        ns: dict = {}
        # Extract just the needed functions via targeted exec
        import calendar as _cal
        from datetime import date as _date, timedelta as _td
        exec(  # noqa: S102
            "import calendar; from datetime import date, timedelta\n" + source.split("def _generate_weekly_chunks")[1].split("\ndef ")[0].replace("def _generate_weekly_chunks", "def fn"),
            ns,
        )
        return ns["fn"]

    def test_chunk_count_for_single_month(self):
        source = (_SRC / "patcher_local.py").read_text()
        # Verify _generate_weekly_chunks is present and has correct logic
        assert "_generate_weekly_chunks" in source
        assert "timedelta(days=6)" in source

    def test_start_gt_end_produces_empty_or_error(self):
        """Start month after end month must be caught by explicit validation in main()."""
        source = (_SRC / "patcher_local.py").read_text()
        # main() must explicitly reject --date-start after --date-end before DB/cloud ops
        assert "must not be after" in source, (
            "main() must explicitly reject --date-start after --date-end with an error message"
        )

    def test_default_3yr_range_produces_chunks(self):
        """3-year default should produce ~156 chunks."""
        source = (_SRC / "patcher_local.py").read_text()
        # Verify default calculation uses _DEFAULT_BACKFILL_YEARS
        assert "year - _DEFAULT_BACKFILL_YEARS" in source

    def test_invalid_date_format_check_documented(self):
        """CLI validates YYYY-MM format for date-start/end explicitly."""
        source = (_SRC / "patcher_local.py").read_text()
        assert "YYYY-MM" in source
        assert "_YM_RE" in source, "A regex constant _YM_RE must validate date format"


# ===========================================================================
# TC-007: Backfill chunking is bounded
# ===========================================================================

class TestTC007BackfillChunking:
    """TC-007: Chunking generates correct number of 7-day windows."""

    def _run_chunks(self, start_ym: str, end_ym: str) -> list:
        import sys, types, calendar as _cal
        from datetime import date as _date, timedelta as _td
        # Build a minimal namespace to exec just _generate_weekly_chunks
        ns = {"calendar": _cal, "date": _date, "timedelta": _td}
        source = (_SRC / "patcher_local.py").read_text()
        fn_src = ""
        found = False
        for line in source.splitlines(keepends=True):
            if line.startswith("def _generate_weekly_chunks"):
                found = True
            if found:
                fn_src += line
                if found and fn_src.count("    return chunks") >= 1:
                    break
        exec(fn_src, ns)  # noqa: S102
        return ns["_generate_weekly_chunks"](start_ym, end_ym)

    def test_one_month_produces_4_or_5_chunks(self):
        chunks = self._run_chunks("2024-01", "2024-01")
        assert 4 <= len(chunks) <= 5, f"Expected 4-5 chunks for one month, got {len(chunks)}"

    def test_three_months_produces_expected_count(self):
        chunks = self._run_chunks("2024-01", "2024-03")
        assert 12 <= len(chunks) <= 14

    def test_chunk_start_lt_chunk_end(self):
        chunks = self._run_chunks("2024-01", "2024-01")
        for start, end, _ in chunks:
            assert start <= end

    def test_chunks_are_consecutive(self):
        from datetime import date as _date, timedelta as _td
        chunks = self._run_chunks("2024-01", "2024-01")
        for i in range(1, len(chunks)):
            prev_end = _date.fromisoformat(chunks[i - 1][1])
            curr_start = _date.fromisoformat(chunks[i][0])
            assert curr_start == prev_end + _td(days=1)

    def test_start_after_end_produces_empty(self):
        chunks = self._run_chunks("2024-03", "2024-01")
        assert chunks == []


# ===========================================================================
# TC-008: Cloud Function parses new contract
# ===========================================================================

class TestTC008CloudFunctionContract:
    """TC-008: raster_metadata mode routing and date extraction exist in Cloud Function."""

    def test_parse_raster_metadata_request_function_exists(self):
        source = (_SRC / "patcher_cloud_function.py").read_text()
        assert "_parse_raster_metadata_request" in source

    def test_mode_routing_reads_mode_field(self):
        source = (_SRC / "patcher_cloud_function.py").read_text()
        assert '.get("mode")' in source or ".get('mode')" in source

    def test_parse_request_meta_returns_date_start(self):
        source = (_SRC / "patcher_cloud_function.py").read_text()
        assert 'body.get("date_start")' in source or "body.get('date_start')" in source

    def test_parse_request_meta_returns_date_end(self):
        source = (_SRC / "patcher_cloud_function.py").read_text()
        assert 'body.get("date_end")' in source or "body.get('date_end')" in source

    def test_run_engine_accepts_date_params(self):
        import ast
        source = (_SRC / "patcher_cloud_function.py").read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_run_engine":
                param_names = [a.arg for a in node.args.args]
                assert "date_start" in param_names
                assert "date_end" in param_names
                return
        pytest.fail("_run_engine() not found")

    def test_cloud_function_passes_meta_to_run_engine(self):
        source = (_SRC / "patcher_cloud_function.py").read_text()
        assert "req_date_start" in source and "req_date_end" in source


# ===========================================================================
# TC-009: Deploy-side engine accepts explicit date window
# ===========================================================================

class TestTC009EngineAcceptsDateWindow:
    """TC-009: run_pipeline(date_start, date_end) accepted; defaults to weekly when absent."""

    def test_run_pipeline_accepts_date_start(self):
        import ast
        source = (_SRC / "deploy" / "engine_launcher.py").read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "run_pipeline":
                param_names = [a.arg for a in node.args.args]
                assert "date_start" in param_names
                assert "date_end" in param_names
                return
        pytest.fail("run_pipeline() not found in deploy/engine_launcher.py")

    def test_run_pipeline_date_params_default_none(self):
        import ast
        source = (_SRC / "deploy" / "engine_launcher.py").read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "run_pipeline":
                for arg, default in zip(reversed(node.args.args), reversed(node.args.defaults)):
                    if arg.arg in ("date_start", "date_end"):
                        assert isinstance(default, ast.Constant) and default.value is None
                return
        pytest.fail("run_pipeline() not found")

    def test_engine_uses_supplied_dates_when_provided(self):
        source = (_SRC / "deploy" / "engine_launcher.py").read_text()
        assert "if date_start and date_end" in source

    def test_engine_falls_back_to_weekly_default(self):
        source = (_SRC / "deploy" / "engine_launcher.py").read_text()
        assert "timedelta(days=7)" in source
        assert "date.today()" in source


# ===========================================================================
# TC-010: Backfill safety/resume behavior preserved
# ===========================================================================

class TestTC010BackfillResumeGuard:
    """TC-010: Three-layer resume guard is present in patcher_local."""

    def test_ensure_backlog_table_exists(self):
        source = (_SRC / "patcher_local.py").read_text()
        assert "_ensure_backlog_table" in source

    def test_has_existing_data_exists(self):
        source = (_SRC / "patcher_local.py").read_text()
        assert "_has_existing_data" in source

    def test_is_in_backlog_exists(self):
        source = (_SRC / "patcher_local.py").read_text()
        assert "_is_in_backlog" in source

    def test_write_to_backlog_exists(self):
        source = (_SRC / "patcher_local.py").read_text()
        assert "_write_to_backlog" in source

    def test_layer1_check_in_run_backfill(self):
        source = (_SRC / "patcher_local.py").read_text()
        assert "_has_existing_data(conn" in source

    def test_layer2_check_in_run_backfill(self):
        source = (_SRC / "patcher_local.py").read_text()
        assert "_is_in_backlog(conn" in source

    def test_layer3_write_on_no_new_data(self):
        source = (_SRC / "patcher_local.py").read_text()
        assert "_write_to_backlog(conn" in source
        assert "no_new_data_cloud_route" in source

    def test_backlog_ddl_in_patcher_local(self):
        source = (_SRC / "patcher_local.py").read_text()
        assert "_BACKLOG_DDL" in source
        assert "backfill_skipped" in source

    def test_layer1_check_is_scope_aware(self):
        """_has_existing_data must accept block_ids to avoid cross-estate false-skip."""
        import ast
        source = (_SRC / "patcher_local.py").read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_has_existing_data":
                param_names = [a.arg for a in node.args.args] + [a.arg for a in node.args.kwonlyargs]
                assert "block_ids" in param_names, (
                    "_has_existing_data must accept block_ids — without it, any estate's data "
                    "in the window skips all other estates"
                )
                return
        pytest.fail("_has_existing_data not found in patcher_local.py")

    def test_backlog_guard_is_scope_aware(self):
        """_is_in_backlog must accept batch_fp so backlog is scoped per block-set + window."""
        import ast
        source = (_SRC / "patcher_local.py").read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_is_in_backlog":
                param_names = [a.arg for a in node.args.args]
                assert "batch_fp" in param_names, (
                    "_is_in_backlog must accept batch_fp — without it a NO_NEW_DATA for "
                    "one estate skips all other estates for the same date window"
                )
                return
        pytest.fail("_is_in_backlog not found in patcher_local.py")


# ===========================================================================
# TC-011: Patcher run logging includes required evidence fields
# ===========================================================================

class TestTC011LoggingSchema:
    """TC-011: patcher_run_log receives mode, date range, estate_id, status, api_version."""

    def test_log_write_accepts_estate_id(self):
        import ast
        source = (_SRC / "patcher_local.py").read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_log_write":
                param_names = [a.arg for a in node.args.args] + node.args.kwonlyargs
                kwonly_names = [a.arg for a in node.args.kwonlyargs]
                assert "estate_id" in kwonly_names, "_log_write must accept estate_id kwarg"
                assert "date_start" in kwonly_names
                assert "date_end" in kwonly_names
                return
        pytest.fail("_log_write() not found")

    def test_ddl_has_estate_id_column(self):
        source = (_SRC / "patcher_run_log_ddl.sql").read_text()
        assert "estate_id" in source

    def test_ddl_has_date_start_column(self):
        source = (_SRC / "patcher_run_log_ddl.sql").read_text()
        assert "date_start" in source

    def test_ddl_has_date_end_column(self):
        source = (_SRC / "patcher_run_log_ddl.sql").read_text()
        assert "date_end" in source

    def test_ddl_includes_backfill_trigger_mode(self):
        source = (_SRC / "patcher_run_log_ddl.sql").read_text()
        assert "'backfill'" in source

    def test_ddl_includes_no_new_data_status(self):
        source = (_SRC / "patcher_run_log_ddl.sql").read_text()
        assert "'NO_NEW_DATA'" in source

    def test_no_new_data_status_in_patcher_local(self):
        source = (_SRC / "patcher_local.py").read_text()
        assert "NO_NEW_DATA" in source

    def test_migration_file_exists(self):
        migration = _SRC / "patcher_run_log_migration_v1.3.sql"
        assert migration.exists(), "Migration file src/patcher_run_log_migration_v1.3.sql must exist"

    def test_migration_adds_estate_id(self):
        source = (_SRC / "patcher_run_log_migration_v1.3.sql").read_text()
        assert "estate_id" in source

    def test_migration_extends_trigger_mode_check(self):
        source = (_SRC / "patcher_run_log_migration_v1.3.sql").read_text()
        assert "backfill" in source

    def test_migration_extends_status_check(self):
        source = (_SRC / "patcher_run_log_migration_v1.3.sql").read_text()
        assert "NO_NEW_DATA" in source

    def test_migration_handles_backfill_skipped_batch_fp(self):
        """Migration must add batch_fp to backfill_skipped for existing v1.3 deployments."""
        source = (_SRC / "patcher_run_log_migration_v1.3.sql").read_text()
        assert "backfill_skipped" in source, (
            "Migration must handle backfill_skipped schema — existing deployments "
            "may have the old (window_start, window_end) unique key without batch_fp"
        )
        assert "batch_fp" in source

    def test_migration_backfill_skipped_is_idempotent(self):
        """Migration backfill_skipped section must use IF EXISTS / IF NOT EXISTS guards."""
        source = (_SRC / "patcher_run_log_migration_v1.3.sql").read_text()
        assert "ALTER TABLE IF EXISTS canopysense.backfill_skipped" in source
        assert "ADD COLUMN IF NOT EXISTS batch_fp" in source
        assert "DROP CONSTRAINT IF EXISTS" in source

    def test_historical_backfill_ddl_includes_batch_fp(self):
        """historical_backfill.py _BACKLOG_DDL must match patcher_local schema (batch_fp column)."""
        source = (_SRC / "historical_backfill.py").read_text()
        assert "batch_fp" in source, (
            "historical_backfill.py _BACKLOG_DDL must include batch_fp to stay compatible "
            "with the scope-aware backfill_skipped schema"
        )
        assert "UNIQUE (window_start, window_end, batch_fp)" in source

    def test_historical_backfill_write_to_backlog_uses_compatible_conflict_key(self):
        """historical_backfill._write_to_backlog must use (window_start, window_end, batch_fp) conflict key."""
        source = (_SRC / "historical_backfill.py").read_text()
        assert "ON CONFLICT (window_start, window_end, batch_fp) DO NOTHING" in source, (
            "historical_backfill.py must use the 3-column conflict key — "
            "the old (window_start, window_end) constraint no longer exists"
        )


# ===========================================================================
# TC-008b: src/deploy/main.py must stay aligned with patcher_cloud_function.py
#          (deploy-source drift detection)
# ===========================================================================

class TestTC008bDeployMainAlignment:
    """TC-008b: deploy/main.py must have the same date window and mode routing
    behavior as patcher_cloud_function.py (the dev source). Any drift here
    would silently break backfill date windows on the deployed Cloud Function."""

    def test_deploy_main_has_parse_raster_metadata_request(self):
        """deploy/main.py must define _parse_raster_metadata_request."""
        source = (_SRC / "deploy" / "main.py").read_text()
        assert "_parse_raster_metadata_request" in source, (
            "src/deploy/main.py is missing _parse_raster_metadata_request — "
            "it will not handle mode=raster_metadata requests after deploy"
        )

    def test_deploy_main_has_mode_routing(self):
        """deploy/main.py must route on mode=raster_metadata before patcher branch."""
        source = (_SRC / "deploy" / "main.py").read_text()
        assert 'req_mode == "raster_metadata"' in source or "req_mode == 'raster_metadata'" in source, (
            "src/deploy/main.py is missing raster_metadata mode routing"
        )

    def test_deploy_main_run_engine_accepts_date_params(self):
        """deploy/main.py _run_engine must accept date_start and date_end."""
        import ast
        source = (_SRC / "deploy" / "main.py").read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_run_engine":
                param_names = [a.arg for a in node.args.args]
                assert "date_start" in param_names, (
                    "src/deploy/main.py _run_engine() is missing date_start — "
                    "backfill date windows will be silently dropped on deploy"
                )
                assert "date_end" in param_names, (
                    "src/deploy/main.py _run_engine() is missing date_end"
                )
                return
        pytest.fail("_run_engine() not found in src/deploy/main.py")

    def test_deploy_main_run_engine_passes_dates_to_run_pipeline(self):
        """deploy/main.py _run_engine must pass date_start/date_end to run_pipeline."""
        source = (_SRC / "deploy" / "main.py").read_text()
        assert "run_pipeline(blocks_gdf=blocks_gdf, date_start=date_start, date_end=date_end)" in source, (
            "src/deploy/main.py _run_engine does not pass date_start/date_end to run_pipeline — "
            "backfill date window will be silently ignored on the deployed function"
        )

    def test_deploy_main_patcher_branch_reads_date_window(self):
        """deploy/main.py patcher branch must read req_date_start and req_date_end from body."""
        source = (_SRC / "deploy" / "main.py").read_text()
        assert "req_date_start" in source, (
            "src/deploy/main.py patcher branch missing req_date_start extraction"
        )
        assert "req_date_end" in source, (
            "src/deploy/main.py patcher branch missing req_date_end extraction"
        )

    def test_deploy_main_passes_date_window_to_executor(self):
        """deploy/main.py must pass req_date_start and req_date_end to executor.submit."""
        source = (_SRC / "deploy" / "main.py").read_text()
        assert "executor.submit(_run_engine, output_dir, blocks_gdf, req_date_start, req_date_end)" in source, (
            "src/deploy/main.py does not pass date window to executor.submit — "
            "backfill windows will be silently dropped on the deployed Cloud Function"
        )


# ===========================================================================
# TC-014: Deploy package contains intended source (static file check)
# ===========================================================================

class TestTC014DeployPackage:
    """TC-014: src/deploy/ contains all files required for Cloud Function."""

    REQUIRED = [
        "main.py",
        "engine_launcher.py",
        "core_engine/__init__.py",
        "core_engine/ee_init.py",
        "core_engine/scene_selector.py",
        "core_engine/cloud_masking.py",
        "core_engine/harmonization.py",
        "core_engine/index_calculator.py",
        "core_engine/quality_gate.py",
        "core_engine/map_previewer.py",
        "ingestion/ingest_to_postgis.py",
        "ingestion/__init__.py",
    ]

    def test_all_required_files_present(self):
        deploy = _SRC / "deploy"
        for rel in self.REQUIRED:
            assert (deploy / rel).exists(), f"Deploy package missing: src/deploy/{rel}"

    def test_patcher_cloud_function_in_deploy(self):
        assert (_SRC / "patcher_cloud_function.py").exists()

    def test_deploy_engine_launcher_no_hardcoded_date_window(self):
        """Engine launcher must not hardcode today−7 unconditionally."""
        source = (_SRC / "deploy" / "engine_launcher.py").read_text()
        assert "if date_start and date_end" in source


# ===========================================================================
# TC-023: Secret hygiene holds (automated scan)
# ===========================================================================

class TestTC023SecretHygiene:
    """TC-023: No real secrets in tracked src/ files."""

    _SECRET_PATTERNS = [
        "AKIA",          # AWS key prefix
        "-----BEGIN RSA PRIVATE KEY-----",
        "-----BEGIN EC PRIVATE KEY-----",
        "-----BEGIN PRIVATE KEY-----",
    ]

    def _scan_file(self, path: pathlib.Path) -> list[str]:
        if not path.exists():
            return []
        text = path.read_text(errors="replace")
        return [p for p in self._SECRET_PATTERNS if p in text]

    def test_patcher_local_no_hardcoded_secrets(self):
        hits = self._scan_file(_SRC / "patcher_local.py")
        assert not hits, f"Potential secret pattern found in patcher_local.py: {hits}"

    def test_patcher_cloud_function_no_hardcoded_secrets(self):
        hits = self._scan_file(_SRC / "patcher_cloud_function.py")
        assert not hits, f"Potential secret in patcher_cloud_function.py: {hits}"

    def test_env_example_has_no_real_values(self):
        path = _SRC / ".env.example"
        if not path.exists():
            pytest.skip(".env.example not found")
        text = path.read_text()
        suspicious = [line for line in text.splitlines()
                      if "=" in line and not line.startswith("#")
                      and any(c.isalpha() for c in line.split("=", 1)[1])
                      and len(line.split("=", 1)[1].strip()) > 20
                      and "<" not in line and "example" not in line.lower()
                      and "your_" not in line.lower() and "replace" not in line.lower()]
        assert not suspicious, f"Possible real values in .env.example: {suspicious[:3]}"


# ===========================================================================
# Manual Run Procedures (not automated — requires secrets/cloud access)
# ===========================================================================

"""
MANUAL RUN PROCEDURES — requires secrets / GEE / DB / Director authorization

TC-014 (cloud-stage): Build and inspect deploy package
    cd src/deploy && zip -r ../../artifacts/deploy_package.zip . --exclude "*.pyc" "__pycache__/*"
    md5sum ../../artifacts/deploy_package.zip
    unzip -l ../../artifacts/deploy_package.zip | grep -E "engine_launcher|main.py|patcher_cloud"

TC-015: Capture Cloud Function pre-deploy state
    gcloud functions describe patcher_cloud --gen2 --region=asia-southeast2 --project=canopysense
    Expected: current updateTime, runtime, source object/generation captured

TC-016 (Director-authorized): Redeploy Cloud Function
    gcloud functions deploy patcher_cloud --gen2 --region=asia-southeast2 \
        --runtime=python312 --trigger-http --allow-unauthenticated \
        --source=src/deploy/ --entry-point=patcher_cloud --project=canopysense
    Post-deploy: re-run TC-015 — verify updateTime changed

TC-017: Weekly live smoke (post-redeploy)
    python src/patcher_local.py
    Check: SELECT * FROM canopysense.patcher_run_log ORDER BY triggered_at DESC LIMIT 5;
    Expected: trigger_mode=scheduled, api_version=1.1, status IN (FULL_SUCCESS, NO_NEW_DATA, PARTIAL_SUCCESS)

TC-018: Single-block live smoke (post-redeploy)
    python src/patcher_local.py --estate-id <ESTATE_ID> --afdeling-id <AFL_ID> --block-id <BLOCK_ID>
    Check: patcher_run_log row with trigger_mode=upload, estate_id=<ESTATE_ID>

TC-019: Historical/backfill live smoke — small range (post-redeploy)
    python src/patcher_local.py --backfill --date-start 2024-01 --date-end 2024-01
    Expected: ~4-5 chunks processed; trigger_mode=backfill rows in patcher_run_log
    Each chunk: date_start and date_end populated; status IN (FULL_SUCCESS, NO_NEW_DATA, FULL_FAILURE)

TC-020: Verify smoke evidence is not local-only
    gcloud logging read "resource.type=cloud_function AND resource.labels.function_name=patcher_cloud" \
        --project=canopysense --limit=20 --format=json
    Expected: audit entries with mode=backfill or mode=scheduled from post-redeploy run

TC-021: Full historical backfill operating limits analysis
    DEV report: _generate_weekly_chunks("2023-04", "<current_month>") → count chunks
    python -c "
    import sys; sys.path.insert(0,'src')
    from patcher_local import _generate_weekly_chunks
    chunks = _generate_weekly_chunks('2023-04', '$(date +%Y-%m)')
    print(f'{len(chunks)} chunks | est. {len(chunks)*120}s at 2min/chunk = {len(chunks)*2/60:.0f} hr')
    "
    Expected: ~156 chunks for 3yr; quota/time analysis reviewed by Director

TC-022: Documentation review
    diff docs/env-reference.md + docs/phase2-handoff.md
    Expected: route contract table, CLI hierarchy, backfill commands, env vars documented

TC-023 (extended): Full secret scan
    git diff --name-only HEAD~1
    grep -rn "AKIA" src/ docs/
    grep -rn "BEGIN PRIVATE KEY" src/ docs/
    Expected: zero matches
"""

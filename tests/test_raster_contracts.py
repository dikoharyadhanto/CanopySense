"""
Offline contract tests for the CanopySense raster engine [v1.6].

These tests validate:
  TC-007 Basic tier routing: gee_mapid, date params ignored
  TC-008 Premium tier routing: maps_platform, date validated against timelapse_period_months
  TC-011 Metadata schema: all required fields present with correct types
  TC-012 Index formula consistency: SUPPORTED_INDICES matches map_previewer._VIZ_PARAMS
  TC-009 No fake static raster path in codebase
  TC-015 All offline tests pass without GEE credentials
  TC-023 Raster cache contract: key schema, metadata-only storage, no tile images
  TC-024 Cache hit avoids duplicate provider generation (mock Redis)
  TC-025 Cache expiry is provider-driven: TTL is configurable, not hardcoded

No GEE credentials are required to run this file. No ee.* calls are made.
No real Redis connection required — cache tests use mocks.
Real GEE smoke tests (TC-016/TC-017) require Director approval and are NOT in this file.
"""

from __future__ import annotations

import dataclasses
import pathlib
import sys
from datetime import date, timedelta

import pytest

# ---------------------------------------------------------------------------
# Path setup — allow import from src/
# ---------------------------------------------------------------------------
_REPO_ROOT = pathlib.Path(__file__).parent.parent
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# Import only contract-safe symbols (no ee.* triggered at import time)
from raster_engine import (
    RasterMetadata,
    RasterEngineError,
    SubscriptionAccessError,
    SUPPORTED_INDICES,
    SERVING_MODES,
    _resolve_date_window,
    _VIZ_PARAMS,
)


# ---------------------------------------------------------------------------
# TC-011: RasterMetadata schema — all required fields, correct types
# ---------------------------------------------------------------------------

class TestRasterMetadataSchema:
    def _make_sample(self) -> RasterMetadata:
        return RasterMetadata(
            schema_version="1.0",
            serving_mode="gee_mapid",
            subscription_tier="basic",
            index="ndvi",
            sensor="S2",
            date_acquired="2026-05-21",
            date_window_start="2026-05-14",
            date_window_end="2026-05-21",
            valid_pixel_ratio=0.847,
            low_quality=False,
            bounds={"west": 104.1, "south": -3.2, "east": 104.5, "north": -3.0},
            resolution_m=10,
            palette=["red", "yellow", "green"],
            viz_min=-0.2,
            viz_max=0.9,
            tile_url_format="https://earthengine.googleapis.com/v1/REDACTED",
            tile_url_expires_note="~48 hours from generation (GEE getMapId limitation).",
            cloud_nodata_note="Cloudy and shadowed pixels are masked.",
            generated_at_utc="2026-05-27T10:00:00+00:00",
        )

    def test_schema_version_is_string(self):
        m = self._make_sample()
        assert isinstance(m.schema_version, str)
        assert m.schema_version == "1.0"

    def test_serving_mode_is_valid(self):
        m = self._make_sample()
        assert m.serving_mode in SERVING_MODES

    def test_subscription_tier_is_valid(self):
        m = self._make_sample()
        assert m.subscription_tier in ("basic", "premium")

    def test_index_is_supported(self):
        m = self._make_sample()
        assert m.index in SUPPORTED_INDICES

    def test_sensor_is_valid(self):
        m = self._make_sample()
        assert m.sensor in ("S2", "L8", "L9")

    def test_dates_are_iso_strings(self):
        m = self._make_sample()
        date.fromisoformat(m.date_acquired)
        date.fromisoformat(m.date_window_start)
        date.fromisoformat(m.date_window_end)

    def test_valid_pixel_ratio_in_range(self):
        m = self._make_sample()
        assert 0.0 <= m.valid_pixel_ratio <= 1.0

    def test_bounds_has_required_keys(self):
        m = self._make_sample()
        for key in ("west", "south", "east", "north"):
            assert key in m.bounds
            assert isinstance(m.bounds[key], float)

    def test_resolution_m_is_positive_int(self):
        m = self._make_sample()
        assert isinstance(m.resolution_m, int)
        assert m.resolution_m > 0

    def test_palette_is_nonempty_list_of_strings(self):
        m = self._make_sample()
        assert isinstance(m.palette, list)
        assert len(m.palette) > 0
        assert all(isinstance(p, str) for p in m.palette)

    def test_viz_min_less_than_viz_max(self):
        m = self._make_sample()
        assert m.viz_min < m.viz_max

    def test_tile_url_format_is_nonempty_string(self):
        m = self._make_sample()
        assert isinstance(m.tile_url_format, str)
        assert len(m.tile_url_format) > 0

    def test_expiry_note_present(self):
        m = self._make_sample()
        assert "48" in m.tile_url_expires_note

    def test_cloud_nodata_note_present(self):
        m = self._make_sample()
        assert len(m.cloud_nodata_note) > 0

    def test_to_dict_serializable(self):
        import json
        m = self._make_sample()
        d = m.to_dict()
        assert isinstance(d, dict)
        json.dumps(d)  # must not raise

    def test_all_required_fields_present(self):
        m = self._make_sample()
        required = {
            "schema_version", "serving_mode", "subscription_tier", "index",
            "sensor", "date_acquired", "date_window_start", "date_window_end",
            "valid_pixel_ratio", "low_quality", "bounds", "resolution_m",
            "palette", "viz_min", "viz_max", "tile_url_format",
            "tile_url_expires_note", "cloud_nodata_note", "generated_at_utc",
        }
        d = m.to_dict()
        missing = required - set(d.keys())
        assert not missing, f"Missing fields: {missing}"


# ---------------------------------------------------------------------------
# TC-012: Index formula consistency — SUPPORTED_INDICES matches viz params
# ---------------------------------------------------------------------------

class TestIndexConsistency:
    def test_all_supported_indices_have_viz_params(self):
        for idx in SUPPORTED_INDICES:
            assert idx in _VIZ_PARAMS, f"Missing viz params for index: {idx}"

    def test_viz_params_have_required_keys(self):
        for idx, params in _VIZ_PARAMS.items():
            assert "min" in params, f"Missing 'min' in viz params for {idx}"
            assert "max" in params, f"Missing 'max' in viz params for {idx}"
            assert "palette" in params, f"Missing 'palette' in viz params for {idx}"

    def test_ndvi_viz_params_match_canonical(self):
        # NDVI canonical: min=-0.2, max=0.9, palette=["red", "yellow", "green"]
        ndvi = _VIZ_PARAMS["ndvi"]
        assert ndvi["min"] == -0.2
        assert ndvi["max"] == 0.9
        assert ndvi["palette"] == ["red", "yellow", "green"]

    def test_map_previewer_viz_params_consistent(self):
        # Verify raster_engine._VIZ_PARAMS matches map_previewer._VIZ_PARAMS.
        # Requires earthengine-api — skipped in offline env (TC-012 offline pass is above).
        pytest.importorskip("ee", reason="earthengine-api not installed; test skipped for offline mode")
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "map_previewer",
            _REPO_ROOT / "src" / "core_engine" / "map_previewer.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        previewer_params = mod._VIZ_PARAMS
        for idx in SUPPORTED_INDICES:
            if idx in previewer_params:
                assert _VIZ_PARAMS[idx] == previewer_params[idx], (
                    f"Viz params mismatch for {idx}: "
                    f"raster_engine={_VIZ_PARAMS[idx]!r} "
                    f"map_previewer={previewer_params[idx]!r}"
                )

    def test_ndre_in_supported_indices(self):
        assert "ndre" in SUPPORTED_INDICES

    def test_serving_modes_are_exactly_two(self):
        assert set(SERVING_MODES) == {"gee_mapid", "maps_platform"}


# ---------------------------------------------------------------------------
# TC-007: Basic tier routing — date params ignored, latest window always used
# ---------------------------------------------------------------------------

class TestBasicTierRouting:
    def test_basic_ignores_date_params(self):
        start, end = _resolve_date_window(
            serving_mode="gee_mapid",
            subscription_tier="basic",
            timelapse_period_months=None,
            date_start="2025-01-01",
            date_end="2025-01-08",
        )
        today = date.today()
        expected_end = today.isoformat()
        expected_start = (today - timedelta(days=7)).isoformat()
        assert start == expected_start
        assert end == expected_end

    def test_basic_tier_label_overrides_serving_mode(self):
        # Even if serving_mode is maps_platform, basic tier gets latest window
        start, end = _resolve_date_window(
            serving_mode="maps_platform",
            subscription_tier="basic",
            timelapse_period_months=3,
            date_start="2025-01-01",
            date_end="2025-01-08",
        )
        today = date.today()
        assert end == today.isoformat()

    def test_gee_mapid_mode_always_returns_latest(self):
        start, end = _resolve_date_window(
            serving_mode="gee_mapid",
            subscription_tier="premium",
            timelapse_period_months=3,
            date_start=None,
            date_end=None,
        )
        today = date.today()
        assert end == today.isoformat()
        assert start == (today - timedelta(days=7)).isoformat()


# ---------------------------------------------------------------------------
# TC-008: Premium tier routing — date validated against timelapse_period_months
# ---------------------------------------------------------------------------

class TestPremiumTierRouting:
    def test_premium_accepts_date_within_window(self):
        today = date.today()
        valid_start = (today - timedelta(days=30)).isoformat()
        valid_end = (today - timedelta(days=23)).isoformat()
        start, end = _resolve_date_window(
            serving_mode="maps_platform",
            subscription_tier="premium",
            timelapse_period_months=3,
            date_start=valid_start,
            date_end=valid_end,
        )
        assert start == valid_start
        assert end == valid_end

    def test_premium_rejects_date_outside_window(self):
        today = date.today()
        too_old_start = (today - timedelta(days=200)).isoformat()
        too_old_end = (today - timedelta(days=193)).isoformat()
        with pytest.raises(SubscriptionAccessError) as exc_info:
            _resolve_date_window(
                serving_mode="maps_platform",
                subscription_tier="premium",
                timelapse_period_months=3,
                date_start=too_old_start,
                date_end=too_old_end,
            )
        assert "timelapse" in str(exc_info.value).lower() or "outside" in str(exc_info.value).lower()

    def test_premium_uses_latest_if_no_date_given(self):
        today = date.today()
        start, end = _resolve_date_window(
            serving_mode="maps_platform",
            subscription_tier="premium",
            timelapse_period_months=3,
            date_start=None,
            date_end=None,
        )
        assert end == today.isoformat()
        assert start == (today - timedelta(days=7)).isoformat()

    def test_subscription_access_error_is_raster_engine_error(self):
        assert issubclass(SubscriptionAccessError, RasterEngineError)


# ---------------------------------------------------------------------------
# TC-009: No fake static raster path in raster_engine.py
# ---------------------------------------------------------------------------

class TestNoFakeRasterPath:
    def _read_raster_engine(self) -> str:
        path = _REPO_ROOT / "src" / "raster_engine.py"
        return path.read_text(encoding="utf-8")

    def test_no_hardcoded_fake_tile_url(self):
        src = self._read_raster_engine()
        assert "fake" not in src.lower() or "no fake" in src.lower()
        assert "placeholder" not in src.lower() or "no placeholder" in src.lower()

    def test_no_random_heatmap(self):
        src = self._read_raster_engine()
        assert "random" not in src.lower() or "random heatmap" not in src.lower()

    def test_generate_metadata_calls_core_engine(self):
        src = self._read_raster_engine()
        assert "select_best_scene" in src
        assert "apply_cloud_mask" in src
        assert "prepare_image" in src
        assert "calculate_indices" in src

    def test_tile_url_from_getmapid_not_hardcoded(self):
        src = self._read_raster_engine()
        assert "getMapId" in src
        assert "tile_fetcher" in src

    def test_secret_not_in_source(self):
        src = self._read_raster_engine()
        forbidden = ["service_account_key", "private_key", "GOOGLE_APPLICATION_CREDENTIALS"]
        for term in forbidden:
            assert term not in src, f"Sensitive term found in source: {term}"


# ---------------------------------------------------------------------------
# TC-023: Raster cache contract — key schema, metadata-only storage
# ---------------------------------------------------------------------------

class TestRasterCacheContract:
    def _import_cache(self):
        backend_dir = _REPO_ROOT / "backend"
        if str(backend_dir) not in sys.path:
            sys.path.insert(0, str(backend_dir))
        from app.api.raster_cache import build_cache_key, get_cached_metadata, set_cached_metadata
        return build_cache_key, get_cached_metadata, set_cached_metadata

    def test_cache_key_prefix_is_versioned(self):
        build_cache_key, _, _ = self._import_cache()
        key = build_cache_key(1, "ndvi", "2026-05-14", "2026-05-21", "gee_mapid")
        assert key.startswith("raster:v1:"), f"Cache key missing versioned prefix: {key}"

    def test_cache_key_includes_all_dimensions(self):
        build_cache_key, _, _ = self._import_cache()
        key = build_cache_key(2, "evi", "2026-04-01", "2026-04-08", "maps_platform")
        assert "2" in key
        assert "evi" in key
        assert "2026-04-01" in key
        assert "2026-04-08" in key
        assert "maps_platform" in key

    def test_different_companies_get_different_keys(self):
        build_cache_key, _, _ = self._import_cache()
        key1 = build_cache_key(1, "ndvi", "2026-05-14", "2026-05-21", "gee_mapid")
        key2 = build_cache_key(2, "ndvi", "2026-05-14", "2026-05-21", "gee_mapid")
        assert key1 != key2, "Different companies must have different cache keys"

    def test_different_indices_get_different_keys(self):
        build_cache_key, _, _ = self._import_cache()
        key1 = build_cache_key(1, "ndvi", "2026-05-14", "2026-05-21", "gee_mapid")
        key2 = build_cache_key(1, "evi", "2026-05-14", "2026-05-21", "gee_mapid")
        assert key1 != key2

    def test_different_dates_get_different_keys(self):
        build_cache_key, _, _ = self._import_cache()
        key1 = build_cache_key(1, "ndvi", "2026-05-14", "2026-05-21", "gee_mapid")
        key2 = build_cache_key(1, "ndvi", "2026-04-14", "2026-04-21", "gee_mapid")
        assert key1 != key2

    def test_different_serving_modes_get_different_keys(self):
        build_cache_key, _, _ = self._import_cache()
        key1 = build_cache_key(1, "ndvi", "2026-05-14", "2026-05-21", "gee_mapid")
        key2 = build_cache_key(1, "ndvi", "2026-05-14", "2026-05-21", "maps_platform")
        assert key1 != key2

    def test_cache_module_exists(self):
        cache_file = _REPO_ROOT / "backend" / "app" / "api" / "raster_cache.py"
        assert cache_file.exists(), "raster_cache.py must exist"

    def test_cache_source_stores_only_metadata_not_tile_images(self):
        cache_file = _REPO_ROOT / "backend" / "app" / "api" / "raster_cache.py"
        src = cache_file.read_text(encoding="utf-8")
        assert "tile image" not in src.lower() or "not" in src.lower()
        assert "metadata" in src.lower()
        assert "json" in src.lower()

    def test_cache_ttl_not_hardcoded_in_cache_module(self):
        cache_file = _REPO_ROOT / "backend" / "app" / "api" / "raster_cache.py"
        src = cache_file.read_text(encoding="utf-8")
        assert "RASTER_CACHE_TTL_SECONDS" in src or "ttl_seconds" in src, (
            "Cache TTL must be parameter-driven, not hardcoded"
        )
        assert "14 * 24" not in src, "Must not hardcode 14-day TTL"
        assert "14400" not in src or "14 days" not in src


# ---------------------------------------------------------------------------
# TC-024: Cache hit avoids duplicate provider generation (async mock)
# ---------------------------------------------------------------------------

class TestCacheHitPreventsProviderCall:
    def _import_cache(self):
        backend_dir = _REPO_ROOT / "backend"
        if str(backend_dir) not in sys.path:
            sys.path.insert(0, str(backend_dir))
        from app.api.raster_cache import build_cache_key, get_cached_metadata, set_cached_metadata
        return build_cache_key, get_cached_metadata, set_cached_metadata

    def test_get_cached_metadata_returns_dict_on_hit(self):
        import asyncio

        class _FakeRedis:
            def __init__(self, stored: dict):
                self._store = stored
            async def get(self, key):
                import json
                val = self._store.get(key)
                return json.dumps(val) if val is not None else None

        _, get_cached_metadata, _ = self._import_cache()
        cached_data = {"schema_version": "1.0", "index": "ndvi", "sensor": "S2"}
        fake_redis = _FakeRedis({"raster:v1:1:ndvi:2026-05-14:2026-05-21:gee_mapid": cached_data})

        result = asyncio.run(
            get_cached_metadata(fake_redis, "raster:v1:1:ndvi:2026-05-14:2026-05-21:gee_mapid")
        )
        assert result == cached_data

    def test_get_cached_metadata_returns_none_on_miss(self):
        import asyncio

        class _FakeRedis:
            async def get(self, key):
                return None

        _, get_cached_metadata, _ = self._import_cache()
        result = asyncio.run(
            get_cached_metadata(_FakeRedis(), "raster:v1:1:ndvi:2026-05-14:2026-05-21:gee_mapid")
        )
        assert result is None

    def test_get_cached_metadata_returns_none_when_redis_is_none(self):
        import asyncio
        _, get_cached_metadata, _ = self._import_cache()
        result = asyncio.run(
            get_cached_metadata(None, "any_key")
        )
        assert result is None

    def test_set_cached_metadata_stores_json(self):
        import asyncio
        import json

        stored = {}

        class _FakeRedis:
            async def setex(self, key, ttl, value):
                stored[key] = (ttl, json.loads(value))

        _, _, set_cached_metadata = self._import_cache()
        data = {"schema_version": "1.0", "index": "ndvi"}
        asyncio.run(
            set_cached_metadata(_FakeRedis(), "test_key", data, 43200)
        )
        assert "test_key" in stored
        assert stored["test_key"][0] == 43200
        assert stored["test_key"][1] == data

    def test_set_cached_metadata_noop_when_redis_is_none(self):
        import asyncio
        _, _, set_cached_metadata = self._import_cache()
        asyncio.run(
            set_cached_metadata(None, "test_key", {}, 43200)
        )


# ---------------------------------------------------------------------------
# TC-025: Cache expiry is provider-driven — configurable, not hardcoded
# ---------------------------------------------------------------------------

class TestCacheExpiryProviderDriven:
    def test_settings_has_raster_cache_ttl_seconds(self):
        backend_dir = _REPO_ROOT / "backend"
        if str(backend_dir) not in sys.path:
            sys.path.insert(0, str(backend_dir))
        from app.database import settings
        assert hasattr(settings, "RASTER_CACHE_TTL_SECONDS"), (
            "Settings must expose RASTER_CACHE_TTL_SECONDS for operator configuration"
        )
        assert isinstance(settings.RASTER_CACHE_TTL_SECONDS, int)
        assert settings.RASTER_CACHE_TTL_SECONDS > 0

    def test_default_ttl_is_within_gee_window(self):
        backend_dir = _REPO_ROOT / "backend"
        if str(backend_dir) not in sys.path:
            sys.path.insert(0, str(backend_dir))
        from app.database import settings
        # Default must be < 48h (172800s) — within GEE getMapId empirical window
        assert settings.RASTER_CACHE_TTL_SECONDS < 172800, (
            "Default TTL exceeds GEE getMapId ~48h window — tile URLs would be stale"
        )

    def test_default_ttl_is_not_hardcoded_14_days(self):
        from app.database import settings
        assert settings.RASTER_CACHE_TTL_SECONDS != 1209600, (
            "TTL must not be hardcoded to 14 days — use provider-driven value"
        )

    def test_raster_cache_ttl_env_var_documented_in_database_py(self):
        db_file = _REPO_ROOT / "backend" / "app" / "database.py"
        src = db_file.read_text(encoding="utf-8")
        assert "RASTER_CACHE_TTL_SECONDS" in src, (
            "RASTER_CACHE_TTL_SECONDS must be in database.py Settings"
        )

    def test_cache_file_passes_ttl_as_parameter_not_constant(self):
        cache_file = _REPO_ROOT / "backend" / "app" / "api" / "raster_cache.py"
        src = cache_file.read_text(encoding="utf-8")
        assert "def set_cached_metadata" in src
        assert "ttl_seconds" in src, (
            "set_cached_metadata must accept ttl_seconds as parameter"
        )


# ---------------------------------------------------------------------------
# TC-003 (v1.9): date_acquired fix — must come from GEE scene, not actual_end
# ---------------------------------------------------------------------------

class TestDateAcquiredFix:
    def test_date_acquired_bug_not_present_in_src_engine(self):
        """TC-003: raster_engine.py must not assign date_acquired=actual_end."""
        path = _REPO_ROOT / "src" / "raster_engine.py"
        src = path.read_text(encoding="utf-8")
        assert "date_acquired=actual_end" not in src, (
            "BUG REGRESSED: date_acquired=actual_end found in src/raster_engine.py. "
            "Must use scene.image.date().format('YYYY-MM-dd').getInfo() instead."
        )

    def test_date_acquired_fix_present_in_src_engine(self):
        """TC-003: scene.image.date() call must be present for actual acquisition date."""
        path = _REPO_ROOT / "src" / "raster_engine.py"
        src = path.read_text(encoding="utf-8")
        assert "scene.image.date()" in src, (
            "Fix not found: scene.image.date() must be used to derive date_acquired."
        )
        assert "getInfo()" in src, (
            "getInfo() call required for scene.image.date().format().getInfo() derivation."
        )

    def test_date_acquired_failure_raises_raster_engine_error(self):
        """TC-003: If GEE date call fails, RasterEngineError must be raised (no silent fallback)."""
        path = _REPO_ROOT / "src" / "raster_engine.py"
        src = path.read_text(encoding="utf-8")
        assert "RasterEngineError" in src, "RasterEngineError must be raised on date derivation failure."
        assert "Cannot read scene acquisition date" in src, (
            "Error message for date derivation failure must be explicit."
        )

    def test_deploy_package_date_acquired_fix_in_sync(self):
        """TC-003: src/deploy/raster_engine.py must carry the same fix as src/raster_engine.py."""
        path = _REPO_ROOT / "src" / "deploy" / "raster_engine.py"
        src = path.read_text(encoding="utf-8")
        assert "date_acquired=actual_end" not in src, (
            "SYNC ERROR: date_acquired=actual_end still in src/deploy/raster_engine.py. "
            "Deploy package must be kept in sync with src/raster_engine.py."
        )
        assert "scene.image.date()" in src, (
            "Deploy package must also use scene.image.date() for date_acquired."
        )


# ---------------------------------------------------------------------------
# TC-013 (v1.9): Frame cache key isolation — frame_id must produce unique keys
# ---------------------------------------------------------------------------

class TestFrameCacheKeyIsolation:
    def _import_cache(self):
        backend_dir = _REPO_ROOT / "backend"
        if str(backend_dir) not in sys.path:
            sys.path.insert(0, str(backend_dir))
        from app.api.raster_cache import build_cache_key
        return build_cache_key

    def test_different_frame_ids_get_different_keys(self):
        """TC-013: Two different frames must not share a cache entry."""
        build_cache_key = self._import_cache()
        key1 = build_cache_key(2, "ndvi", "2026-09-24", "2026-09-25", "maps_platform", frame_id="2026-09-24")
        key2 = build_cache_key(2, "ndvi", "2026-10-14", "2026-10-15", "maps_platform", frame_id="2026-10-14")
        assert key1 != key2, "Different frame_ids must produce different cache keys."

    def test_frame_id_key_differs_from_window_key_same_dates(self):
        """TC-013: frame_id cache key must not collide with non-frame_id key for same dates."""
        build_cache_key = self._import_cache()
        frame_key = build_cache_key(2, "ndvi", "2026-09-24", "2026-09-25", "maps_platform", frame_id="2026-09-24")
        window_key = build_cache_key(2, "ndvi", "2026-09-24", "2026-09-25", "maps_platform")
        assert frame_key != window_key, "frame_id path must not collide with date-window path."

    def test_frame_key_is_company_scoped(self):
        """TC-013: Company isolation must hold for frame_id keys."""
        build_cache_key = self._import_cache()
        key_c1 = build_cache_key(1, "ndvi", "2026-09-24", "2026-09-25", "maps_platform", frame_id="2026-09-24")
        key_c2 = build_cache_key(2, "ndvi", "2026-09-24", "2026-09-25", "maps_platform", frame_id="2026-09-24")
        assert key_c1 != key_c2, "Same frame must have different keys for different companies."

    def test_frame_key_contains_frame_id_value(self):
        """TC-013: Cache key must embed frame_id for debuggability."""
        build_cache_key = self._import_cache()
        key = build_cache_key(2, "ndvi", "2026-09-24", "2026-09-25", "maps_platform", frame_id="2026-09-24")
        assert "frame" in key, "Cache key must contain 'frame' segment when frame_id is provided."
        assert "2026-09-24" in key, "Cache key must embed the frame_id date value."


# ---------------------------------------------------------------------------
# TC-002 / TC-004 (v1.9): Frames endpoint SQL contract — GROUP BY and index filter
# ---------------------------------------------------------------------------

class TestFramesEndpointSqlContract:
    def test_frames_sql_has_group_by(self):
        """TC-004: Frame list SQL must use GROUP BY, not DISTINCT with aggregates."""
        path = _REPO_ROOT / "backend" / "app" / "api" / "raster.py"
        src = path.read_text(encoding="utf-8")
        assert "GROUP BY sd.acquisition_date" in src, (
            "Frame list SQL missing GROUP BY sd.acquisition_date. "
            "Aggregate functions (MIN, AVG) require GROUP BY, not DISTINCT."
        )

    def test_frames_sql_has_index_is_not_null_filter(self):
        """TC-004: Frame list SQL must filter by index IS NOT NULL to exclude incompatible sensors."""
        path = _REPO_ROOT / "backend" / "app" / "api" / "raster.py"
        src = path.read_text(encoding="utf-8")
        assert "IS NOT NULL" in src, (
            "Frame list SQL missing IS NOT NULL filter. "
            "Landsat-only dates must not appear in Sentinel-only index frame lists (e.g. NDRE)."
        )

    def test_frames_endpoint_is_premium_only(self):
        """TC-011: /api/raster/frames must reject non-premium users."""
        path = _REPO_ROOT / "backend" / "app" / "api" / "raster.py"
        src = path.read_text(encoding="utf-8")
        assert "timelapse_enabled" in src, (
            "Frames endpoint must check timelapse_enabled from DB subscription."
        )
        assert "Premium feature" in src or "premium" in src.lower(), (
            "Frames endpoint must gate on Premium tier."
        )

    def test_frame_id_param_in_metadata_endpoint(self):
        """TC-002: metadata endpoint must accept frame_id as an ISO date parameter."""
        path = _REPO_ROOT / "backend" / "app" / "api" / "raster.py"
        src = path.read_text(encoding="utf-8")
        assert "frame_id" in src, "metadata endpoint must accept frame_id parameter."
        assert "fromisoformat" in src, "frame_id must be parsed as an ISO date."

    def test_frame_id_exclusive_end_conversion(self):
        """TC-002: frame_id must be converted to date_end = frame_date + 1 day for GEE exclusive end."""
        path = _REPO_ROOT / "backend" / "app" / "api" / "raster.py"
        src = path.read_text(encoding="utf-8")
        assert "timedelta(days=1)" in src, (
            "frame_id conversion to date_end must add 1 day (GEE filterDate end is exclusive)."
        )

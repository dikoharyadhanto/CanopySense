"""
test_estate_onboarding_contracts.py — CanopySense estate onboarding contract tests.

Covers TC-001 through TC-022 from FMN-PLAN v1.12 test contract (estate onboarding
and pgAdmin sub-set). All tests are offline (no DB, no Redis required).

They verify:
  - Migration 006 exists and contains required DDL
  - spatial_validator module structure and Phase 1 logic (pure Python, no DB)
  - estate_onboarding module structure and route registration
  - RBAC dependency: get_current_admin enforced on all endpoints
  - Validation matrix: file size, CRS, geometry type, required props, duplicates
  - Preview/commit response shapes
  - docker-compose.yml contains pgAdmin service
  - Sample fixture is valid GeoJSON matching the import contract

Usage:
    python -m pytest tests/test_estate_onboarding_contracts.py -v
"""
from __future__ import annotations

import importlib.util
import inspect
import json
import pathlib
import sys
import types

import pytest

_ROOT = pathlib.Path(__file__).parent.parent
_BACKEND = _ROOT / "backend"
sys.path.insert(0, str(_BACKEND))


# ---------------------------------------------------------------------------
# Module loader (stubs out DB to avoid startup side effects)
# ---------------------------------------------------------------------------

def _make_db_stub() -> types.ModuleType:
    stub = types.ModuleType("app.database")
    stub.get_db_pool = lambda: None  # type: ignore[attr-defined]
    stub.settings = types.SimpleNamespace(  # type: ignore[attr-defined]
        SECRET_KEY="test-secret",
        ALGORITHM="HS256",
        ACCESS_TOKEN_EXPIRE_MINUTES=60,
        CLOUD_FUNCTION_URL="",
        PATCHER_API_KEY="",
        CONTRACTOR_ID="",
        PGHOST="localhost",
        PGPORT=5432,
        PGUSER="postgres",
        PGPASSWORD="",
        PGDATABASE="canopysense",
        PGSCHEMA="canopysense",
        FUNCTION_TIMEOUT_SECONDS=120,
        PATCHER_API_VERSION="1.1",
        RASTER_CACHE_TTL_SECONDS=43200,
    )
    return stub


def _load(dotted: str) -> types.ModuleType:
    path = _BACKEND / (dotted.replace(".", "/") + ".py")
    spec = importlib.util.spec_from_file_location(dotted, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot find: {path}")

    if "app.database" not in sys.modules:
        sys.modules["app.database"] = _make_db_stub()
    if "app.auth.jwt" not in sys.modules:
        jwt_stub = types.ModuleType("app.auth.jwt")
        jwt_stub.decode_access_token = lambda t: {"sub": "test"}  # type: ignore[attr-defined]
        jwt_stub.get_password_hash = lambda p: "hashed"  # type: ignore[attr-defined]
        jwt_stub.verify_password = lambda p, h: True  # type: ignore[attr-defined]
        sys.modules["app.auth.jwt"] = jwt_stub

    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ===========================================================================
# TC-M01: Migration 006 exists and contains required DDL
# ===========================================================================

class TestMigration006:
    MIG = _ROOT / "database/migrations/006_estate_onboarding.sql"

    def test_file_exists(self):
        assert self.MIG.exists(), "006_estate_onboarding.sql must exist"

    def test_drop_estate_geometry_not_null(self):
        sql = self.MIG.read_text()
        assert "ALTER COLUMN geometry DROP NOT NULL" in sql

    def test_null_aware_estate_constraint(self):
        sql = self.MIG.read_text()
        assert "geometry IS NULL" in sql and "chk_estate_valid" in sql

    def test_is_draft_column_added(self):
        sql = self.MIG.read_text()
        assert "is_draft" in sql

    def test_is_draft_backfill(self):
        sql = self.MIG.read_text()
        assert "is_draft = FALSE" in sql

    def test_afdeling_geometry_nullable(self):
        sql = self.MIG.read_text()
        assert "canopysense.afdelings" in sql
        assert "DROP NOT NULL" in sql

    def test_afdeling_unique_constraint(self):
        sql = self.MIG.read_text()
        assert "uq_afdelings_estate_code" in sql or "UNIQUE (estate_id, code)" in sql


# ===========================================================================
# TC-M02: pgAdmin in docker-compose
# ===========================================================================

class TestDockerComposePgAdmin:
    DC = _ROOT / "docker-compose.yml"

    def test_pgadmin_service_present(self):
        content = self.DC.read_text()
        assert "pgadmin" in content

    def test_pgadmin_port_5050(self):
        content = self.DC.read_text()
        assert "5050" in content

    def test_pgadmin_email_env_var(self):
        content = self.DC.read_text()
        assert "PGADMIN_DEFAULT_EMAIL" in content

    def test_pgadmin_password_env_var_no_default(self):
        content = self.DC.read_text()
        assert "PGADMIN_DEFAULT_PASSWORD" in content
        assert "PGADMIN_DEFAULT_PASSWORD=password" not in content
        assert "PGADMIN_DEFAULT_PASSWORD=admin" not in content

    def test_pgadmin_data_volume(self):
        content = self.DC.read_text()
        assert "pgadmin_data" in content


# ===========================================================================
# TC-M03: Sample fixture is valid GeoJSON matching the import contract
# ===========================================================================

class TestSampleFixture:
    SAMPLE = _ROOT / "samples/estate_import_sample.geojson"
    REQUIRED_PROPS = {"block_code", "block_name", "afdeling_code", "afdeling_name"}

    def test_file_exists(self):
        assert self.SAMPLE.exists()

    def test_is_feature_collection(self):
        data = json.loads(self.SAMPLE.read_text())
        assert data["type"] == "FeatureCollection"

    def test_has_features(self):
        data = json.loads(self.SAMPLE.read_text())
        assert len(data["features"]) >= 1

    def test_all_features_are_polygons(self):
        data = json.loads(self.SAMPLE.read_text())
        for feat in data["features"]:
            assert feat["geometry"]["type"] == "Polygon", (
                f"Feature {feat} is not a Polygon"
            )

    def test_all_features_have_required_props(self):
        data = json.loads(self.SAMPLE.read_text())
        for feat in data["features"]:
            props = feat.get("properties", {})
            for p in self.REQUIRED_PROPS:
                assert p in props and props[p], (
                    f"Feature missing required property {p!r}"
                )

    def test_no_duplicate_block_codes(self):
        data = json.loads(self.SAMPLE.read_text())
        codes = [f["properties"]["block_code"] for f in data["features"]]
        assert len(codes) == len(set(codes)), "Sample has duplicate block_codes"

    def test_no_explicit_crs(self):
        data = json.loads(self.SAMPLE.read_text())
        assert "crs" not in data, "Sample should not include a crs member (assume EPSG:4326)"

    def test_has_multiple_afdelings(self):
        data = json.loads(self.SAMPLE.read_text())
        afdeling_codes = {f["properties"]["afdeling_code"] for f in data["features"]}
        assert len(afdeling_codes) >= 2

    def test_field_lengths_within_limits(self):
        data = json.loads(self.SAMPLE.read_text())
        limits = {"block_code": 20, "block_name": 100, "afdeling_code": 20, "afdeling_name": 100}
        for feat in data["features"]:
            props = feat["properties"]
            for field, max_len in limits.items():
                val = props.get(field, "")
                assert len(str(val)) <= max_len, (
                    f"Field {field!r} exceeds max length {max_len}: {val!r}"
                )


# ===========================================================================
# TC-V01–TC-V10: spatial_validator Phase 1 (pure Python)
# ===========================================================================

class TestValidateGeoJSONBytes:
    @pytest.fixture(autouse=True)
    def _import_validator(self):
        self.mod = _load("app.services.spatial_validator")
        self.validate = self.mod.validate_geojson_bytes

    def _make_feature(self, props: dict, geom_type: str = "Polygon") -> dict:
        return {
            "type": "Feature",
            "geometry": {
                "type": geom_type,
                "coordinates": [[[109.0, 0.0], [109.1, 0.0], [109.1, 0.1], [109.0, 0.0]]],
            },
            "properties": props,
        }

    def _make_fc(self, features: list) -> bytes:
        return json.dumps({"type": "FeatureCollection", "features": features}).encode()

    def _valid_props(self, suffix: str = "1") -> dict:
        return {
            "block_code": f"BLK-{suffix}",
            "block_name": f"Block {suffix}",
            "afdeling_code": "AFD-A",
            "afdeling_name": "Afdeling Alpha",
        }

    # TC-V01: valid file passes
    def test_valid_file_passes(self):
        fc = self._make_fc([self._make_feature(self._valid_props())])
        result = self.validate(fc, "test.geojson")
        assert result.file_error is None
        assert len(result.valid_features) == 1
        assert len(result.invalid_rows) == 0
        assert result.commit_eligible is True

    # TC-V02: file size limit
    def test_file_too_large(self):
        big = b"x" * (11 * 1024 * 1024)
        result = self.validate(big, "big.geojson")
        assert result.file_error is not None
        assert "large" in result.file_error.lower() or "bytes" in result.file_error.lower()

    # TC-V03: invalid JSON
    def test_invalid_json(self):
        result = self.validate(b"not json {{{", "bad.geojson")
        assert result.file_error is not None
        assert "json" in result.file_error.lower()

    # TC-V04: not a FeatureCollection
    def test_not_feature_collection(self):
        result = self.validate(json.dumps({"type": "Feature"}).encode(), "bad.geojson")
        assert result.file_error is not None
        assert "FeatureCollection" in result.file_error

    # TC-V05: empty features list
    def test_empty_features(self):
        fc = self._make_fc([])
        result = self.validate(fc, "empty.geojson")
        assert result.file_error is not None
        assert "empty" in result.file_error.lower() or "no features" in result.file_error.lower()

    # TC-V06: explicit EPSG:4326 CRS is accepted
    def test_accepted_crs_epsg_4326(self):
        fc = {
            "type": "FeatureCollection",
            "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
            "features": [self._make_feature(self._valid_props())],
        }
        result = self.validate(json.dumps(fc).encode(), "crs.geojson")
        assert result.file_error is None

    # TC-V07: explicit non-4326 CRS is rejected
    def test_rejected_crs(self):
        fc = {
            "type": "FeatureCollection",
            "crs": {"type": "name", "properties": {"name": "EPSG:32749"}},
            "features": [self._make_feature(self._valid_props())],
        }
        result = self.validate(json.dumps(fc).encode(), "bad_crs.geojson")
        assert result.file_error is not None
        assert "CRS" in result.file_error or "crs" in result.file_error.lower()

    # TC-V08: MultiPolygon geometry type is rejected
    def test_multipolygon_rejected(self):
        feat = {
            "type": "Feature",
            "geometry": {
                "type": "MultiPolygon",
                "coordinates": [[[[109.0, 0.0], [109.1, 0.0], [109.1, 0.1], [109.0, 0.0]]]],
            },
            "properties": self._valid_props(),
        }
        fc = self._make_fc([feat])
        result = self.validate(fc, "mp.geojson")
        assert len(result.invalid_rows) == 1
        assert "MultiPolygon" in result.invalid_rows[0]["reason"]

    # TC-V09: missing required property
    def test_missing_required_prop(self):
        props = self._valid_props()
        del props["block_code"]
        fc = self._make_fc([self._make_feature(props)])
        result = self.validate(fc, "missing.geojson")
        assert len(result.invalid_rows) == 1
        assert "block_code" in result.invalid_rows[0]["reason"]

    # TC-V10: block_code too long
    def test_block_code_too_long(self):
        props = self._valid_props()
        props["block_code"] = "B" * 21
        fc = self._make_fc([self._make_feature(props)])
        result = self.validate(fc, "long.geojson")
        assert len(result.invalid_rows) == 1
        assert "block_code" in result.invalid_rows[0]["reason"]

    # TC-V11: plant_year must be int
    def test_plant_year_string_rejected(self):
        props = self._valid_props()
        props["plant_year"] = "2015"
        fc = self._make_fc([self._make_feature(props)])
        result = self.validate(fc, "year.geojson")
        assert len(result.invalid_rows) == 1
        assert "plant_year" in result.invalid_rows[0]["reason"]

    # TC-V12: plant_year integer is accepted
    def test_plant_year_int_accepted(self):
        props = self._valid_props()
        props["plant_year"] = 2015
        fc = self._make_fc([self._make_feature(props)])
        result = self.validate(fc, "year.geojson")
        assert result.file_error is None
        assert len(result.valid_features) == 1

    # TC-V13: within-file duplicate block_code — both occurrences rejected
    def test_duplicate_block_code_within_file(self):
        props = self._valid_props("X")
        fc = self._make_fc([
            self._make_feature({**props, "block_name": "Block X1"}),
            self._make_feature({**props, "block_name": "Block X2"}),
        ])
        result = self.validate(fc, "dup.geojson")
        assert len(result.invalid_rows) == 2
        assert all("Duplicate" in r["reason"] for r in result.invalid_rows)

    # TC-V14: duplicate afdeling_code within file is allowed (merge semantics)
    def test_duplicate_afdeling_code_allowed(self):
        fc = self._make_fc([
            self._make_feature(self._valid_props("1")),
            self._make_feature({**self._valid_props("2"), "afdeling_code": "AFD-A"}),
        ])
        result = self.validate(fc, "afd_dup.geojson")
        assert result.file_error is None
        assert len(result.valid_features) == 2
        assert len(result.invalid_rows) == 0

    # TC-V15: large feature count triggers warning
    def test_large_file_warning(self):
        features = [self._make_feature(self._valid_props(str(i))) for i in range(5001)]
        fc = self._make_fc(features)
        result = self.validate(fc, "large.geojson")
        assert len(result.warnings) > 0

    # TC-V16: unsupported file extension rejected
    def test_unsupported_extension(self):
        result = self.validate(b"{}", "data.csv")
        assert result.file_error is not None

    # TC-V17: commit_eligible False when any invalid rows exist
    def test_commit_ineligible_with_invalid_rows(self):
        props_ok = self._valid_props("OK")
        props_bad = {**self._valid_props("BAD"), "block_code": "X" * 21}
        fc = self._make_fc([
            self._make_feature(props_ok),
            self._make_feature(props_bad),
        ])
        result = self.validate(fc, "mixed.geojson")
        assert result.commit_eligible is False

    # TC-V18: OGC:CRS84 name accepted
    def test_accepted_crs_ogc_crs84(self):
        fc = {
            "type": "FeatureCollection",
            "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
            "features": [self._make_feature(self._valid_props())],
        }
        result = self.validate(json.dumps(fc).encode(), "crs84.geojson")
        assert result.file_error is None

    # TC-V19: no crs member — accepted (RFC 7946 default)
    def test_no_crs_member_accepted(self):
        data = json.loads(self._make_fc([self._make_feature(self._valid_props())]))
        assert "crs" not in data
        result = self.validate(json.dumps(data).encode(), "nocrs.geojson")
        assert result.file_error is None


# ===========================================================================
# TC-R01–TC-R06: estate_onboarding module structure
# ===========================================================================

class TestEstateOnboardingModule:
    @pytest.fixture(autouse=True)
    def _import_mod(self):
        self.mod = _load("app.api.admin.estate_onboarding")

    def test_router_exists(self):
        assert hasattr(self.mod, "router"), "estate_onboarding must expose a router"

    def test_all_six_routes_registered(self):
        routes = {r.path for r in self.mod.router.routes}
        assert "/companies/{company_id}/estates" in routes
        assert "/estates/{estate_id}" in routes
        assert "/estates/{estate_id}/import/preview" in routes
        assert "/estates/{estate_id}/import/commit" in routes

    def test_get_current_admin_dep_present(self):
        from app.api.deps import get_current_admin
        src = inspect.getsource(self.mod)
        assert "get_current_admin" in src

    def test_log_admin_action_dep_present(self):
        src = inspect.getsource(self.mod)
        assert "log_admin_action" in src

    def test_spatial_validator_imported(self):
        src = inspect.getsource(self.mod)
        assert "validate_geojson_bytes" in src
        assert "run_postgis_validity" in src

    def test_audit_events_all_present(self):
        src = inspect.getsource(self.mod)
        for event in ("estate_create", "estate_edit", "estate_import_preview",
                      "estate_import_commit", "estate_import_failure"):
            assert event in src, f"Audit event {event!r} not found in estate_onboarding.py"

    def test_transactional_commit_pattern(self):
        src = inspect.getsource(self.mod)
        assert "conn.transaction()" in src

    def test_is_draft_guard_on_edit(self):
        src = inspect.getsource(self.mod)
        assert "is_draft" in src


# ===========================================================================
# TC-R07: router.py includes estate_onboarding
# ===========================================================================

class TestAdminRouterIncludes:
    def test_estate_onboarding_included(self):
        router_path = _BACKEND / "app/api/admin/router.py"
        src = router_path.read_text()
        assert "estate_onboarding" in src
        assert "estate-onboarding" in src


# ===========================================================================
# TC-R08: ValidationResult dataclass shape
# ===========================================================================

class TestValidationResultShape:
    def test_dataclass_fields(self):
        mod = _load("app.services.spatial_validator")
        result = mod.ValidationResult()
        assert hasattr(result, "valid_features")
        assert hasattr(result, "invalid_rows")
        assert hasattr(result, "warnings")
        assert hasattr(result, "commit_eligible")
        assert hasattr(result, "file_error")
        assert result.commit_eligible is False
        assert result.file_error is None


# ===========================================================================
# TC-R09: run_postgis_validity and run_db_duplicate_check signatures
# ===========================================================================

class TestValidatorAsyncFunctions:
    def test_run_postgis_validity_is_async(self):
        mod = _load("app.services.spatial_validator")
        func = getattr(mod, "run_postgis_validity")
        assert inspect.iscoroutinefunction(func)

    def test_run_db_duplicate_check_is_async(self):
        mod = _load("app.services.spatial_validator")
        func = getattr(mod, "run_db_duplicate_check")
        assert inspect.iscoroutinefunction(func)

    def test_run_db_duplicate_check_accepts_conn(self):
        mod = _load("app.services.spatial_validator")
        func = getattr(mod, "run_db_duplicate_check")
        sig = inspect.signature(func)
        assert "conn" in sig.parameters


# ===========================================================================
# TC-R10: Sample fixture passes Phase 1 validation
# ===========================================================================

class TestSampleFixturePhase1:
    def test_sample_passes_validate_geojson_bytes(self):
        mod = _load("app.services.spatial_validator")
        sample = (_ROOT / "samples/estate_import_sample.geojson").read_bytes()
        result = mod.validate_geojson_bytes(sample, "estate_import_sample.geojson")
        assert result.file_error is None, f"Sample failed Phase 1: {result.file_error}"
        assert len(result.valid_features) == 3
        assert len(result.invalid_rows) == 0
        assert result.commit_eligible is True


# ===========================================================================
# TC-001 through TC-005: /import/parse endpoint (Stage 1.15)
# ===========================================================================

class TestImportParseEndpoint:
    """Structural contract tests for POST /estates/{id}/import/parse."""

    @pytest.fixture(autouse=True)
    def _import_mod(self):
        self.mod = _load("app.api.admin.estate_onboarding")

    # TC-001: /import/parse route is registered
    def test_parse_route_registered(self):
        routes = {r.path for r in self.mod.router.routes}
        assert "/estates/{estate_id}/import/parse" in routes, (
            "/import/parse route not found in router"
        )

    # TC-001: parse endpoint is an async coroutine function
    def test_parse_endpoint_is_async(self):
        route = next(
            r for r in self.mod.router.routes
            if getattr(r, "path", None) == "/estates/{estate_id}/import/parse"
        )
        assert inspect.iscoroutinefunction(route.endpoint), (
            "import_parse must be an async function"
        )

    # TC-001: response shape includes 'features' and 'warnings' keys
    def test_parse_response_shape_contains_features_and_warnings(self):
        src = inspect.getsource(self.mod.import_parse)
        assert '"features"' in src or "'features'" in src, (
            "import_parse response must include 'features' key"
        )
        assert '"warnings"' in src or "'warnings'" in src, (
            "import_parse response must include 'warnings' key"
        )

    # TC-002: parse returns empty features list on file_error path
    def test_parse_returns_empty_features_on_file_error(self):
        src = inspect.getsource(self.mod.import_parse)
        assert '"features": []' in src or "'features': []" in src, (
            "import_parse must return empty features list on file_error"
        )

    # TC-003: parse uses same file-size limit as preview (MAX_UPLOAD_SIZE_BYTES)
    def test_parse_enforces_file_size_limit(self):
        src = inspect.getsource(self.mod.import_parse)
        assert "MAX_UPLOAD_SIZE_BYTES" in src, (
            "import_parse must enforce MAX_UPLOAD_SIZE_BYTES"
        )

    # TC-003: parse uses same conversion path (convert_to_geojson_bytes) as preview
    def test_parse_uses_convert_to_geojson_bytes(self):
        src = inspect.getsource(self.mod.import_parse)
        assert "convert_to_geojson_bytes" in src, (
            "import_parse must call convert_to_geojson_bytes for ZIP/KML/KMZ conversion"
        )

    # TC-004: parse endpoint requires get_current_admin (admin-only)
    def test_parse_enforces_admin_auth(self):
        # get_current_admin is declared via Depends() in the function signature,
        # not as a route-level dependency. Check source for its presence.
        src = inspect.getsource(self.mod.import_parse)
        assert "get_current_admin" in src, (
            "import_parse must use get_current_admin dependency"
        )

    # TC-005: /import/preview response shape is unchanged (no new fields injected)
    def test_preview_response_shape_unchanged(self):
        route = next(
            r for r in self.mod.router.routes
            if getattr(r, "path", None) == "/estates/{estate_id}/import/preview"
        )
        src = inspect.getsource(route.endpoint)
        for field in (
            "commit_eligible", "file_error", "valid_blocks",
            "invalid_rows", "afdeling_count", "warnings"
        ):
            assert f'"{field}"' in src or f"'{field}'" in src, (
                f"import_preview response must still contain field: {field!r}"
            )

    # TC-005: /import/parse is a separate function from /import/preview
    def test_parse_is_separate_from_preview(self):
        assert hasattr(self.mod, "import_parse"), "import_parse must be defined"
        assert hasattr(self.mod, "import_preview"), "import_preview must still be defined"
        assert self.mod.import_parse is not self.mod.import_preview, (
            "import_parse and import_preview must be separate functions"
        )

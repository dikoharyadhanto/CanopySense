# ANT-WO-004-v0.1 - Migration Repair Work Order

> [!IMPORTANT]
> **Dependencies**: `DIR-DI-001-v1.0`, `GMN-STRAT-001-v1.0`, migration audit performed by ANT on 2026-05-14.
> **Director authorization**: Director approved opening a new WO after ANT detected migration errors and risks.
> **State safety**: `Delta/progress.json`, `project.json`, `Delta/DELTA-REGISTRY.json`, and `~/.delta/project_registry.json` must not be edited manually. Workflow/state repair must use Delta CLI or be escalated to the Director/Delta CLI maintainer if no safe CLI command exists.

## 1. Metadata

| Field         | Value                                                                 |
|:------------- |:--------------------------------------------------------------------- |
| Project ID    | 001                                                                   |
| Document Type | Work Order (WO)                                                       |
| Version       | v0.1                                                                  |
| Status        | PENDING - migration repair scope issued for CDC/admin planning        |
| Created by    | ANT (Technical Foreman)                                               |
| Issued to     | CDC (Lead Developer) plus Director/admin for CLI-managed state repair |
| Task Title    | Repair post-migration path, test, and Delta integrity drift           |

## 2. Readiness Audit

| Check                      | Result                                                                                                                                         |
|:-------------------------- |:---------------------------------------------------------------------------------------------------------------------------------------------- |
| DI file exists             | PASS: `Delta/01_Strategy/DIR-DI-001-v1.0.md` exists                                                                                            |
| STRAT file exists          | PASS: `Delta/01_Strategy/GMN-STRAT-001-v1.0.md` exists                                                                                         |
| STRAT audit gate           | PASS: Director, GPT, and PPX are APPROVED per `delta audit status --strat GMN-STRAT-001-v1.0.md`                                               |
| CLI formal state           | WARNING: session bootstrap reports DI and STRAT locked, active WO now `ANT-WO-004-v0.1.md` PENDING                                             |
| CLI effective integrity    | FAIL: `delta refresh` reports duplicate/missing DI entries and effective `GMN-STRAT-001-v1.0.md` BLOCKED                                       |
| Registry validation        | FAIL: `delta sync registry` reports `CLAUDE.md` and `GEMINI.md` missing despite root files existing                                            |
| v0.4 artifact registration | FAIL: `ANT-STR-003-v0.4.md`, `CDC-IMPL-003-v0.4.md`, and `CDC-WALK-003-v0.4.md` exist on disk but are not surfaced by CLI status/list commands |

## 3. Problem Summary

The migration from legacy project-layer directories (`03_Build/`, `04_Test/`) into the current project-layer layout (`src/`, `tests/`) left stale paths in source code, test infrastructure, and governance evidence. Basic Python compilation passes, but executable validation is degraded:

- `tests/run_test.py` fails with `ModuleNotFoundError: No module named 'core_engine'` because it still inserts `03_Build` into `sys.path`.
- `tests/docker-compose.yml` references `04_Test/Dockerfile.patcher`, which does not exist.
- `tests/Dockerfile.patcher` copies from `04_Test/` and `03_Build/`, which do not exist.
- `tests/generate_test_blocks.py` expects `tests/Dummy_rubber_estate_SHP/dummy_rubber_estate.shp`, but no `.shp` or `.geojson` test fixture exists in the project layer.
- Multiple runtime modules still default to `04_Test/.env` or `04_Test/result_output`.
- Delta CLI integrity currently reports stale/broken DI state entries and registry path-resolution drift.

## 4. Scope

### 4.1 CDC-Owned Source/Test Repair

CDC shall repair the migrated project-layer code and test infrastructure so the current `src/` and `tests/` layout is executable without legacy root folders.

Required work:

1. Update active runtime paths from legacy `03_Build/` and `04_Test/` to current `src/` and `tests/` locations where those paths affect execution.
2. Repair `tests/run_test.py` so it imports `core_engine` from `src/` and fails only on legitimate external prerequisites, not path migration errors.
3. Repair Docker integration files:
   - `tests/docker-compose.yml` must reference the actual Dockerfile path.
   - `tests/Dockerfile.patcher` must copy `tests/requirements_local.txt` and the current source package from `src/`.
   - Container working directory/import path must allow `patcher_local.py` to run.
4. Repair local env/output path defaults in source modules that still use `04_Test/.env` or `04_Test/result_output`.
5. Provide a deterministic local test fixture path:
   - either commit a small `tests/test_blocks.geojson` fixture, or
   - make `tests/generate_test_blocks.py` use an existing project shapefile via explicit configuration and fail with an actionable message when missing.
6. Update user-facing runtime docs only where stale commands would make the repaired scripts fail.

### 4.2 Delta/Admin-Owned Governance Repair

CDC must not directly edit CLI-managed state files. Director/admin or Delta CLI maintainer shall repair or provide a safe command path for:

1. Removing or superseding stale duplicate DI entries:
   - `Delta/01_Strategy/DIR-DI-001-v1.0.md` recorded with path `Delta/01_Strategy/Delta/01_Strategy/DIR-DI-001-v1.0.md`
   - `01_Strategy/DIR-DI-001-v1.0.md` recorded with path `Delta/01_Strategy/01_Strategy/DIR-DI-001-v1.0.md`
2. Restoring `GMN-STRAT-001-v1.0.md` effective status from BLOCKED to healthy after the DI dependency drift is resolved.
3. Reconciling `Delta/DELTA-REGISTRY.json` validation for root bridge files:
   - `CLAUDE.md`
   - `GEMINI.md`
4. Registering or intentionally retiring v0.4 artifacts that exist on disk but are not reflected by CLI list/status:
   - `Delta/02_Blueprint/ANT-STR-003-v0.4.md`
   - `Delta/03_Build/CDC-IMPL-003-v0.4.md`
   - `Delta/03_Build/CDC-WALK-003-v0.4.md`

If the current Delta CLI has no non-destructive command for any item above, CDC/ANT shall halt that item and return a concise escalation note to the Director instead of editing JSON manually.

## 5. Success Indicators

This WO is successful when all applicable checks below pass, or when any blocked governance item has a documented Director/admin escalation:

1. `python -m compileall src tests` exits 0.
2. `python tests/run_test.py` no longer fails on `ModuleNotFoundError` caused by `03_Build` migration drift.
3. `python tests/generate_test_blocks.py` either produces `tests/test_blocks.geojson` from an available fixture/source, or fails with an explicit actionable configuration message.
4. `docker compose -f tests/docker-compose.yml config` resolves a Dockerfile and copy paths that exist in the migrated project.
5. If Docker is available, the local PostGIS/patcher simulation can be run or a clear environment limitation is recorded.
6. `rg "03_Build|04_Test" src tests` contains no execution-affecting stale paths. Historical comments may remain only if they are clearly marked as legacy and cannot mislead runtime behavior.
7. `delta refresh` reports 0 integrity issues after authorized Delta/admin repair, or records an explicit Delta CLI repair gap.
8. `delta sync registry` reports 0 registry issues after authorized Delta/admin repair, or records an explicit Delta CLI repair gap.
9. CLI status/list output is internally consistent for the active WO chain and any v0.4 artifacts intentionally retained.

## 6. Implementation Constraints

- Do not manually edit `Delta/progress.json`, `project.json`, `Delta/DELTA-REGISTRY.json`, or `~/.delta/project_registry.json`.
- Do not delete locked historical WOs or historical implementation evidence.
- Do not move or rewrite locked historical artifacts unless a Delta CLI command explicitly performs the lifecycle operation.
- Preserve the two-layer separation principle:
  - actual source/test code remains in project-layer folders such as `src/` and `tests/`;
  - Delta governance documents remain under `Delta/`.
- Do not commit secrets, service-account keys, real API keys, or contractor credentials.
- Avoid real GEE, GCP, Secret Manager, or contractor PostGIS calls during local migration tests unless the Director explicitly provides credentials and approves the run.
- Prefer backward-compatible path resolution only when it does not hide migration failures. Current `src/` and `tests/` paths are authoritative.

## 7. Authority Levels

| Level                    | Constraint                                                                                                                    |
|:------------------------ |:----------------------------------------------------------------------------------------------------------------------------- |
| Level 1 - Non-negotiable | No manual edits to CLI-managed state/registry files. No deletion of locked history. No secrets in repo.                       |
| Level 2 - Guided         | CDC may choose exact path helper structure, fixture format, and test harness details if success indicators remain measurable. |
| Level 3 - Preference     | Keep path constants centralized where practical and update comments/docs near changed behavior.                               |
| Level 4 - Freedom        | CDC may refactor local test scripts and Docker packaging internals as needed within this WO scope.                            |

## 8. Action Items for CDC

1. Inventory execution-affecting stale path references in `src/` and `tests/`.
2. Patch project-layer source and test files to use the migrated layout.
3. Repair Docker test packaging and validate Docker Compose config.
4. Add or repair deterministic local test fixtures for `tests/run_test.py` and `tests/generate_test_blocks.py`.
5. Run the success-indicator commands and record outputs in CDC-WALK.
6. Produce a short governance repair escalation note for any Delta state/registry item that cannot be fixed through official CLI commands.

## 9. Action Items for Director/Admin

1. Provide or approve a safe Delta CLI/admin method to remove stale duplicate DI state entries.
2. Provide or approve a safe Delta CLI/admin method to reconcile registry validation for root bridge files.
3. Decide whether v0.4 STR/IMPL/WALK disk artifacts should be registered, superseded, or archived through official lifecycle commands.

## 10. Skill Routing Authorization

No external skills authorized for this WO.

## 11. Acceptance and Handoff

CDC may begin only after this WO is locked and same-version STR/IMPL/WALK lifecycle gates are satisfied by Delta CLI. Until then, this document is a pending migration-repair scope and risk record.

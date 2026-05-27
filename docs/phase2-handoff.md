# CanopySense — Phase 2 Pipeline Alignment Handoff

> Updated by DEV at end of Plan Doc v1.4 (Stage 1.4 — Phase 1 Main Product Features per Mockup).
> Previous versions covered Plan v1.2 (pipeline/auth) and Plan v1.3 (backfill integration).
> Intended audience: Plan Doc v1.5 (UX/UI refinement) and Plan Doc v1.6 (deployment/server ops).

---

## 1. What Plan Doc v1.3 Can Safely Assume

### Data pipeline is architecturally sound for Phase 1 scope

- `canopysense.satellite_data` is the single authoritative table for all vegetation index data.
- Write conflict key is `(block_id, acquisition_date, sensor)` — safe for idempotent re-runs.
- All 5 indices (NDVI, EVI, NDRE, SAVI, GNDVI) are stored per block per scene.
  NDRE is NULL for Landsat records (Landsat lacks the red-edge band).
- The `features` JSONB column stores `{"valid_pixel_ratio": <float>, "low_quality": <bool>}`.
- Sensor values in DB: `"sentinel-2"`, `"landsat-8"`, `"landsat-9"` (already normalized).

### API assumptions are valid

- `/api/blocks` returns block geometries from `canopysense.blocks` (with afdeling_id FK).
- Block data for `BLOK_SEMBAWA` estate is seeded and confirmed in local DB.
- Backend auth is JWT-based with `SECRET_KEY`; token expire = 7 days default.
- Schema namespace: `canopysense.*` (all tables).

### What is NOT yet settled for Plan v1.3

- Frontend mock-token fallback (if any remains) should be removed before product feature testing.
- The existing `tests/run_test.py` harness uses a deprecated direct GEE path — it is NOT a
  reliable test oracle for API-to-UI value consistency checks.
- Historical satellite data in local DB depends on whether `historical_backfill.py` was run.
  If satellite_data is empty, the map/dashboard will show no data. Plan v1.3 implementation
  and testing should verify that seeded data exists or document the empty-state UI behavior.

---

## 2. What Plan Doc v1.5 (Deployment) Needs to Know

### Cloud Function deployment

| Item | Current State | Action Required for v1.5 |
| :--- | :--- | :--- |
| Cloud Function source | Deployed 2026-04-24; uses `04_Test/` paths (stale, but harmless at runtime) | Redeploy from `src/deploy/` with updated path constants |
| Canonical deploy source | `src/deploy/` directory | Deploy from this directory using `gcloud functions deploy` |
| Deploy package | `src/deploy/` contains: `main.py`, `engine_launcher.py`, `core_engine/`, `ingestion/` | Verify contents match local before deploy |
| Entry point | `patcher_cloud` (function name in `main.py`) | Unchanged |
| Runtime | python312 | Unchanged |
| Region | asia-southeast2 | Unchanged |
| GCF gen | gen2 (HTTP trigger) | Unchanged |

### Secret Manager

| Secret | Purpose | Owner |
| :--- | :--- | :--- |
| `canopysense-api-key-registry` | Per-contractor API key hashes and metadata | Admin |
| `canopysense-gee-service-account` | GEE service account JSON key | Admin |

Secrets are accessed via `GCP_PROJECT_ID` env var in the Cloud Function. No secrets in code or git.

### Online DB requirements

When deploying online (Plan v1.5), the PostgreSQL/PostGIS instance must have:
- Schema: `canopysense`
- Tables: `estates`, `afdelings`, `blocks`, `satellite_data`, `patcher_run_log`, `users`,
  `companies`, and optionally `backfill_skipped` (for historical backfill runs)
- Unique constraint: `satellite_data(block_id, acquisition_date, sensor)`
- Block data seeded (via `engine_launcher.py --seed-shapefile` or DB import)

### patcher_local.py operational prerequisites

- `CLOUD_FUNCTION_URL` — update to the production Cloud Function URI
- `PATCHER_API_KEY` — issue via Secret Manager API key registry
- `CONTRACTOR_ID` — assign per contractor
- Local PostGIS connection (`PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`, `PGSCHEMA`)

### Historical backfill for production (v1.3 integrated route)

Use `patcher_local.py --backfill` after production DB is live and seeded with blocks.
Default 3-year range. Can be scoped by estate or custom date range.

```bash
# Full backfill, all estates, default 3yr
python3 src/patcher_local.py --backfill

# Estate-scoped backfill
python3 src/patcher_local.py --backfill --estate-id 1

# Custom date range (e.g. smoke test with 1 month)
python3 src/patcher_local.py --backfill --date-start 2024-01 --date-end 2024-01
```

This route goes through the Cloud Function (Option B architecture). Resume guard is built in —
safe to restart if interrupted. `historical_backfill.py` is retained as fallback only.

---

## 3. Pipeline Route Authority Map (v1.3)

| Route | Trigger | Who Runs It | GEE Path | DB Write Path | Frequency |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Weekly scheduled | `patcher_local.py` (cron) | Contractor server | Cloud Function → GEE | patcher_local → PostGIS | Weekly |
| Scheduled (estate scope) | `patcher_local.py --estate-id X` | Manual/cron | Cloud Function → GEE | patcher_local → PostGIS | On-demand |
| Single block upload | `patcher_local.py --estate-id X --afdeling-id Y --block-id Z` | Manual | Cloud Function → GEE | patcher_local → PostGIS | On-demand |
| Historical backfill (integrated) | `patcher_local.py --backfill [--estate-id X] [--date-start Y]` | Admin/ops | Cloud Function → GEE | patcher_local → PostGIS | Once (onboarding) |
| Historical backfill (legacy fallback) | `historical_backfill.py` (DEPRECATED) | Admin/ops | Direct local GEE | historical_backfill → PostGIS | Fallback only |
| Retry (auto) | patcher_local.py retry_map on next scheduled run | Automatic | Cloud Function → GEE | patcher_local → PostGIS | Next run |

### patcher_run_log — New Columns (v1.3)

| Column | Type | Purpose |
| :--- | :--- | :--- |
| `estate_id` | `INTEGER NULL` | Scope for the run; NULL = all estates |
| `date_start` | `DATE NULL` | Window start for backfill chunks |
| `date_end` | `DATE NULL` | Window end for backfill chunks |

New `trigger_mode` value: `'backfill'`. New `status` value: `'NO_NEW_DATA'` (Cloud Function ran, no satellite data for that window — distinct from `FULL_FAILURE`).

For existing installations, run `src/patcher_run_log_migration_v1.3.sql` before deploying patcher_local v1.3.

---

## 4a. Phase 1 Product Feature Deferred Items (v1.4 — Require Director Authorization for Roadmap Stage 1.5+)

| Item | Risk | Roadmap Stage |
| :--- | :--- | :--- |
| Phase 2+ nav pages: Long-Term Trends, Model Studio, Alerts & Tasking, Reports & Export | Low — currently routed to `/unavailable`; no functional pages | Stage 2 feature work |
| Dashboard delta stats (7-day change, annual change) — currently "Coming Soon" | Low — requires historical comparison API not in Phase 1 scope | Stage 1.5 or dedicated summary endpoint |
| Full profile/account page | Low — sidebar shows username/role from JWT; full page is not in Phase 1 mockup | Stage 1.5 UX refinement |
| Token refresh / expiry handling | Low for local demo | Stage 1.5 or 1.6 |
| E2E browser tests (Playwright) | Low — vitest unit tests cover contract and routing | Stage 1.5 |
| Admin/internal UI | Not in Phase 1 scope; no admin seed account in Phase 1 | Stage 1.6 or separate plan |
| CORS hardening (`allow_origins=["*"]`) | Low for local; risk in production | Stage 1.6 deployment |

---

## 4. Known Deferred Items (Post Exec-Lock — Require Director Authorization)

| Item | Risk | Required Timing |
| :--- | :--- | :--- |
| Cloud Function redeploy (TASK-012 / TC-016) | None blocked; path constants + date-threading update | Requires explicit Director authorization at execution moment; staged post exec-lock |
| TC-017/018/019 live smoke tests (weekly, single-block, backfill) | Medium — cannot confirm backfill end-to-end without a real GEE run | Post-redeploy; Director authorization required per FMN constraint |
| Full 3-year backfill operational run (TC-021) | Medium — ~156 chunks, GEE quota + time cost | Director quota review required before execution |
| `tests/run_test.py` legacy harness retirement/update | Medium — misleading test oracle (deprecated direct GEE path) | Future cleanup; not blocking Gate 3 |

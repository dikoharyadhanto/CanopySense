# CanopySense — Environment Variable Reference

## Backend (`backend/` — FastAPI)

| Variable | Default | Required | Description |
| :--- | :--- | :--- | :--- |
| `PGHOST` | `localhost` | Yes | PostgreSQL host |
| `PGPORT` | `5432` | Yes | PostgreSQL port |
| `PGUSER` | `postgres` | Yes | PostgreSQL username |
| `PGPASSWORD` | `postgres` | Yes | PostgreSQL password |
| `PGDATABASE` | `canopysense` | Yes | PostgreSQL database name |
| `SECRET_KEY` | `super_secret_key_change_me_in_production` | Yes | JWT signing key — **must change in production** |
| `ALGORITHM` | `HS256` | No | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `10080` (7 days) | No | JWT expiry in minutes |

> `SECRET_KEY` must be a random, cryptographically strong string in any non-development environment.

---

## Frontend (`frontend/` — Vite)

| Variable | Default | Required | Description |
| :--- | :--- | :--- | :--- |
| `VITE_API_URL` | `http://localhost:8000` | Yes | Backend API base URL (seen by browser) |

In Vite, prefix all environment variables with `VITE_` to expose them to the client bundle.

### Phase 1 Product Flow (v1.4+)

The frontend is a React + Vite SPA with the following routes:

| Route | Auth Required | Description |
| :--- | :--- | :--- |
| `/login` | No | Login page — calls `POST /auth/login` |
| `/dashboard` | Yes | Dashboard with stats, Leaflet map, top-blocks panel |
| `/timeseries` | Yes | Time-series chart for a selected block |
| `/unavailable` | Yes | Phase 2+ placeholder — "Fitur belum tersedia di Phase 1" |

All protected routes (`/dashboard`, `/timeseries`, `/unavailable`) require a valid JWT in
`localStorage` under the key `token`. The sidebar navigation displays username and role decoded
from the JWT for display purposes only. Authorization is enforced by backend endpoints.

Phase 2+ navigation items (Long-Term Trends, Model Studio, Alerts & Tasking, Reports & Export)
are visible in the sidebar but route to `/unavailable`.

---

## Patcher-Local (`src/patcher_local.py`)

Patcher-Local runs on the contractor's local machine or server. It reads blocks from
local PostGIS, sends them to the Cloud Function, and writes satellite index results back.

Copy `src/.env.example` to `tests/.env` and fill in real values before running.

| Variable | Default | Required | Owner Runtime | Description |
| :--- | :--- | :--- | :--- | :--- |
| `CLOUD_FUNCTION_URL` | — | **Required** | Local | Full HTTPS URI of the deployed Cloud Function. Current: `https://patcher-cloud-7dzkvzbnfq-et.a.run.app` |
| `PATCHER_API_KEY` | — | **Required** | Local | Contractor API key — stored in Secret Manager on GCP side; never commit this value |
| `CONTRACTOR_ID` | — | **Required** | Local | Contractor identifier string (e.g. `CONTRACTOR_DASMAP`) |
| `PGDATABASE` | — | **Required** | Local | Local PostgreSQL database name |
| `PGUSER` | — | **Required** | Local | Local PostgreSQL username |
| `PGPASSWORD` | `""` | Optional | Local | Local PostgreSQL password |
| `PGHOST` | `localhost` | Optional | Local | Local PostgreSQL host |
| `PGPORT` | `5432` | Optional | Local | Local PostgreSQL port |
| `PGSCHEMA` | `canopysense` | Optional | Local | PostgreSQL schema for `patcher_run_log` and `satellite_data` writes |
| `FUNCTION_TIMEOUT_SECONDS` | `120` | Optional | Local | HTTP timeout for Cloud Function call (seconds) |
| `BATCH_MODE` | `afdeling` | Optional | Local | Batch grouping strategy: `afdeling` (default) or `none` |
| `PATCHER_API_VERSION` | `1.1` | Optional | Local | Expected `api_version` in Cloud Function response; mismatch logs a warning but does not fail |

---

## Cloud Function (`src/deploy/main.py` = `src/patcher_cloud_function.py`)

The Cloud Function runs in GCP (region: `asia-southeast2`, project: `canopysense`).
These environment variables are configured in Cloud Function deployment settings —
**never** committed to git.

| Variable | Default | Required | Description |
| :--- | :--- | :--- | :--- |
| `GCP_PROJECT_ID` | — | **Required** | GCP project ID (`canopysense`) |
| `SECRET_NAME` | `canopysense-api-key-registry` | Optional | Secret Manager secret name for the API key registry |
| `GEE_SECRET_NAME` | `canopysense-gee-service-account` | Optional | Secret Manager secret name for the GEE service account JSON key |
| `LOG_LEVEL` | `INFO` | Optional | Cloud Function log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `FUNCTION_TIMEOUT_SECONDS` | `120` | Optional | Max seconds the Cloud Function allows for core engine execution |
| `LOCAL_REGISTRY_JSON` | — | Optional (dev only) | Bypass Secret Manager for local testing; set to raw JSON registry string |

> **Cloud Function does NOT use any PostgreSQL env vars.** As of v0.9, the Cloud Function
> has no outbound DB connection. All DB writes are handled by Patcher-Local on the contractor side.

---

## Patcher-Local — CLI Reference (v1.3)

```
# Scheduled — all estates (default weekly behavior)
python3 src/patcher_local.py

# Scheduled — estate scope
python3 src/patcher_local.py --estate-id 1

# Scheduled — afdeling scope (requires --estate-id)
python3 src/patcher_local.py --estate-id 1 --afdeling-id 2

# Upload — single block (requires --estate-id and --afdeling-id)
python3 src/patcher_local.py --estate-id 1 --afdeling-id 2 --block-id 42

# Backfill — all estates, default 3-year range
python3 src/patcher_local.py --backfill

# Backfill — estate scope with custom range
python3 src/patcher_local.py --backfill --estate-id 1 --date-start 2024-01 --date-end 2024-03
```

CLI hierarchy rule: `--block-id` requires `--afdeling-id` AND `--estate-id`. `--afdeling-id` requires `--estate-id`.

---

## Operational Route Contract (v1.3)

| Mode | CLI | Scope | DB trigger_mode | Cloud Function Date Window |
| :--- | :--- | :--- | :--- | :--- |
| Scheduled (all) | `patcher_local.py` | All estates | `scheduled` | today−7 (default) |
| Scheduled (estate) | `--estate-id X` | Estate X | `scheduled` | today−7 |
| Scheduled (afdeling) | `--estate-id X --afdeling-id Y` | Afdeling Y | `scheduled` | today−7 |
| Upload (block) | `--estate-id X --afdeling-id Y --block-id Z` | Block Z | `upload` | today−7 |
| Backfill (all) | `--backfill` | All estates | `backfill` | Chunks: default 3yr |
| Backfill (estate) | `--backfill --estate-id X` | Estate X | `backfill` | Chunks: default 3yr |
| Backfill (custom range) | `--backfill --date-start YYYY-MM --date-end YYYY-MM` | Per scope | `backfill` | Supplied chunks |

---

## Historical Backfill (deprecated standalone — `src/historical_backfill.py`)

**DEPRECATED.** Use `patcher_local.py --backfill` for all new historical backfill operations.
`historical_backfill.py` is retained as a documented fallback only. It bypasses the Cloud
Function and connects directly to GEE — do not use for routine operations.

Uses the same local PostGIS env vars as Patcher-Local (`PGHOST`, `PGPORT`, `PGDATABASE`,
`PGUSER`, `PGPASSWORD`). Loads from `tests/.env` if present.

GEE access requires `EE_SERVICE_ACCOUNT`, `EE_SERVICE_ACCOUNT_KEY_JSON`, or
`EE_PROJECT_ID` env vars (or a valid initialized EE environment).

---

## Pipeline Architecture — Env Summary by Runtime

| Env Var | patcher_local | Cloud Function | historical_backfill | Backend |
| :--- | :---: | :---: | :---: | :---: |
| `CLOUD_FUNCTION_URL` | ✓ | — | — | — |
| `PATCHER_API_KEY` | ✓ | — | — | — |
| `CONTRACTOR_ID` | ✓ | — | — | — |
| `PGHOST/PORT/DB/USER/PASSWORD` | ✓ | — | ✓ | ✓ |
| `PGSCHEMA` | ✓ | — | — | — |
| `GCP_PROJECT_ID` | — | ✓ | — | — |
| `SECRET_NAME` | — | ✓ | — | — |
| `GEE_SECRET_NAME` | — | ✓ | — | — |
| `FUNCTION_TIMEOUT_SECONDS` | ✓ | ✓ | — | — |
| `SECRET_KEY` | — | — | — | ✓ |

---

## Secret Handling Rules

1. **Never commit** API keys, service account JSON, DB passwords, or Secret Manager values to git.
2. **Local secrets** (PATCHER_API_KEY, PGPASSWORD) live only in `tests/.env` — gitignored.
3. **Cloud secrets** (GEE service account, API key registry) live in GCP Secret Manager — not in env files.
4. **Rotations**: Contact administrator to rotate `PATCHER_API_KEY`; `SECRET_Name` / `GEE_SECRET_NAME` are updated via Secret Manager directly.

---

## Direct GEE Test Harness Note (`tests/run_test.py`)

`tests/run_test.py` is a legacy test harness that exercises a **direct GEE → GCS export path**.
This harness uses a different architecture than the operational path and may fail if the
GEE service account lacks `storage.objects.create` on the GCS bucket.

This is **separate from the accepted operational path**, where:
- `patcher_local.py` sends blocks to the Cloud Function via HTTP
- The Cloud Function calls GEE internally and returns results
- `patcher_local.py` writes results to local PostGIS

The legacy harness failure does not indicate a production pipeline issue.

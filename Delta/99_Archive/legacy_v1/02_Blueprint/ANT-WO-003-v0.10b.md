---
name: ANT-WO-003-v0.10b
project: Canopy Sense
phase: Tahap III (Architecture Upgrade): Local Simulation Environment for ANT-STR-003-v0.10
status: PENDING — Awaiting CDC walkthrough
version: 0.10b
created_date: 2026-04-24
prerequisite: ANT-WO-003-v0.10 COMPLETE
linked_str: ANT-STR-003-v0.10
---

# ANT-WO-003-v0.10b (Work Order)

> [!IMPORTANT]
> **Lead Developer (CDC):** This Work Order builds the local simulation environment required to execute ANT-STR-003-v0.10 Phases A–F. This is test infrastructure — not product code. All new files go in `04_Test/` at the project root. Zero changes to `03_Build/` files.

---

## 1. Background and Motivation

ANT-STR-003-v0.10 test phases require a running PostGIS database and a patcher runtime that mirrors the real Dasmap contractor deployment. The simulation uses two separate Docker containers:

- **`postgis` container** — represents Dasmap's database server
- **`patcher` container** — represents Dasmap's application server running `patcher_local.py`

These are kept separate to accurately reflect the real deployment topology where the application and database always run on different machines. Combining them in one container would test a scenario that will never exist in production.

Phase D additionally requires a lightweight local mock that returns a two-entry `writes` response without calling GEE, so Patcher-Local's generic write loop can be tested without a live Cloud Function.

---

## 2. Technical Tasks (Scope)

### 2.1 Deliverables

All files in `04_Test/` (project root):

| File | Purpose |
|------|---------|
| `04_Test/docker-compose.yml` | Defines `postgis` and `patcher` services |
| `04_Test/Dockerfile.patcher` | Patcher container — Python 3.11-slim + minimal deps |
| `04_Test/init.sql` | Schema, table DDL, and seed data |
| `04_Test/requirements_local.txt` | Minimal Python deps for patcher container |
| `04_Test/.env.test.example` | Env template — committed, no secrets |
| `04_Test/mock_cloud.py` | Phase D static two-entry writes mock (stdlib only) |
| `.gitignore` | Add `04_Test/.env.test` entry |

---

### 2.2 `docker-compose.yml` — Service Specification

**`postgis` service:**
- Image: `postgis/postgis:15-3.3`
- Database: `canopysense_test`, user: `patcher`, password: `patcher_test`
- Mount `./init.sql` to `/docker-entrypoint-initdb.d/init.sql`
- Expose host port `5433` → container port `5432` (avoids conflict with local postgres)
- Healthcheck: `pg_isready -U patcher -d canopysense_test`

**`patcher` service:**
- Build context: `..` (project root, from `04_Test/`), dockerfile: `04_Test/Dockerfile.patcher`
  — project root is required so the Dockerfile can `COPY` from both `04_Test/` and `03_Build/`
- `depends_on: postgis: condition: service_healthy`
- Env vars — hardcode infrastructure vars directly in `environment:`, pull secrets from `.env.test`:
  - `PGHOST=postgis` (internal Docker network — service name)
  - `PGPORT=5432`
  - `PGDATABASE=canopysense_test`
  - `PGUSER=patcher`
  - `PGPASSWORD=patcher_test`
  - `PGSCHEMA=canopysense`
  - `FUNCTION_TIMEOUT_SECONDS=120`
  - `PATCHER_API_VERSION=1.1`
  - `CLOUD_FUNCTION_URL`, `PATCHER_API_KEY`, `CONTRACTOR_ID` — via `env_file: .env.test`
- `extra_hosts: ["host.docker.internal:host-gateway"]` — Linux host access for Phase D
- Default command: `python3 patcher_local.py`

---

### 2.3 `Dockerfile.patcher`

- Base image: `python:3.11-slim`
- `WORKDIR /app`
- `COPY 04_Test/requirements_local.txt /tmp/requirements.txt` — accessible because build context is project root
- `RUN pip install --no-cache-dir -r /tmp/requirements.txt`
- `COPY 03_Build/ /app/`
- `CMD ["python3", "patcher_local.py"]`

No `ENTRYPOINT` — `CMD` allows `docker-compose run --rm patcher python3 -c "..."` override used in Phase 0-4 verification steps.

Note: `patcher_local.py` looks for `_ENV_FILE` at `../04_Test/.env` relative to its location. Inside the container that path does not exist — `_load_env()` falls through to `load_dotenv(override=False)` and picks up env vars injected by docker-compose. No code change needed.

---

### 2.4 `init.sql` — Schema, Tables, Seed Data

Execute in this order:

**1. Extensions and schemas:**
```sql
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE SCHEMA IF NOT EXISTS canopysense;
CREATE SCHEMA IF NOT EXISTS testschema;
```

**2. `canopysense.blocks`** (read source for patcher_local.py):
```
id            SERIAL PRIMARY KEY
code          TEXT NOT NULL
name          TEXT NOT NULL
afdeling_id   INTEGER NOT NULL
geometry      geometry(Polygon, 4326) NOT NULL
```

Seed data — minimum 4 blocks, covering two afdelings:

| id | code | name | afdeling_id | geometry |
|----|------|------|-------------|---------|
| 1 | BLK-001 | Block 1 | 1 | small polygon EPSG:4326 |
| 2 | BLK-002 | Block 2 | 1 | small polygon EPSG:4326 |
| 3 | BLK-003 | Block 3 | 1 | small polygon EPSG:4326 |
| 18 | BLK-018 | Block 18 | 2 | polygon from STR Test A-1 |

Use `ST_GeomFromText('POLYGON(...)', 4326)` with valid small polygons. Block 18 must use the geometry from STR Test A-1: `[[[108.0,-1.0],[108.1,-1.0],[108.1,-1.1],[108.0,-1.1],[108.0,-1.0]]]`.

**3. `canopysense.satellite_data`** (output table, starts empty):
```
block_id         INTEGER        NOT NULL
acquisition_date DATE           NOT NULL
sensor           VARCHAR(20)    NOT NULL
cloud_cover      FLOAT
ndvi             FLOAT
evi              FLOAT
ndre             FLOAT
savi             FLOAT
gndvi            FLOAT
features         JSONB
PRIMARY KEY (block_id, acquisition_date, sensor)
```

**4. `canopysense.patcher_run_log`** — use exact DDL from `03_Build/patcher_run_log_ddl.sql` (copy it verbatim into init.sql).

**5. `canopysense.patcher_write_test`** (Phase D forward-compat test table, starts empty):
```
block_id         INTEGER     NOT NULL
acquisition_date DATE        NOT NULL
sensor           VARCHAR(20) NOT NULL
test_value       TEXT
PRIMARY KEY (block_id, acquisition_date, sensor)
```

**6. `testschema` mirrors** (Phase C custom schema test, start empty):
```sql
CREATE TABLE testschema.satellite_data (LIKE canopysense.satellite_data INCLUDING ALL);
CREATE TABLE testschema.patcher_run_log (LIKE canopysense.patcher_run_log INCLUDING ALL);
```

---

### 2.5 `requirements_local.txt`

Three packages — no GEE, no geopandas:
```
psycopg2-binary>=2.9
requests>=2.28
python-dotenv>=1.0
```

---

### 2.6 `.env.test.example`

```
CLOUD_FUNCTION_URL=https://asia-southeast2-canopysense.cloudfunctions.net/patcher_cloud
PATCHER_API_KEY=your-api-key-here
CONTRACTOR_ID=CONTRACTOR_DASMAP
PGSCHEMA=canopysense
FUNCTION_TIMEOUT_SECONDS=120
PATCHER_API_VERSION=1.1
```

This file is committed. The real `.env.test` (with actual secrets) must not be committed.

---

### 2.7 `mock_cloud.py` — Phase D Static Mock (≤80 lines, stdlib only)

A minimal `http.server`-based mock. No Flask, no third-party deps.

**Behavior:**
- `POST /` without `X-API-Key` header → HTTP 401
- `POST /` with any `X-API-Key` value → HTTP 200 with static two-entry `writes` response
- Adds `"timestamp"` dynamically at serve time
- Logs each request to stdout

**Static response contract (exact structure):**
```json
{
  "status": "success",
  "api_version": "1.1",
  "contractor_id": "CONTRACTOR_DASMAP",
  "rows_returned": 2,
  "errors": [],
  "writes": [
    {
      "table": "satellite_data",
      "columns": ["block_id","acquisition_date","sensor","cloud_cover","ndvi","evi","ndre","savi","gndvi","features"],
      "conflict_columns": ["block_id","acquisition_date","sensor"],
      "presence_check": {"block_id_column":"block_id","recency_column":"acquisition_date","recency_days":14},
      "records": [
        {
          "block_id": "18",
          "acquisition_date": "2026-04-18",
          "sensor": "sentinel-2",
          "cloud_cover": "3.20",
          "ndvi": "0.6124",
          "evi": "0.3891",
          "ndre": "0.4201",
          "savi": "0.5012",
          "gndvi": "0.5534",
          "features": "{\"valid_pixel_ratio\": 0.968, \"low_quality\": false}"
        }
      ]
    },
    {
      "table": "patcher_write_test",
      "columns": ["block_id","acquisition_date","sensor","test_value"],
      "conflict_columns": ["block_id","acquisition_date","sensor"],
      "presence_check": null,
      "records": [
        {
          "block_id": "18",
          "acquisition_date": "2026-04-18",
          "sensor": "sentinel-2",
          "test_value": "stage2_test"
        }
      ]
    }
  ]
}
```

Run with: `python3 04_Test/mock_cloud.py`
Listens on `0.0.0.0:8080`.

---

## 3. Success Indicators

| Indicator | How to Verify |
|-----------|--------------|
| `docker-compose up -d` completes without error | `docker-compose ps` — both containers `running` / `healthy` |
| All required tables exist in PostGIS | `\dt canopysense.*` lists 4 tables; `\dt testschema.*` lists 2 |
| `blocks` seeded with block_id 18 | `SELECT id FROM canopysense.blocks WHERE id=18` returns 1 row |
| Patcher container connects to PostGIS | `psycopg2.connect` from container prints `PostGIS OK` |
| `patcher_local.py --help` exits 0 in container | No import errors |
| `mock_cloud.py` returns HTTP 401 on missing key | `curl -X POST localhost:8080` → 401 |
| `mock_cloud.py` returns HTTP 200 with `writes` length 2 | `curl -H "X-API-Key: test" -X POST localhost:8080 \| jq '.writes \| length'` → 2 |
| `.env.test` not committed | `git status` does not list `04_Test/.env.test` |

---

## 4. Implementation Constraints

| Constraint | Rule |
|-----------|------|
| File location | All new files in `04_Test/` — zero changes to `03_Build/` |
| `patcher_local.py` | No modifications — runs unmodified inside the container |
| Patcher container deps | `requirements_local.txt` only — no GEE, no geopandas |
| `mock_cloud.py` | stdlib only (`http.server`, `json`, `datetime`) — no pip installs |
| Secrets | `.env.test` must not be committed; only `.env.test.example` is committed |
| PostGIS port | `5433` on host — avoids conflict with any local postgres on `5432` |
| `host.docker.internal` | Must work on Linux via `extra_hosts: host-gateway` |

---

## 5. Deliverables Checklist

| Deliverable | Type | Owner | Status |
|------------|------|-------|--------|
| `04_Test/docker-compose.yml` | New file | CDC | Pending |
| `04_Test/Dockerfile.patcher` | New file | CDC | Pending |
| `04_Test/init.sql` | New file | CDC | Pending |
| `04_Test/requirements_local.txt` | New file | CDC | Pending |
| `04_Test/.env.test.example` | New file | CDC | Pending |
| `04_Test/mock_cloud.py` | New file | CDC | Pending |
| `.gitignore` | Update — add `04_Test/.env.test` | CDC | Pending |

---

## 6. Notes for CDC

1. **`_ENV_FILE` path inside container:** `patcher_local.py` resolves `_ENV_FILE` to `/app/../04_Test/.env`. This path does not exist inside the container — `_load_env()` silently falls through to `load_dotenv(override=False)`, which reads from docker-compose env injection. This is correct behavior. No code change.

2. **`host.docker.internal` on Linux:** The `extra_hosts: ["host.docker.internal:host-gateway"]` entry in docker-compose.yml is required for Phase D on Linux. On macOS and Windows (Docker Desktop), this resolves automatically. Adding the entry does no harm on non-Linux systems.

3. **Block 18 geometry:** Use the exact polygon from STR Test A-1 — `POLYGON((108.0 -1.0, 108.1 -1.0, 108.1 -1.1, 108.0 -1.1, 108.0 -1.0))` in EPSG:4326. This ensures Phase D's `--block-id 18` finds the block and the presence check query succeeds.

4. **`acquisition_date` in mock response:** The static date `2026-04-18` is within 14 days of `2026-04-24` (test date). The presence check `acquisition_date >= CURRENT_DATE - INTERVAL '14 days'` will pass. If you run this test significantly later, update the date in `mock_cloud.py`.

5. **`testschema` tables created empty:** `init.sql` creates the testschema tables with no seed data. Phase C verifies that data goes there only when `PGSCHEMA=testschema`. The tables must not have data before Phase C runs.

6. **`patcher_write_test` in `canopysense` schema only:** This table exists only in `canopysense`, not in `testschema`. Phase D uses the default `PGSCHEMA=canopysense`.

---

**ANT (Technical Foreman) Sign-off**: ISSUED
**Date:** 2026-04-24

**Next Steps:**
1. CDC reads this WO + updated `ANT-STR-003-v0.10.md` (Phase 0)
2. CDC submits walkthrough (`CDC-WALK-003-v0.10b.md`)
3. ANT approves walkthrough
4. CDC implements and submits `CDC-IMPL-003-v0.10b.md`
5. ANT executes ANT-STR-003-v0.10 Phases 0–F

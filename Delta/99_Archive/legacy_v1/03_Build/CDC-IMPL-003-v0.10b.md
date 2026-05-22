---
name: CDC-IMPL-003-v0.10b
type: implementation-log
version: 0.10b
linked_wo: ANT-WO-003-v0.10b
linked_walk: CDC-WALK-003-v0.10b
status: COMPLETE
created_date: 2026-04-24
---

# CDC-IMPL-003-v0.10b — Implementation Log

---

## 1. Deliverables Status

| Deliverable | Status | Notes |
|------------|--------|-------|
| `04_Test/docker-compose.yml` | DONE | context: .. (project root) per ANT FLAG-1 approval |
| `04_Test/Dockerfile.patcher` | DONE | 6 lines |
| `04_Test/init.sql` | DONE | 6 sections, all IF NOT EXISTS guards |
| `04_Test/requirements_local.txt` | DONE | 3 packages, no GEE/geopandas |
| `04_Test/.env.test.example` | DONE | Exact content from WO 2.6 |
| `04_Test/mock_cloud.py` | DONE | 62 lines (target ≤80) |
| `.gitignore` | DONE | `04_Test/.env.test` added under `# Environment` |

Zero changes to any file in `03_Build/`. `patcher_local.py` unmodified.

---

## 2. Implementation Decisions

### 2.1 Build context — FLAG-1 resolution
ANT approved using `context: ..` (project root) in `docker-compose.yml` instead of the WO's original `context: ../03_Build`. The Dockerfile COPY paths reflect this:
```
COPY 04_Test/requirements_local.txt /tmp/requirements.txt
COPY 03_Build/ /app/
```

### 2.2 Patcher service env injection — two-layer approach
`env_file: .env.test` injects the secret vars (CLOUD_FUNCTION_URL, PATCHER_API_KEY, CONTRACTOR_ID, PGSCHEMA, FUNCTION_TIMEOUT_SECONDS, PATCHER_API_VERSION) from the host `.env.test` file. `environment:` injects the hardcoded network vars (PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD). `environment:` takes precedence over `env_file:` for any key conflicts — there are none in the current `.env.test.example`, so both layers are additive.

### 2.3 `extra_hosts` — Linux Phase D requirement
`extra_hosts: ["host.docker.internal:host-gateway"]` added to patcher service. On macOS/Windows Docker Desktop, `host.docker.internal` resolves automatically. The extra_hosts entry is a no-op on those platforms — adding it causes no harm.

### 2.4 init.sql — blocks sequence reset
After inserting seed blocks with explicit IDs (1, 2, 3, 18), the SERIAL sequence is reset:
```sql
SELECT setval(pg_get_serial_sequence('canopysense.blocks', 'id'),
    (SELECT MAX(id) FROM canopysense.blocks));
```
Without this, the next auto-generated id would start at 1 and collide with the seed data. This is safe to run even if `ON CONFLICT DO NOTHING` skips all inserts — `setval` with the current MAX is idempotent.

### 2.5 `patcher_run_log_ddl.sql` — verbatim paste
Section 4 of `init.sql` contains the full verbatim content of `03_Build/patcher_run_log_ddl.sql`, including header comment and original inline comments. The DDL already has `IF NOT EXISTS` on the table and indexes — safe to run on an existing database.

### 2.6 `testschema` mirrors — FLAG-2 accepted
`testschema.satellite_data` and `testschema.patcher_run_log` are created with `LIKE ... INCLUDING ALL`. The `IF NOT EXISTS` guard is added to both for idempotency. For `testschema.patcher_run_log`, the `id` column shares the `canopysense.patcher_run_log_id_seq` sequence (FLAG-2, accepted by ANT). Phase C verifies row presence and `status` values — not ID ordering — so this is non-blocking.

### 2.7 mock_cloud.py — shallow copy for timestamp injection
```python
resp = {**_RESPONSE, "timestamp": datetime.now(timezone.utc).isoformat()}
```
This creates a shallow copy and adds the `timestamp` key. The nested `writes` list is the same reference as `_RESPONSE["writes"]` — read-only in `json.dumps()`, no mutation risk. Each request gets a fresh timestamp without copying the large nested structure.

### 2.8 mock_cloud.py — 401 response includes api_version
The 401 response body includes `"api_version": "1.1"` to match the Cloud Function's error response contract (tested by Phase A-3). Consistent with WO section 2.7 behavior spec.

---

## 3. Line Count Verification

| File | Target | Actual |
|------|--------|--------|
| `04_Test/mock_cloud.py` | ≤80 | **62** |

---

## 4. Security Note (non-blocking, local-only risk)

`COPY 03_Build/ /app/` in the Dockerfile copies the entire `03_Build/` directory including `03_Build/.env.cloud.local` (which exists locally but is untracked). This file would land in the local Docker image layer. Risk is local-only: the image is never pushed to a registry in this test workflow. No fix taken to stay within WO deliverable scope. ANT may choose to add a project-root `.dockerignore` in a future WO if image push capability is added.

---

## 5. WO Success Indicator Self-Check

| Indicator | Implementation | Pass |
|-----------|---------------|------|
| `docker-compose up -d` completes | Correct image tag, 5-retry healthcheck, `depends_on: service_healthy` | Expected ✓ |
| 4 tables in `canopysense.*`, 2 in `testschema.*` | `init.sql` creates all 6 tables with `IF NOT EXISTS` | Expected ✓ |
| `blocks` seeded with block_id 18 | Explicit INSERT with `ON CONFLICT (id) DO NOTHING` | Expected ✓ |
| Patcher → PostGIS connectivity | Internal Docker network; `PGHOST=postgis` env var | Expected ✓ |
| `--help` exits 0 | python:3.11-slim + 3 deps cover all patcher_local.py imports | Expected ✓ |
| mock 401 on missing `X-API-Key` | `do_POST` checks header before processing | Expected ✓ |
| mock 200 with `writes` length 2 | `_RESPONSE["writes"]` has exactly 2 entries | Expected ✓ |
| `.env.test` not committed | `.gitignore` entry `04_Test/.env.test` added | Expected ✓ |

---

## 6. Constraint Compliance

| Constraint | Status |
|-----------|--------|
| All new files in `04_Test/` (except .gitignore) | ✓ |
| Zero changes to `03_Build/` | ✓ |
| `patcher_local.py` unmodified | ✓ |
| `requirements_local.txt` — no GEE, no geopandas | ✓ |
| `mock_cloud.py` — stdlib only | ✓ (json, datetime, http.server) |
| Secrets — `.env.test` not committed | ✓ |
| PostGIS port 5433 on host | ✓ |
| `host.docker.internal` via `extra_hosts` | ✓ |

---

**CDC Status: COMPLETE — Ready for ANT to execute ANT-STR-003-v0.10 Phases 0–F.**

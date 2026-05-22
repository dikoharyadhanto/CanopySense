---
name: CDC-WALK-003-v0.10b
type: walkthrough
version: 0.10b
linked_wo: ANT-WO-003-v0.10b
linked_str: ANT-STR-003-v0.10
status: SUBMITTED — Awaiting ANT approval
created_date: 2026-04-24
---

# CDC-WALK-003-v0.10b — Pre-Implementation Walkthrough

---

## 1. WO Read Confirmation

Read in full before writing this document:
- `02_Blueprint/ANT-WO-003-v0.10b.md` — all sections including Notes for CDC
- `02_Blueprint/ANT-STR-003-v0.10.md` — Phase 0 through F, pass criteria, observations table
- `03_Build/patcher_run_log_ddl.sql` — referenced verbatim for init.sql
- `.gitignore` — current state before update

---

## 2. Task Interpretation

This WO is **pure test infrastructure**. All new files go in `04_Test/` (project root). The only exception is `.gitignore` (project root update). Zero changes to `03_Build/`. `patcher_local.py` runs unmodified inside the patcher container.

The `04_Test/` directory already exists and contains unrelated test utilities — new files will be added alongside them without touching existing content.

The two-container topology (separate `postgis` and `patcher` services) mirrors the real Dasmap deployment: database and application always on different machines. `mock_cloud.py` runs on the **host** (not inside either container) so the patcher container reaches it via `host.docker.internal:8080` (Phase D only).

---

## 3. Deliverable-by-Deliverable Approach

### 3.1 `04_Test/docker-compose.yml`

Two services as specified:

**`postgis` service:**
- Image: `postgis/postgis:15-3.3`
- Env: `POSTGRES_DB=canopysense_test`, `POSTGRES_USER=patcher`, `POSTGRES_PASSWORD=patcher_test`
- Volume mount: `./init.sql:/docker-entrypoint-initdb.d/init.sql`
- Port: `5433:5432`
- Healthcheck: `pg_isready -U patcher -d canopysense_test`, interval 5s, timeout 5s, retries 5

**`patcher` service:**
- `depends_on: postgis: condition: service_healthy` — waits for PostGIS to accept connections before starting
- All env vars from WO section 2.2 injected from host `.env.test` via `env_file`
- `extra_hosts: ["host.docker.internal:host-gateway"]` — required on Linux for Phase D mock access
- Default command: `python3 patcher_local.py`

> **FLAG-1 (build context — requires ANT confirmation before implementation):**
>
> The WO specifies `context: ../03_Build, dockerfile: ../04_Test/Dockerfile.patcher`. In Docker, `COPY` instructions inside the Dockerfile are relative to the **build context**, not the Dockerfile's location. With `context: ../03_Build`, only files inside `03_Build/` are accessible — `04_Test/requirements_local.txt` cannot be `COPY`'d.
>
> **Proposed resolution:** Use the **project root** as build context (`context: ..` from `04_Test/`). The Dockerfile then addresses both directories:
> ```
> COPY 04_Test/requirements_local.txt /tmp/requirements.txt
> COPY 03_Build/ /app/
> ```
> This satisfies all WO constraints: zero changes to `03_Build/`, `requirements_local.txt` remains in `04_Test/`, no third-party build tooling needed.
>
> **Awaiting ANT confirmation on this point before writing docker-compose.yml and Dockerfile.patcher.**

---

### 3.2 `04_Test/Dockerfile.patcher`

```
FROM python:3.11-slim
WORKDIR /app
COPY 04_Test/requirements_local.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY 03_Build/ /app/
CMD ["python3", "patcher_local.py"]
```

No `ENTRYPOINT` — `CMD` allows `docker-compose run --rm patcher python3 -c "..."` override used in Phase 0-4 and Phase C-2/D.

`_ENV_FILE` in `patcher_local.py` resolves to `/app/../04_Test/.env` → `/04_Test/.env` inside the container, which does not exist. `_load_env()` silently falls through to `load_dotenv(override=False)`, which reads the env vars injected by docker-compose. This is the intended behavior per WO Note 1 — no code change needed.

---

### 3.3 `04_Test/init.sql`

Execution order as specified:

1. **Extensions + schemas:**
   ```sql
   CREATE EXTENSION IF NOT EXISTS postgis;
   CREATE SCHEMA IF NOT EXISTS canopysense;
   CREATE SCHEMA IF NOT EXISTS testschema;
   ```

2. **`canopysense.blocks`** with seed data — 4 rows:
   - Blocks 1–3: `afdeling_id=1`, small valid EPSG:4326 polygons (distinct from block 18 region)
   - Block 18: `afdeling_id=2`, exact polygon from STR Test A-1:
     `POLYGON((108.0 -1.0, 108.1 -1.0, 108.1 -1.1, 108.0 -1.1, 108.0 -1.0))`
   - `INSERT ... ON CONFLICT DO NOTHING` guard for idempotency

3. **`canopysense.satellite_data`** — empty, DDL as specified in WO

4. **`canopysense.patcher_run_log`** — verbatim paste of `03_Build/patcher_run_log_ddl.sql` (already has `IF NOT EXISTS` guards)

5. **`canopysense.patcher_write_test`** — empty, DDL as specified in WO

6. **`testschema` mirrors:**
   ```sql
   CREATE TABLE testschema.satellite_data (LIKE canopysense.satellite_data INCLUDING ALL);
   CREATE TABLE testschema.patcher_run_log (LIKE canopysense.patcher_run_log INCLUDING ALL);
   ```

> **FLAG-2 (non-blocking, noting for ANT awareness):**
>
> `LIKE canopysense.patcher_run_log INCLUDING ALL` copies the `id` column default `nextval('canopysense.patcher_run_log_id_seq')`. Both tables will share the same PostgreSQL sequence — ids are globally unique but not independently sequential within each table. This is acceptable for Phase C: the test verifies row insertion and `status` values, not `id` ordering. If ANT requires independent sequences for `testschema.patcher_run_log`, the fix is one additional `ALTER TABLE testschema.patcher_run_log ALTER COLUMN id SET DEFAULT nextval(pg_get_serial_sequence('testschema.patcher_run_log','id'))` after creating the table.

---

### 3.4 `04_Test/requirements_local.txt`

Exactly three packages as specified:
```
psycopg2-binary>=2.9
requests>=2.28
python-dotenv>=1.0
```

No GEE, no geopandas, no other additions.

---

### 3.5 `04_Test/.env.test.example`

Exact content from WO section 2.6. This file is committed. The real `04_Test/.env.test` (with actual secrets) is excluded via `.gitignore`.

---

### 3.6 `04_Test/mock_cloud.py` (≤80 lines, stdlib only)

Uses `http.server.BaseHTTPRequestHandler` — no pip installs.

**Control flow in `do_POST`:**
1. Check `X-API-Key` header → if absent, reply `401` with `{"error": "unauthorized", "api_version": "1.1"}`
2. Build response: copy `_STATIC_RESPONSE` dict, inject dynamic `timestamp` from `datetime.now(timezone.utc).isoformat()`
3. Reply `200` with full response
4. Print `[mock_cloud] POST / → <status_code>` to stdout after each request
5. Override `log_message` to no-op — suppresses default BaseHTTPRequestHandler access log to stdout (avoids double logging)

**Static response:** Exact two-entry `writes` structure from WO section 2.7. `presence_check: null` for the second entry matches JSON `None` serialization.

**Estimated line count: ~48 lines** (well within ≤80 target).

Listener: `HTTPServer(("0.0.0.0", 8080), MockHandler).serve_forever()` with startup print:
`[mock_cloud] Listening on port 8080 — Phase D two-entry writes mock`

---

### 3.7 `.gitignore` update

Add `04_Test/.env.test` under the `# Environment` section, alongside `.env`. No other changes.

---

## 4. Line Budget

| File | Target | Estimated |
|------|--------|-----------|
| `mock_cloud.py` | ≤80 lines | ~48 lines |
| All other files | No limit specified | N/A |

---

## 5. Success Indicator Self-Check

| WO Indicator | How My Implementation Satisfies It |
|--------------|-----------------------------------|
| `docker-compose up -d` completes | Correct image tag, healthcheck with retries=5, `depends_on: condition: service_healthy` |
| All required tables exist | `init.sql` creates: `blocks`, `satellite_data`, `patcher_run_log`, `patcher_write_test` in `canopysense`; `satellite_data`, `patcher_run_log` in `testschema` = 6 tables total |
| `blocks` seeded with block_id 18 | Explicit `INSERT` with id=18 and exact WO polygon |
| Patcher → PostGIS connectivity | Internal Docker network resolves `postgis` hostname; `PGHOST=postgis` env var |
| `patcher_local.py --help` exits 0 | python:3.11-slim + psycopg2-binary + requests + python-dotenv covers all imports |
| mock 401 on missing key | `X-API-Key` header check before processing |
| mock 200 with `writes` length 2 | Static `_STATIC_RESPONSE` has exactly 2 entries in `writes` |
| `.env.test` not committed | `.gitignore` entry `04_Test/.env.test` added |

---

## 6. Open Items Requiring ANT Confirmation

| # | Item | Proposed Resolution |
|---|------|---------------------|
| FLAG-1 | Build context must be project root (`..`) to allow COPY of both `03_Build/` and `04_Test/requirements_local.txt` — contradicts WO's `context: ../03_Build` | Use `context: ..` in docker-compose.yml; update Dockerfile COPY paths accordingly |
| FLAG-2 | `testschema.patcher_run_log.id` shares sequence with `canopysense.patcher_run_log.id` via `LIKE INCLUDING ALL` | Non-blocking for Phase C — acceptable unless ANT requires independent sequences |

---

**CDC Status:** Ready to implement all 7 deliverables pending ANT approval of FLAG-1 (build context).

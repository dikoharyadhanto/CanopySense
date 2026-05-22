---
name: ANT-STR-003-v0.10
project: Canopy Sense
status: PENDING — Awaiting CDC implementation of ANT-WO-003-v0.10
version: 0.10
created_date: 2026-04-21
prerequisite: ANT-WO-003-v0.10 implementation complete
linked_wo: ANT-WO-003-v0.10
---

# ANT-STR-003-v0.10 (Test Plan — Generic Write Routing)

---

## 1. Acceptance Rules

- Patcher-Local must contain no hardcoded table names or column lists
- Patcher-Cloud response `writes` array fully controls what gets written and where
- Schema prefix must be configurable via `PGSCHEMA` env var with `canopysense` as default
- Adding a second write entry to the response must cause Patcher-Local to write to that table with zero code changes
- All error responses must include `api_version: "1.1"`
- Request format must be identical to v1.0 — no changes on the sending side

---

## 2. Pre-Conditions Before Execution

- [ ] Phase 0 simulation environment running — `postgis` and `patcher` containers healthy (see Phase 0)
- [ ] `patcher_local.py` v0.10 deployed — no `_TABLE` or `_COLS` constants present
- [ ] `patcher_cloud_function.py` v0.10 deployed to Cloud Function (`patcher_cloud`)
- [ ] Cloud Function returns `api_version: "1.1"` and `writes` array
- [ ] `04_Test/.env.test` populated with valid `CONTRACTOR_ID`, `PATCHER_API_KEY`, `CLOUD_FUNCTION_URL`

---

## 3. Testing Phases

---

### Phase 0: Simulation Environment Setup

**Goal:** Stand up the two-container local simulation before executing any test phase. Phases B, C, D run inside the `patcher` container against the `postgis` container. Phases A and F run as curl from the host directly against the real Cloud Function.

**Architecture:**
```
[Host Machine]                         [GCP]
Phase A / F curl  ───────────────────► Cloud Function (patcher_cloud)

Phase B / C / D
      │
      ▼
[Docker: patcher container]            [Docker: postgis container]
patcher_local.py  ───────────────────► canopysense.satellite_data
                   internal network    canopysense.patcher_run_log
                                       canopysense.blocks (seeded)
                                       canopysense.patcher_write_test  ← Phase D
                                       testschema.satellite_data       ← Phase C
                                       testschema.patcher_run_log      ← Phase C
```

**Step 0-1: Create environment file**
```bash
cp 04_Test/.env.test.example 04_Test/.env.test
# Edit 04_Test/.env.test — fill in CLOUD_FUNCTION_URL, PATCHER_API_KEY, CONTRACTOR_ID
```

**Step 0-2: Start containers**
```bash
cd 04_Test && docker-compose --env-file .env.test up -d
```

Pass criteria:
- Both `postgis` and `patcher` containers reach `healthy` / `running`
- No errors in `docker-compose logs`

**Step 0-3: Verify PostGIS tables and seed data**
```bash
docker-compose exec postgis psql -U patcher -d canopysense_test -c "\dt canopysense.*"
docker-compose exec postgis psql -U patcher -d canopysense_test \
  -c "SELECT id, afdeling_id FROM canopysense.blocks ORDER BY id"
```

Pass criteria:
- Tables listed: `blocks`, `satellite_data`, `patcher_run_log`, `patcher_write_test`
- `blocks` contains at least block_id 18

**Step 0-4: Verify patcher container connectivity**
```bash
docker-compose run --rm patcher python3 -c \
  "import psycopg2; conn=psycopg2.connect(host='postgis',port=5432,dbname='canopysense_test',user='patcher',password='patcher_test'); print('PostGIS OK')"
```

Pass criteria:
- Prints `PostGIS OK` with no connection error

---

### Phase A: API Contract v1.1 Verification

**Goal:** Confirm response schema matches v1.1 contract — `writes` array present, top-level `records` absent, `api_version: "1.1"` in all responses.

**Test A-1: Valid request — verify v1.1 response structure**
```bash
curl -s -X POST https://asia-southeast2-canopysense.cloudfunctions.net/patcher_cloud \
  -H "X-API-Key: my-test-key-123" \
  -H "Content-Type: application/json" \
  -d '{
    "api_version": "1.0",
    "blocks": {
      "type": "FeatureCollection",
      "features": [{
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": [[[108.0,-1.0],[108.1,-1.0],[108.1,-1.1],[108.0,-1.1],[108.0,-1.0]]]},
        "properties": {"block_id": 18, "code": "BLK-018", "name": "Test Block"}
      }]
    }
  }'
```

Pass criteria:
- HTTP 200
- `"api_version": "1.1"` in response
- `"writes"` array present with at least one entry
- `writes[0]` contains: `table`, `columns`, `conflict_columns`, `presence_check`, `records`
- `writes[0].table` equals `"satellite_data"` (no schema prefix)
- Top-level `"records"` field is **absent**
- `rows_returned` equals `len(writes[0].records)`

---

**Test A-2: Missing body — error still includes api_version 1.1**
```bash
curl -s -X POST https://asia-southeast2-canopysense.cloudfunctions.net/patcher_cloud \
  -H "X-API-Key: my-test-key-123" \
  -H "Content-Type: application/json"
```

Pass criteria:
- HTTP 400
- `"api_version": "1.1"` in error response

---

**Test A-3: Auth error — api_version 1.1**
```bash
curl -s -X POST https://asia-southeast2-canopysense.cloudfunctions.net/patcher_cloud \
  -H "Content-Type: application/json"
```

Pass criteria:
- HTTP 401
- `"api_version": "1.1"` in error response

---

**Test A-4: Verify `writes` entry structure is complete**

Inspect the `writes[0]` object from Test A-1 response:

Pass criteria:
- `writes[0].columns` is a non-empty list matching the known satellite_data columns
- `writes[0].conflict_columns` equals `["block_id", "acquisition_date", "sensor"]`
- `writes[0].presence_check.block_id_column` equals `"block_id"`
- `writes[0].presence_check.recency_column` equals `"acquisition_date"`
- `writes[0].presence_check.recency_days` equals `14`

---

### Phase B: Patcher-Local — Generic Write Execution

**Goal:** Verify Patcher-Local correctly uses `writes` array to insert records into the right table with the right columns.

**Test B-1: Full scheduled run writes to correct table**
```bash
cd 04_Test && docker-compose --env-file .env.test run --rm patcher python3 patcher_local.py
```

Verify data written:
```bash
docker-compose exec postgis psql -U patcher -d canopysense_test \
  -c "SELECT COUNT(*) FROM canopysense.satellite_data"
docker-compose exec postgis psql -U patcher -d canopysense_test \
  -c "SELECT run_id, status, rows_inserted FROM canopysense.patcher_run_log ORDER BY id DESC LIMIT 5"
```

Pass criteria:
1. Records inserted into `canopysense.satellite_data` (not any other table)
2. Log shows `FULL_SUCCESS` with `presence_check` passing
3. `patcher_run_log` row present with `status=FULL_SUCCESS`
4. No `_TABLE` or `_COLS` references in Patcher-Local source code

---

**Test B-2: Idempotency — re-run inserts 0 rows, still FULL_SUCCESS**

Run again immediately:

Pass criteria:
- `rows_inserted=0` for all batches
- `FULL_SUCCESS` via presence check (data already present)
- No duplicates in `satellite_data`

---

### Phase C: Dynamic Schema Prefix

**Goal:** Verify `PGSCHEMA` env var controls the schema prefix for all writes.

**Test C-1: Default schema works with no PGSCHEMA set**

Run without `PGSCHEMA` override (docker-compose default is `canopysense`):

Pass criteria:
- Writes to `canopysense.satellite_data` (default schema applied)
- No error about missing schema configuration

---

**Test C-2: Custom schema prefix**

**Setup:** `testschema.satellite_data` and `testschema.patcher_run_log` are already created by `init.sql` — no manual setup required.

Run with custom schema:
```bash
cd 04_Test && docker-compose --env-file .env.test run --rm \
  -e PGSCHEMA=testschema patcher python3 patcher_local.py --block-id 18
```

Verify correct schema routing:
```bash
docker-compose exec postgis psql -U patcher -d canopysense_test \
  -c "SELECT COUNT(*) FROM testschema.satellite_data"
docker-compose exec postgis psql -U patcher -d canopysense_test \
  -c "SELECT COUNT(*) FROM canopysense.satellite_data"
```

Pass criteria:
- `testschema.satellite_data` row count increases
- `canopysense.satellite_data` row count unchanged
- `patcher_run_log` row written to `testschema.patcher_run_log`
- No hardcoded schema references triggered

---

### Phase D: Forward Compatibility — Second Write Entry

**Goal:** Verify that adding a second entry to `writes` causes Patcher-Local to write to that table with zero code changes.

**Setup:** `canopysense.patcher_write_test` is already created by `init.sql`. `mock_cloud.py` returns a static two-entry `writes` response — no modification to any product code required.

**Step D-1: Start the mock on the host (Terminal 1)**
```bash
python3 04_Test/mock_cloud.py
# Output: [mock_cloud] Listening on port 8080 — Phase D two-entry writes mock
```

**Step D-2: Run patcher container pointing to mock (Terminal 2)**
```bash
cd 04_Test && docker-compose --env-file .env.test run --rm \
  -e CLOUD_FUNCTION_URL=http://host.docker.internal:8080 \
  patcher python3 patcher_local.py --block-id 18
```

Verify both tables were written:
```bash
docker-compose exec postgis psql -U patcher -d canopysense_test \
  -c "SELECT block_id, acquisition_date, sensor FROM canopysense.satellite_data WHERE block_id=18"
docker-compose exec postgis psql -U patcher -d canopysense_test \
  -c "SELECT * FROM canopysense.patcher_write_test WHERE block_id=18"
```

**Step D-3: Restore — stop mock (Ctrl+C Terminal 1)**

Pass criteria:
1. Records inserted into both `satellite_data` AND `patcher_write_test`
2. No changes made to `patcher_local.py` source code before this test
3. Log shows two write operations completed
4. `patcher_run_log` shows `FULL_SUCCESS`

---

### Phase E: Source Code Audit — No Hardcoded Table Names

**Goal:** Confirm `patcher_local.py` contains no hardcoded table names or column lists.

```bash
grep -n "satellite_data\|patcher_run_log\|block_id.*acquisition_date\|_TABLE\|_COLS" \
  03_Build/patcher_local.py
```

Pass criteria:
- Zero matches for `satellite_data` (table reference)
- Zero matches for `_TABLE` or `_COLS` constants
- `patcher_run_log` references are acceptable only in `_log_write()` and `_log_update()` (these are internal retry-memory operations, not output writes)

---

### Phase F: Backward Compat — Request Format Unchanged

**Goal:** Confirm the v1.0 request format still works against the v1.1 Cloud Function.

Use the same curl from Test A-1 with `"api_version": "1.0"` in the request body:

Pass criteria:
- Cloud Function accepts the request normally
- `api_version: "1.1"` in response (server version, not client version)
- No error about request api_version mismatch

---

## 4. Observations & Output

*(Fill during execution)*

### Simulation Environment
| Test | Result | Notes |
|------|--------|-------|
| 0-1 Containers start healthy | PENDING | |
| 0-2 Tables present and blocks seeded | PENDING | |
| 0-3 Patcher → PostGIS connectivity | PENDING | |

### API Contract v1.1
| Test | Result | Notes |
|------|--------|-------|
| A-1 Valid request — writes structure | PENDING | |
| A-2 Error includes api_version 1.1 | PENDING | |
| A-3 Auth error includes api_version 1.1 | PENDING | |
| A-4 writes entry fields complete | PENDING | |

### Generic Write Execution
| Test | Result | Notes |
|------|--------|-------|
| B-1 Full scheduled run | PENDING | |
| B-2 Idempotency | PENDING | |

### Dynamic Schema
| Test | Result | Notes |
|------|--------|-------|
| C-1 Default schema | PENDING | |
| C-2 Custom PGSCHEMA | PENDING | |

### Forward Compatibility
| Test | Result | Notes |
|------|--------|-------|
| D-1 Second write entry — no code change | PENDING | |

### Source Code Audit
| Test | Result | Notes |
|------|--------|-------|
| E-1 No hardcoded table names | PENDING | |

### Backward Compat
| Test | Result | Notes |
|------|--------|-------|
| F-1 v1.0 request accepted by v1.1 Cloud Function | PENDING | |

---

## 5. Success Criteria Summary

| Category | Criteria | Target | Result |
|----------|----------|--------|--------|
| **No hardcoded tables** | `_TABLE`, `_COLS` absent from Patcher-Local | Zero occurrences | PENDING |
| **writes routing** | Patcher-Local writes to table specified in `writes`, not hardcoded | 100% driven by response | PENDING |
| **Dynamic schema** | `PGSCHEMA` env var controls schema prefix | No code change needed | PENDING |
| **Forward compat** | Second `writes` entry processed without Patcher-Local changes | Zero code changes | PENDING |
| **api_version 1.1** | All responses (success + error) return api_version 1.1 | 100% | PENDING |
| **Request unchanged** | v1.0 request format still accepted | No breaking change on send side | PENDING |

---

**ANT (Technical Foreman) Sign-off**: PENDING

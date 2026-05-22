---
name: ANT-STR-003-v0.11
project: Canopy Sense
status: PENDING — Awaiting CDC implementation of ANT-WO-003-v0.11
version: 0.11
created_date: 2026-04-24
prerequisite: ANT-WO-003-v0.11 implementation complete + ANT-STR-003-v0.10 ALL PHASES PASSED
linked_wo: ANT-WO-003-v0.11
---

# ANT-STR-003-v0.11 (Test Plan — Map Preview HTML Storage)

---

## 1. Acceptance Rules

- `canopysense.map_previews` table must exist in Docker PostGIS
- Patcher-Cloud response `writes` array must contain exactly two entries: `satellite_data` and `map_previews`
- Patcher-Local source code must be byte-for-byte identical to its state at end of v0.10 — zero modifications
- A `null` `presence_check` on a write entry must be handled gracefully — warning logged, execution continues
- HTML stored in `map_previews` must be a valid non-empty Leaflet HTML document
- `generated_at` must be stored as a valid TIMESTAMPTZ in PostGIS
- Re-running the patcher for the same block within the same second must produce zero new rows (DO NOTHING)

---

## 2. Pre-Conditions Before Execution

- [ ] `ANT-STR-003-v0.10` — ALL phases passed
- [ ] `patcher_local.py` is at v0.10 state — **no modifications applied for v0.11**
- [ ] `patcher_cloud_function.py` v0.11 deployed to Cloud Function (`patcher_cloud`)
- [ ] `canopysense.map_previews` DDL applied to Docker PostGIS
- [ ] `canopysense.patcher_run_log_ddl.sql` updated with `map_previews` DDL
- [ ] `.env` on test machine has valid `CONTRACTOR_ID`, `PATCHER_API_KEY`, `CLOUD_FUNCTION_URL`
- [ ] `canopysense.blocks` table populated with test blocks (block_id 18 present)

---

## 3. Testing Phases

---

### Phase A: DDL Verification

**Goal:** Confirm `map_previews` table exists with correct schema before running the patcher.

```sql
-- Connect to Docker PostGIS
\d canopysense.map_previews
```

Pass criteria:
- Table exists in `canopysense` schema
- Columns: `block_id INTEGER`, `sensor VARCHAR(20)`, `generated_at TIMESTAMPTZ`, `html_content TEXT`
- Primary key: `(block_id, sensor, generated_at)`

---

**Test A-2: Verify DDL file updated**

```bash
grep -n "map_previews" 03_Build/patcher_run_log_ddl.sql
```

Pass criteria:
- `CREATE TABLE IF NOT EXISTS canopysense.map_previews` present in file

---

### Phase B: Cloud Function Response — Two Write Entries

**Goal:** Confirm Patcher-Cloud v0.11 returns `writes` array with two entries and that `map_previews` entry is correctly structured.

**Test B-1: Valid request — verify two write entries**
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
- `writes` array has exactly **two** entries
- `writes[0].table` equals `"satellite_data"`
- `writes[1].table` equals `"map_previews"`

---

**Test B-2: Verify `map_previews` write entry structure**

Inspect `writes[1]` from Test B-1 response:

Pass criteria:
- `writes[1].columns` equals `["block_id", "sensor", "generated_at", "html_content"]`
- `writes[1].conflict_columns` equals `["block_id", "sensor", "generated_at"]`
- `writes[1].presence_check` is `null`
- `writes[1].records` is a list with exactly one entry
- `writes[1].records[0].html_content` is a non-empty string starting with `<!DOCTYPE html>` or `<html`

---

**Test B-3: `rows_returned` includes map preview record**

Inspect top-level `rows_returned` from Test B-1 response:

Pass criteria:
- `rows_returned` equals `len(writes[0].records) + len(writes[1].records)`
- `len(writes[1].records)` equals 1 (one HTML preview per batch)

---

### Phase C: Patcher-Local Source Code Audit — Zero Changes

**Goal:** Confirm Patcher-Local was not modified during v0.11 implementation.

```bash
# Check modification timestamp — should be from v0.10 implementation date, not v0.11
git log --oneline 03_Build/patcher_local.py
```

Pass criteria:
- Most recent commit to `patcher_local.py` is from v0.10 implementation
- No v0.11-related commits touch `patcher_local.py`

```bash
# Confirm no map_previews or html_content references in patcher_local.py
grep -n "map_previews\|html_content\|generated_at" 03_Build/patcher_local.py
```

Pass criteria:
- Zero matches — Patcher-Local has no knowledge of `map_previews` table or HTML content

---

### Phase D: Full Run — Both Tables Written

**Goal:** Verify Patcher-Local writes to both `satellite_data` and `map_previews` in a single run without code changes.

**Test D-1: Full scheduled run writes to both tables**
```bash
set -a && source 04_Test/.env && set +a
python3 03_Build/patcher_local.py
```

Pass criteria:
1. Records inserted into `canopysense.satellite_data`
2. Record inserted into `canopysense.map_previews`
3. Log shows `FULL_SUCCESS`
4. Log shows two write operations completed (one per `writes` entry)
5. `null` presence_check on `map_previews` entry logged as warning — NOT an error, execution continues
6. `patcher_run_log` updated correctly

---

**Test D-2: Verify database content**

```sql
-- Verify map_previews has a record
SELECT block_id, sensor, generated_at, length(html_content) AS html_bytes
FROM canopysense.map_previews
ORDER BY generated_at DESC
LIMIT 5;
```

Pass criteria:
- At least one row present for `block_id = 18`
- `html_bytes` > 10000 (non-trivial HTML — full Leaflet document)
- `generated_at` is a valid timestamp within last 5 minutes

---

**Test D-3: HTML content is valid Leaflet document**

```sql
-- Extract and inspect start of HTML
SELECT substring(html_content, 1, 200)
FROM canopysense.map_previews
WHERE block_id = 18
ORDER BY generated_at DESC
LIMIT 1;
```

Pass criteria:
- Output begins with `<!DOCTYPE html>` or `<html`
- Contains `leaflet` reference (Leaflet.js CDN or inline)

---

### Phase E: Idempotency — Re-run Produces No Duplicate Rows

**Goal:** Running patcher again within the same minute does not create duplicate `map_previews` rows.

Note: The primary key is `(block_id, sensor, generated_at)`. A second run will have a different `generated_at` timestamp (seconds differ), so it will insert a new row — this is expected and correct behavior. The test is that the patcher does not error and `satellite_data` rows are still `DO NOTHING`.

Run patcher immediately after Test D-1:

Pass criteria:
- No error during `map_previews` write
- `satellite_data` rows: `rows_inserted=0` (idempotent — data already present)
- `map_previews` rows: one new row added (new `generated_at`) — expected, not a failure
- `FULL_SUCCESS` in log

---

### Phase F: Browser Render Verification

**Goal:** HTML retrieved from database opens in a browser and renders Leaflet basemap.

```sql
-- Export HTML to file for browser test
COPY (
  SELECT html_content
  FROM canopysense.map_previews
  WHERE block_id = 18
  ORDER BY generated_at DESC
  LIMIT 1
) TO '/tmp/map_preview_test.html';
```

Open `/tmp/map_preview_test.html` in browser.

Pass criteria:
- Leaflet basemap renders (OpenStreetMap tiles load)
- Layer control panel visible (NDVI, EVI, etc. toggles present)
- GEE satellite tile layers may appear grey/empty — **this is expected** (tile URLs expire ~48h after generation). This is NOT a test failure.
- No JavaScript console errors unrelated to tile loading

---

### Phase G: `PGSCHEMA` — Dynamic Schema Still Works

**Goal:** `map_previews` write also respects `PGSCHEMA` env var (inherited from v0.10 generic writer).

**Setup:**
```sql
CREATE SCHEMA IF NOT EXISTS testschema;
CREATE TABLE testschema.map_previews (LIKE canopysense.map_previews INCLUDING ALL);
CREATE TABLE testschema.satellite_data (LIKE canopysense.satellite_data INCLUDING ALL);
CREATE TABLE testschema.patcher_run_log (LIKE canopysense.patcher_run_log INCLUDING ALL);
```

Run with custom schema:
```bash
PGSCHEMA=testschema python3 03_Build/patcher_local.py --block-id 18
```

Pass criteria:
- `map_previews` record inserted into `testschema.map_previews`, not `canopysense.map_previews`
- `satellite_data` records inserted into `testschema.satellite_data`
- No hardcoded schema reference triggered

---

## 4. Observations & Output

*(Fill during execution)*

### DDL Verification
| Test | Result | Notes |
|------|--------|-------|
| A-1 map_previews table schema | PENDING | |
| A-2 DDL file updated | PENDING | |

### Cloud Function Response
| Test | Result | Notes |
|------|--------|-------|
| B-1 Two write entries in response | PENDING | |
| B-2 map_previews entry structure correct | PENDING | |
| B-3 rows_returned includes preview count | PENDING | |

### Source Code Audit
| Test | Result | Notes |
|------|--------|-------|
| C-1 Patcher-Local unchanged from v0.10 | PENDING | |
| C-2 No map_previews references in patcher_local | PENDING | |

### Full Run
| Test | Result | Notes |
|------|--------|-------|
| D-1 Both tables written in single run | PENDING | |
| D-2 map_previews row in DB with valid html_bytes | PENDING | |
| D-3 HTML is valid Leaflet document | PENDING | |

### Idempotency
| Test | Result | Notes |
|------|--------|-------|
| E-1 Re-run does not error, satellite_data DO NOTHING | PENDING | |

### Browser Render
| Test | Result | Notes |
|------|--------|-------|
| F-1 HTML renders Leaflet basemap from DB | PENDING | |

### Dynamic Schema
| Test | Result | Notes |
|------|--------|-------|
| G-1 PGSCHEMA redirects map_previews write | PENDING | |

---

## 5. Success Criteria Summary

| Category | Criteria | Target | Result |
|----------|----------|--------|--------|
| **DDL** | `map_previews` table in PostGIS with correct schema | Table present | PENDING |
| **Two write entries** | `writes` array has satellite_data + map_previews | Both present | PENDING |
| **Zero Patcher-Local changes** | `patcher_local.py` identical to v0.10 | Zero diff | PENDING |
| **null presence_check** | Handled as warning, not error | No crash | PENDING |
| **HTML in DB** | Non-empty valid Leaflet HTML stored | html_bytes > 10000 | PENDING |
| **Dynamic schema** | `PGSCHEMA` applies to map_previews write | testschema used | PENDING |
| **Browser render** | Leaflet basemap visible from DB-sourced HTML | Basemap loads | PENDING |

---

**ANT (Technical Foreman) Sign-off**: PENDING

---
name: ANT-WO-003-v0.9
project: Canopy Sense
phase: Tahap III (Architecture Upgrade): Robust Patcher-Local with Option B Block Delivery
status: PENDING — Awaiting ANT activation
version: 0.9
created_date: 2026-04-20
updated_date: 2026-04-21
prerequisite: ANT-WO-003-v0.7 COMPLETE — Level 2 hybrid simulation PASSED
supersedes: patcher_local.py and patcher_cloud_function.py from v0.7
---

# ANT-WO-003-v0.9 (Work Order)

> [!IMPORTANT]
> **Lead Developer (CDC):** This Work Order upgrades the Two-Patcher system from its current v0.7 state to a production-ready architecture. The central goal is to build a **Patcher-Local that is written once and never needs modification again.** All evolving logic lives in Patcher-Cloud, which the admin controls without contractor involvement.

---

## 1. Background and Motivation

The v0.7 implementation has two architectural gaps that must be resolved before production:

**Gap 1 — Block data source:**
The Cloud Function currently reads block polygons from a database it connects to directly (via `PGHOST`/`PGPORT` env vars). This requires either a bore tunnel (testing workaround) or exposing the contractor's database to the internet (Option C — rejected). The chosen production design is **Option B**: Patcher-Local reads blocks from the contractor's local PostGIS and sends them as GeoJSON in the request body. The Cloud Function no longer needs any outbound database connection.

**Gap 2 — Patcher-Local is too fragile:**
The current `patcher_local.py` is a single-shot script with minimal retry logic. It does not handle batch loops, does not isolate batch failures, and has no mechanism for the next scheduled run to retry only what failed. For a script that lives on the contractor's server and must never be updated, this is insufficient.

**Core design principle for this WO:**
> Patcher-Local is a stable client. It is deployed once and rarely if ever modified. All smart logic — processing decisions, engine updates, new features — lives in Patcher-Cloud where the admin can update it freely without contractor involvement or knowledge.

---

## 2. Technical Tasks (Scope)

### 2.1 Redesign Patcher-Local (Robust Stable Client)

**File:** `03_Build/patcher_local.py` (full rewrite of v0.7)

Patcher-Local must handle **two distinct trigger modes** from a single entry point:

**Mode 1 — Upload Trigger (single area, immediate)**
Fired when a new user uploads a shapefile through the contractor's application. Only that one new area is processed immediately. Fast, lightweight, single JSON sent to Cloud Function.

**Mode 2 — Scheduled Trigger (all areas, looping)**
Fired on a schedule (weekly, daily). Processes all blocks in the contractor's PostGIS, batched by estate or afdeling. Each batch is sent as a separate request to the Cloud Function. The loop continues regardless of individual batch failures.

**Trigger mode is determined by how `patcher_local.py` is called:**
```bash
# Scheduled run — all blocks
python3 patcher_local.py

# Upload trigger — single block by block_id
python3 patcher_local.py --block-id 42
```

---

**2.1.1 Block Reading**

Before calling the Cloud Function, Patcher-Local reads block geometries from the contractor's local PostGIS:

```sql
-- Scheduled run: all blocks
SELECT block_id, code, name, afdeling_id, ST_AsGeoJSON(geometry) AS geojson
FROM canopysense.blocks
ORDER BY afdeling_id, block_id;

-- Upload trigger: single block
SELECT block_id, code, name, afdeling_id, ST_AsGeoJSON(geometry) AS geojson
FROM canopysense.blocks
WHERE block_id = <id>;
```

Results are serialized as a GeoJSON FeatureCollection and included in the POST request body.

---

**2.1.2 Batch Strategy (Scheduled Mode)**

For scheduled runs, blocks are grouped into batches by `afdeling_id` — one Cloud Function call per afdeling. This limits payload size per request and isolates failures at the afdeling level.

- Each batch is sent as an independent HTTP request
- A failure in batch N does not stop batch N+1
- Each batch result is written to PostGIS immediately after that batch completes
- A batch fingerprint (SHA-256 hash of sorted `block_id` list) is computed per batch before sending
- After the full loop, a run summary is logged: batches succeeded, batches failed, total rows inserted

**Batch grouping fallback order:**
1. `afdeling_id` — default
2. `estate_id` — if no afdeling data exists
3. Single request for all blocks — if no estate data exists either

---

**2.1.3 Failure Tracking (patcher_run_log)**

After each batch, Patcher-Local writes a status record to a local tracking table in the contractor's PostGIS:

```sql
-- Table created once during setup (CDC provides DDL)
CREATE TABLE IF NOT EXISTS canopysense.patcher_run_log (
    id                  SERIAL PRIMARY KEY,
    run_id              UUID NOT NULL,
    triggered_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at          TIMESTAMPTZ,                        -- set when batch begins (for stale detection)
    trigger_mode        TEXT NOT NULL,                      -- 'scheduled' | 'upload'
    afdeling_id         INTEGER,                            -- NULL for upload trigger
    block_id            INTEGER,                            -- NULL for scheduled batches
    batch_fingerprint   TEXT,                               -- SHA-256 hash of sorted block_id list for this batch
    status              TEXT NOT NULL,                      -- 'IN_PROGRESS' | 'FULL_SUCCESS' | 'PARTIAL_SUCCESS' | 'FULL_FAILURE' | 'SKIPPED'
    rows_inserted       INTEGER DEFAULT 0,
    error_detail        TEXT,                               -- JSON: {"message": "...", "missing_block_ids": [...]}
    api_version         TEXT
);
```

**Status definitions:**
- `IN_PROGRESS` — batch has started but not yet completed; set at the start of each batch attempt
- `FULL_SUCCESS` — all blocks in the batch are present in `satellite_data` after the run
- `PARTIAL_SUCCESS` — some blocks succeeded (present in `satellite_data`), others are missing due to block-level errors (e.g. GEE cloud cover failure on specific blocks)
- `FULL_FAILURE` — the entire batch failed (network error, GEE timeout, HTTP 5xx, zero records returned)
- `SKIPPED` — batch was skipped (empty block list, or already succeeded in a previous run)

On the next scheduled run, Patcher-Local checks this table and retries only batches with `FULL_FAILURE` or `PARTIAL_SUCCESS` status — not all batches. Batches with `FULL_SUCCESS` are skipped.

---

**2.1.3a IN_PROGRESS Lifecycle**

Every batch marks itself `IN_PROGRESS` at start and updates to a final state when complete. This protects against:
- Two simultaneous `patcher_local.py` processes running at the same time
- Orphaned `IN_PROGRESS` rows from a crash that left no final state

**Rules:**

1. **Before starting each batch:** query `patcher_run_log` for any row with `trigger_mode='scheduled'`, `afdeling_id=<this_batch>`, and `status='IN_PROGRESS'`.

2. **If a non-stale `IN_PROGRESS` row is found** (i.e. `started_at > NOW() - INTERVAL '30 minutes'`): log `[WARN] Concurrent run detected for afdeling_id=X. Skipping.` and skip this batch.

3. **If a stale `IN_PROGRESS` row is found** (i.e. `started_at <= NOW() - INTERVAL '30 minutes'`): update that row to `status='FULL_FAILURE'`, `error_detail='{"message": "Stale IN_PROGRESS — assumed crashed"}'`. Then proceed with the batch as a fresh attempt.

4. **Stale threshold:** 30 minutes. Any `IN_PROGRESS` row older than this is considered orphaned from a crash.

---

**2.1.3b Batch Completeness Definition**

A batch is **complete** when all blocks that were sent are present in `satellite_data` with a current acquisition date — not based on the `rows_inserted` count from the response.

**Presence check (run after each batch):**
```sql
SELECT COUNT(DISTINCT block_id)
FROM canopysense.satellite_data
WHERE block_id IN (<block_id_list>)
  AND acquisition_date >= CURRENT_DATE - INTERVAL '14 days';
```

- If count equals the number of blocks sent → `FULL_SUCCESS`
- If count is less but greater than zero → `PARTIAL_SUCCESS` (log which block_ids are missing)
- If count is zero → `FULL_FAILURE`

This presence check runs after inserting the response records, and the result determines the final `status` written to `patcher_run_log`.

---

**2.1.3c Partial Success Semantics**

Two categories of batch errors, handled differently:

**Block-level errors** (reported in `response.errors[]` for specific block_ids):
- GEE cloud cover threshold exceeded for one block
- GEE image not available for one block's geometry
- Individual block geometry invalid
→ Outcome: `PARTIAL_SUCCESS`. `error_detail` stores `missing_block_ids` as a JSON array. On retry, only the missing blocks are sent (not the full batch).

**Batch-level errors** (the entire request failed):
- Network timeout
- HTTP 5xx from Cloud Function
- Malformed/unparseable response body
- Zero records returned despite non-empty blocks payload
→ Outcome: `FULL_FAILURE`. On retry, the full batch is re-sent.

---

**2.1.4 Retry Logic**

**Transient failures — retry with exponential backoff (per batch):**
- Network timeout
- `500 Internal Server Error`
- `504 Gateway Timeout`
- `429 Too Many Requests` (treated as transient — also triggers circuit breaker; see 2.1.4a)
- Malformed JSON in response body — retry once, then mark `FULL_FAILURE` on second malformed response

Retry sequence per batch: wait 30s → retry → wait 60s → retry → wait 120s → retry → mark as `FULL_FAILURE`, continue to next batch.

**Deterministic failures — fail immediately, no retry:**
- `401 Unauthorized` — stop entire run, log `[ERROR] 401 Unauthorized — API key missing. Stopping run.`
- `403 Forbidden` — stop entire run, log `[ERROR] 403 Forbidden — API key invalid. Stopping run.`
- Empty blocks result from DB query — skip batch, log as `SKIPPED`
- API version mismatch in response — log warning, continue (do not break)

**Response validation layer:**
Before classifying a response as success or failure, Patcher-Local validates:
1. HTTP status code is 200
2. Response body is valid JSON
3. `api_version` field is present
4. `records` field is a list
5. `rows_returned` is an integer

If any validation step fails, the response is treated as a transient failure and retried according to the backoff sequence.

---

**2.1.4a Circuit Breaker (429 Rate Limit)**

If three consecutive `429 Too Many Requests` responses are received across any batches in the same run:
- Pause the entire run for 5 minutes
- Log: `[WARN] Circuit breaker triggered — 3 consecutive 429s. Pausing run for 5 minutes.`
- After 5 minutes, resume from the next batch (not from the beginning)
- The 429 counter resets after any non-429 response

---

**2.1.4b Batch Fingerprint Rule**

Each batch has a `batch_fingerprint` — the SHA-256 hash of its sorted `block_id` list. This detects when the contractor's block data has changed between runs.

**Behavioral rule:**
- When retrying a `FULL_FAILURE` or `PARTIAL_SUCCESS` batch, compute the current fingerprint and compare to the stored fingerprint in `patcher_run_log`.
- If fingerprints match: retry as normal.
- If fingerprints differ (blocks added or removed): the old log entry is invalidated. Log: `[INFO] Batch fingerprint changed for afdeling_id=X. Treating as new batch.` Insert a new `patcher_run_log` row for this run rather than updating the old one.

---

**2.1.4c Dual-Mode State Isolation**

The scheduled retry loop must never pick up failures from upload trigger runs, and vice versa.

**Rule:** When querying `patcher_run_log` to find batches to retry, always filter by `trigger_mode`:
- Scheduled run: `WHERE trigger_mode = 'scheduled' AND status IN ('FULL_FAILURE', 'PARTIAL_SUCCESS')`
- Upload trigger: never reads from `patcher_run_log` for retry — it always runs fresh on the specified `block_id`

Upload trigger failures are not automatically retried. If a `--block-id` run fails, the contractor or admin must re-run it manually.

---

**2.1.5 API Version Check**

Every response from Patcher-Cloud includes an `api_version` field. Patcher-Local checks this on every call:

- If `api_version` matches expected version → proceed normally
- If `api_version` is newer → log a warning: `"[WARN] Patcher-Cloud api_version=2.0 detected. Consider updating patcher_local.py."` Continue processing — do not break.
- If `api_version` is absent → log a warning and continue. Never raise an error on version mismatch — the script must not break because of a cloud update.

This gives the admin visibility that an update may be beneficial without forcing the contractor to act immediately.

---

**2.1.6 Logging**

All output must be structured, readable, and useful to both contractor (terminal) and admin (forwarded logs):

```
[INFO]  Run started — mode: scheduled | run_id: a3f8-c2d1
[INFO]  Blocks loaded: 101 across 5 afdelings
[INFO]  Batch 1/5 (afdeling_id=1, 22 blocks, fingerprint=a1b2c3) — sending to Cloud Function
[INFO]  Batch 1/5 — FULL_SUCCESS | rows_inserted=22 | presence_check=22/22 | api_version=1.0
[INFO]  Batch 2/5 (afdeling_id=2, 19 blocks, fingerprint=d4e5f6) — sending to Cloud Function
[WARN]  Batch 2/5 — attempt 1 failed (timeout). Retrying in 30s...
[INFO]  Batch 2/5 — FULL_SUCCESS on retry | rows_inserted=19 | presence_check=19/19 | api_version=1.0
[WARN]  Batch 3/5 — PARTIAL_SUCCESS | presence_check=15/18 | missing_block_ids=[42,47,51]
[ERROR] Batch 4/5 — FULL_FAILURE after 3 attempts. Recorded for next run.
[INFO]  Batch 5/5 — FULL_SUCCESS | rows_inserted=21 | presence_check=21/21 | api_version=1.0
[INFO]  Run complete — 3/5 FULL_SUCCESS | 1 PARTIAL_SUCCESS | 1 FULL_FAILURE | 77 rows inserted
```

---

**2.1.7 `.env` Configuration (no new required vars)**

All existing `.env` variables remain. Two optional new vars:

```
BATCH_MODE=afdeling          # how to group batches: 'afdeling' | 'estate' | 'none'
PATCHER_API_VERSION=1.0      # expected api_version in Cloud Function response
```

Both have sensible defaults — Patcher-Local works with no `.env` changes from the contractor.

---

### 2.2 Update Patcher-Cloud (Accept Blocks from Request Body)

**File:** `03_Build/patcher_cloud_function.py` (targeted update)

**Changes required:**

1. **Parse blocks from request body** — after API key validation, read the GeoJSON FeatureCollection from `request.get_json()`. If body is missing or malformed → return `400 Bad Request: Missing or invalid blocks payload`.

2. **Pass blocks to engine** — convert GeoJSON to a GeoDataFrame and pass it to `engine_launcher.run_pipeline(blocks_gdf=...)` as a parameter instead of having the engine read from a DB.

3. **Remove DB environment dependency** — `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD` are no longer needed in Cloud Function environment variables. Remove them from the Cloud Function configuration.

4. **Include `api_version` in every response:**
```json
{
  "status": "success",
  "api_version": "1.0",
  "timestamp": "...",
  "contractor_id": "...",
  "rows_returned": 22,
  "errors": [],
  "records": [...]
}
```

5. **Return `400` for empty blocks payload** — if the GeoJSON FeatureCollection has zero features, return immediately without invoking GEE.

6. **`errors` field classification contract** — the `errors` array in the response must use the following structure to allow Patcher-Local to distinguish block-level from batch-level failures:
```json
{
  "errors": [
    {
      "block_id": 42,
      "type": "block_level",
      "reason": "GEE cloud cover threshold exceeded (87%)"
    }
  ]
}
```
- `type: "block_level"` — specific block failed; other blocks may have succeeded
- `type: "batch_level"` — the entire batch failed; no records should be trusted

An empty `errors` array means all blocks succeeded.

---

### 2.3 Update Engine Launcher (Accept Blocks as Parameter)

**File:** `03_Build/deploy/engine_launcher.py`

> [!NOTE]
> This is the one exception to the "no core changes" constraint from v0.7. The block-loading logic must move from inside the engine to the caller. The change is minimal and surgical — only `run_pipeline()` signature changes.

**Change:** `run_pipeline()` gains an optional `blocks_gdf` parameter:

```python
def run_pipeline(blocks_gdf: gpd.GeoDataFrame | None = None, seed_shapefile: str | None = None) -> None:
    ...
    if blocks_gdf is None:
        blocks_gdf = _load_blocks_from_db(conn)  # fallback for local runs
    ...
```

When `blocks_gdf` is provided (Cloud Function call), the DB block-loading step is skipped entirely. When it is `None` (direct local run of engine_launcher), the existing DB read path is used as fallback. **This preserves full backward compatibility — existing local engine runs are unaffected.**

---

### 2.4 Stable API Contract (Must Not Change Without a Version Bump)

The following interface is the contract between Patcher-Local and Patcher-Cloud. Both sides must honour it. Any change to this contract requires an `api_version` bump and a documented migration path.

**Request (Patcher-Local → Patcher-Cloud):**
```
POST /patcher_cloud
Headers:
  X-API-Key: <raw api key>
  Content-Type: application/json

Body:
{
  "api_version": "1.0",
  "blocks": {
    "type": "FeatureCollection",
    "features": [
      {
        "type": "Feature",
        "geometry": { ...GeoJSON polygon... },
        "properties": {
          "block_id": 18,
          "code": "BLK-018",
          "name": "Blok A"
        }
      }
    ]
  }
}
```

**Required request fields:** `blocks` (FeatureCollection), each feature must have `properties.block_id` (integer). Missing `block_id` in any feature → `400 Bad Request`.

**Response (Patcher-Cloud → Patcher-Local):**
```json
{
  "status": "success",
  "api_version": "1.0",
  "timestamp": "2026-04-20T10:30:05Z",
  "contractor_id": "CONTRACTOR_ACME_FARMS",
  "rows_returned": 22,
  "errors": [],
  "records": [
    {
      "block_id": "18",
      "acquisition_date": "2026-04-18",
      "sensor": "sentinel-2",
      "ndvi": "0.6124",
      "evi": "0.3891",
      "ndre": "0.4201",
      "savi": "0.5012",
      "gndvi": "0.5534",
      "cloud_cover": "3.20",
      "features": "{\"valid_pixel_ratio\": 0.968, \"low_quality\": false}"
    }
  ]
}
```

**Required response fields (validated by Patcher-Local before processing):** `api_version`, `records` (list), `rows_returned` (integer), `errors` (list). Missing any field → treat as malformed response (transient failure, retry once).

**Error responses always include `api_version`:**
```json
{ "api_version": "1.0", "error": "400 Bad Request: Missing or invalid blocks payload" }
{ "api_version": "1.0", "error": "401 Unauthorized: Missing X-API-Key header" }
{ "api_version": "1.0", "error": "403 Forbidden: Invalid API Key (contact administrator)" }
```

---

## 3. Success Indicators

### Patcher-Local Robustness
- [ ] Single trigger fires full scheduled loop without re-triggering needed
- [ ] Batch N failure does not stop batch N+1
- [ ] Transient failures retry with exponential backoff (30s → 60s → 120s)
- [ ] `401`/`403` failures stop the run immediately and log clearly
- [ ] Failed batches recorded in `patcher_run_log` with correct status (`FULL_FAILURE` or `PARTIAL_SUCCESS`)
- [ ] Next scheduled run retries only `FULL_FAILURE` and `PARTIAL_SUCCESS` batches
- [ ] `PARTIAL_SUCCESS` retry sends only missing block_ids, not full batch
- [ ] API version mismatch logs a warning but does not break the run
- [ ] Upload trigger mode (`--block-id`) processes only the specified block
- [ ] Empty blocks result in `SKIPPED` log, not an error
- [ ] IN_PROGRESS guard prevents concurrent runs from processing same batch
- [ ] Stale IN_PROGRESS (>30 min) is marked `FULL_FAILURE` and retried
- [ ] Circuit breaker pauses run for 5 minutes after 3 consecutive 429s
- [ ] Batch fingerprint change triggers new batch row, not update of old row
- [ ] Scheduled retry never picks up upload trigger failures (dual-mode isolation)
- [ ] Presence check (not insert count) determines final batch status

### Patcher-Cloud Stability
- [ ] Accepts GeoJSON blocks from request body
- [ ] Returns `400` for missing or malformed body
- [ ] Returns `400` for empty FeatureCollection (zero features)
- [ ] Returns `400` for any feature missing `block_id` in properties
- [ ] `api_version: "1.0"` present in every response including errors
- [ ] `errors` array uses block_level/batch_level type classification
- [ ] No outbound DB connections — PGHOST/PGPORT removed from Cloud Function env vars

### API Contract Integrity
- [ ] Request and response schema matches this WO exactly
- [ ] `api_version` field present in all responses
- [ ] Engine receives blocks as GeoDataFrame parameter — no DB read for blocks
- [ ] Direct local engine_launcher runs still work (backward compatibility)
- [ ] Patcher-Local validates all required response fields before processing

### Operational Goal
- [ ] `patcher_local.py` requires zero changes to operate across any future Patcher-Cloud update
- [ ] Admin can update Patcher-Cloud internally without notifying contractor

---

## 4. Implementation Constraints

| Constraint | Rule |
|-----------|------|
| Patcher-Local stability | Must function correctly with any future Patcher-Cloud that honours the v1.0 API contract |
| API version | Never remove or rename fields in v1.0 contract — only add new optional fields |
| engine_launcher | Change must be backward compatible — local runs unchanged |
| Patcher-Local `.env` | No new required variables — only optional ones with defaults |
| Patcher-Local line limit | Raised to 300 lines given increased responsibility. Still single-file. |
| Patcher-Cloud line limit | Raised to 250 lines given new block parsing logic |
| Error messages | All existing error messages from v0.7 preserved unchanged |
| Cloud Function env vars | Remove `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD` after deployment |
| patcher_run_log | Must be written before run ends — even if the run itself is crashing |
| Stale threshold | 30 minutes — hardcoded, not configurable via `.env` |

---

## 5. Deliverables Checklist

| Deliverable | Type | Owner | Status |
|------------|------|-------|--------|
| `03_Build/patcher_local.py` | Full rewrite | CDC | Pending |
| `03_Build/patcher_cloud_function.py` | Targeted update | CDC | Pending |
| `03_Build/deploy/engine_launcher.py` | Minimal update (`run_pipeline` signature) | CDC | Pending |
| `03_Build/deploy/main.py` | Sync with updated `patcher_cloud_function.py` | CDC | Pending |
| `canopysense.patcher_run_log` DDL | SQL script | CDC | Pending |
| `03_Build/CDC-IMPL-003-v0.9.md` | Implementation log | CDC | Pending |
| Updated `03_Build/GUIDANCE.md` | Reflect new `--block-id` trigger mode and new log states | CDC | Pending |

---

## 6. Notes for CDC

1. **Patcher-Local is the priority.** The Cloud Function update is simpler — the real complexity is in the batch loop, retry logic, and run log table. Invest time here.
2. **Never raise an exception on API version mismatch.** Log a warning, continue. The script must be indestructible against cloud updates.
3. **The `patcher_run_log` table is the retry memory.** Without it, the next scheduled run has no way to know what failed. It must be written before the run ends, even if the run itself is crashing.
4. **Batch status is determined by presence check, not insert count.** `rows_inserted=0` is normal on re-runs; it does not mean failure. Query `satellite_data` to confirm blocks are present.
5. **Partial retries send only missing blocks.** When retrying a `PARTIAL_SUCCESS` batch, read `missing_block_ids` from `error_detail` in `patcher_run_log` and send only those block geometries — not the full afdeling.
6. **Test backward compatibility of engine_launcher.py.** After changing `run_pipeline()` signature, run the engine locally with no `blocks_gdf` parameter and confirm it still reads from DB correctly.
7. **IN_PROGRESS must be written before any HTTP call.** The `started_at` timestamp must be set before sending the request, not after receiving the response.
8. **Circuit breaker state is in-memory only** — it resets when `patcher_local.py` exits. It is not persisted to `patcher_run_log`.

---

**ANT (Technical Foreman) Sign-off**: PENDING

**Next Steps after CDC Walkthrough approved:**
1. CDC implements all deliverables
2. CDC updates `03_Build/CDC-IMPL-003-v0.9.md`
3. ANT executes `ANT-STR-003-v0.9`

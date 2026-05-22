---
name: ANT-STR-003-v0.9
project: Canopy Sense
status: PENDING — Awaiting CDC implementation of ANT-WO-003-v0.9
version: 0.9
created_date: 2026-04-20
updated_date: 2026-04-21
prerequisite: ANT-WO-003-v0.9 implementation complete
linked_wo: ANT-WO-003-v0.9
---

# ANT-STR-003-v0.9 (Test Plan — Robust Patcher-Local with Option B Block Delivery)

---

## 1. Acceptance Rules

- Patcher-Local triggers once and manages the full loop internally — no external re-triggering needed
- A single batch failure must never stop the remaining batches from running
- Every response from Patcher-Cloud must include `api_version`
- Patcher-Local must not break when Patcher-Cloud is updated (as long as API contract is honoured)
- Failed batches must be recorded and automatically retried on the next scheduled run
- The Cloud Function must never attempt an outbound database connection for block data
- Batch status is determined by presence check — not by `rows_inserted` count
- `IN_PROGRESS` rows older than 30 minutes are treated as crashed and retried
- Scheduled retries never pick up failures from upload trigger runs

---

## 2. Pre-Conditions Before Execution

- [ ] `patcher_local.py` v0.9 deployed and confirmed to be the active script
- [ ] `patcher_cloud_function.py` v0.9 deployed to Cloud Function (`patcher_cloud`)
- [ ] `engine_launcher.py` updated with `blocks_gdf` parameter
- [ ] `canopysense.patcher_run_log` table exists in contractor's PostGIS (with all v0.9 columns including `started_at`, `batch_fingerprint`, `status` supporting all 5 states)
- [ ] `canopysense.blocks` table populated with test blocks (at minimum 2 afdelings)
- [ ] Cloud Function env vars `PGHOST`/`PGPORT`/`PGDATABASE`/`PGUSER`/`PGPASSWORD` removed
- [ ] `.env` on test machine has valid `CONTRACTOR_ID`, `PATCHER_API_KEY`, `CLOUD_FUNCTION_URL`

---

## 3. Testing Phases

---

### Phase A: API Contract Verification

**Goal:** Confirm the request and response schema match the v1.0 contract defined in ANT-WO-003-v0.9 exactly.

**Test A-1: Valid request with blocks**

Send a manually crafted request with a small GeoJSON payload:
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
        "geometry": {"type": "Polygon", "coordinates": [[[...test coords...]]]},
        "properties": {"block_id": 18, "code": "BLK-018", "name": "Test Block"}
      }]
    }
  }'
```

Pass criteria:
- Response HTTP status: `200`
- Response body contains: `"status": "success"`, `"api_version": "1.0"`, `"records": [...]`, `"errors": []`
- `rows_returned` matches number of records in `records` array

---

**Test A-2: Missing request body**
```bash
curl -s -X POST https://asia-southeast2-canopysense.cloudfunctions.net/patcher_cloud \
  -H "X-API-Key: my-test-key-123" \
  -H "Content-Type: application/json"
```

Pass criteria:
- HTTP status: `400`
- Response: `{"api_version": "1.0", "error": "400 Bad Request: Missing or invalid blocks payload"}`

---

**Test A-3: Empty FeatureCollection**
```bash
curl -s -X POST https://asia-southeast2-canopysense.cloudfunctions.net/patcher_cloud \
  -H "X-API-Key: my-test-key-123" \
  -H "Content-Type: application/json" \
  -d '{"api_version": "1.0", "blocks": {"type": "FeatureCollection", "features": []}}'
```

Pass criteria:
- HTTP status: `400`
- Response contains `api_version` field and meaningful error message

---

**Test A-4: Auth errors still include `api_version`**

Send request with no API key:
```bash
curl -s -X POST https://asia-southeast2-canopysense.cloudfunctions.net/patcher_cloud \
  -H "Content-Type: application/json"
```

Pass criteria:
- HTTP status: `401`
- Response body contains `"api_version": "1.0"` even on auth failure

---

**Test A-5: Feature missing `block_id` in properties**
```bash
curl -s -X POST https://asia-southeast2-canopysense.cloudfunctions.net/patcher_cloud \
  -H "X-API-Key: my-test-key-123" \
  -H "Content-Type: application/json" \
  -d '{"api_version": "1.0", "blocks": {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[...]]]}, "properties": {"code": "BLK-018"}}]}}'
```

Pass criteria:
- HTTP status: `400`
- Response contains `api_version` and meaningful error about missing `block_id`

---

**Test A-6: errors field structure on partial success**

Use a test setup where one block has a geometry that will trigger a GEE cloud cover failure.

Pass criteria:
- HTTP status: `200`
- `errors` array contains at least one entry with `"type": "block_level"`, `"block_id"`, and `"reason"` fields
- `records` array contains entries for the blocks that succeeded
- `rows_returned` equals length of `records` array, not total blocks sent

---

### Phase B: Patcher-Local — Scheduled Run (Full Loop)

**Goal:** Verify that one trigger fires the full loop, batches are independent, and results are correctly written.

**Setup:** Ensure `canopysense.blocks` has blocks in at least 2 different afdelings.

**Test B-1: Full scheduled run**
```bash
set -a && source 04_Test/.env && set +a
python3 03_Build/patcher_local.py
```

Pass criteria:
1. Log shows: `"Blocks loaded: N across M afdelings"`
2. Each afdeling logged as a separate batch with fingerprint: `"Batch X/M (afdeling_id=Y, Z blocks, fingerprint=...)"`
3. Each successful batch shows: `"FULL_SUCCESS | presence_check=Z/Z | api_version=1.0"`
4. Final summary line: `"Run complete — M/M FULL_SUCCESS | 0 PARTIAL_SUCCESS | 0 FULL_FAILURE | N rows inserted"`
5. `canopysense.patcher_run_log` has one row per batch with `status='FULL_SUCCESS'`
6. `canopysense.satellite_data` has new rows matching the run

**Test B-2: Re-run immediately (idempotency)**

Run `patcher_local.py` again without waiting:

Pass criteria:
- Presence check confirms all blocks already present — `FULL_SUCCESS` with `rows_inserted=0`
- No errors, no duplicates in `canopysense.satellite_data`
- `patcher_run_log` shows new run entries with `rows_inserted=0` and `status='FULL_SUCCESS'`

---

### Phase C: Patcher-Local — Upload Trigger (Single Block)

**Goal:** Verify the `--block-id` mode processes only the specified block.

**Test C-1: Single block upload trigger**
```bash
python3 03_Build/patcher_local.py --block-id 18
```

Pass criteria:
1. Log shows: `"Mode: upload | block_id=18"`
2. Only one request sent to Cloud Function (one block in GeoJSON)
3. `patcher_run_log` has one row: `trigger_mode='upload'`, `block_id=18`
4. `satellite_data` has a new row for `block_id=18`

**Test C-2: Upload trigger with invalid block_id**
```bash
python3 03_Build/patcher_local.py --block-id 9999
```

Pass criteria:
- Log shows: `"[SKIPPED] block_id=9999 not found in canopysense.blocks"`
- `patcher_run_log` shows `status='SKIPPED'`
- No request sent to Cloud Function
- No error raised — clean exit

---

### Phase D: Batch Failure Isolation

**Goal:** Verify that a batch failure in the middle of a scheduled run does not stop subsequent batches.

**Setup:** Use a test environment with 3 afdelings. Temporarily break one batch by injecting an invalid geometry for all blocks in afdeling 2 to force a GEE failure.

**Test D-1: Middle batch fails, loop continues**

Run scheduled trigger. Observe:

Pass criteria:
1. Batch 1 succeeds — `status='FULL_SUCCESS'` in `patcher_run_log`
2. Batch 2 fails after 3 retry attempts — `status='FULL_FAILURE'` with `error_detail` populated
3. Batch 3 succeeds — `status='FULL_SUCCESS'` in `patcher_run_log`
4. Final log: `"Run complete — 2/3 FULL_SUCCESS | 0 PARTIAL_SUCCESS | 1 FULL_FAILURE"`
5. Patcher-Local exits with code `0` — it does not crash

---

### Phase E: Retry of Previously Failed Batches

**Goal:** Verify that the next scheduled run automatically retries only the batches that previously failed.

**Pre-condition:** Phase D has been run. `patcher_run_log` has one `status='FULL_FAILURE'` row for afdeling 2.

**Test E-1: Fix the failed batch and re-run**

Restore the correct geometry for afdeling 2 blocks. Then run:
```bash
python3 03_Build/patcher_local.py
```

Pass criteria:
1. Log shows: `"Retrying 1 previously failed batch(es) first"`
2. Afdeling 2 is retried — succeeds — `patcher_run_log` updated to `status='FULL_SUCCESS'`
3. Afdelings 1 and 3 are NOT re-run (already succeeded in previous run)
4. `satellite_data` now has data for afdeling 2

---

### Phase F: Transient Failure Retry (Backoff Verification)

**Goal:** Verify exponential backoff works correctly for network/timeout errors.

**Method:** Temporarily set `CLOUD_FUNCTION_URL` in `.env` to an unreachable URL to simulate timeout.

```bash
CLOUD_FUNCTION_URL=https://unreachable.example.com \
python3 03_Build/patcher_local.py --block-id 18
```

Pass criteria:
1. Attempt 1 fails with timeout
2. Log: `"[WARN] attempt 1 failed (timeout). Retrying in 30s..."`
3. Attempt 2 fails — `"[WARN] attempt 2 failed (timeout). Retrying in 60s..."`
4. Attempt 3 fails — `"[ERROR] all retries exhausted. Batch marked FULL_FAILURE."`
5. Total elapsed time: ~3.5 minutes (30s + 60s + 120s wait)
6. `patcher_run_log` shows `status='FULL_FAILURE'`, `error_detail` contains the timeout message
7. Patcher-Local exits cleanly — does not crash

---

### Phase G: Deterministic Failure — Stop Immediately

**Goal:** Verify that `401`/`403` errors stop the entire run without retrying.

**Test G-1: Invalid API key**

Set `PATCHER_API_KEY=invalid-key-xyz` in `.env`. Run scheduled trigger.

Pass criteria:
1. First batch attempt returns `403`
2. Log: `"[ERROR] 403 Forbidden — API key rejected. Stopping run."`
3. No further batches attempted
4. Patcher-Local exits — does not retry
5. `patcher_run_log` has one row: `status='FULL_FAILURE'`, `error_detail='403 Forbidden'`

**Test G-2: Missing API key**

Remove `PATCHER_API_KEY` from `.env`. Run scheduled trigger.

Pass criteria:
- Patcher-Local exits before making any HTTP request
- Log: `"[ERROR] Missing required environment variable: PATCHER_API_KEY"`
- No `patcher_run_log` entry (no run was started)

---

### Phase H: API Version Mismatch Tolerance

**Goal:** Verify Patcher-Local does not break when the Cloud Function returns a newer `api_version`.

**Method:** Manually craft a mock response with `"api_version": "2.0"` in a local test (or temporarily hardcode in Cloud Function for testing purposes). Confirm Patcher-Local handles it gracefully.

Pass criteria:
1. Log: `"[WARN] Patcher-Cloud api_version=2.0 detected. Consider updating patcher_local.py."`
2. Run continues normally — records are still parsed and inserted
3. `patcher_run_log` shows `api_version='2.0'` recorded
4. No exception raised

---

### Phase I: Engine Launcher Backward Compatibility

**Goal:** Verify that the updated `engine_launcher.py` still works for direct local runs (no `blocks_gdf` parameter).

```bash
cd /path/to/project
python3 03_Build/deploy/engine_launcher.py
```

Pass criteria:
1. Engine reads blocks from local PostGIS (original DB path — no error)
2. Pipeline runs end-to-end as in v0.7
3. CSV output written to `04_Test/result_output/`
4. No import errors or breaking changes

---

### Phase J: Cloud Function Has No DB Connection

**Goal:** Verify the Cloud Function no longer attempts to connect to any external database.

**Method:** Check Cloud Function environment variables after deployment.

```bash
~/google-cloud-sdk/bin/gcloud functions describe patcher_cloud \
  --region=asia-southeast2 --project=canopysense \
  --format="value(serviceConfig.environmentVariables)"
```

Pass criteria:
- `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD` are absent from the output
- Cloud Function runs successfully on a valid request without these variables

---

### Phase K: IN_PROGRESS Lifecycle

**Goal:** Verify the IN_PROGRESS guard prevents concurrent runs and recovers stale entries correctly.

**Test K-1: Concurrent run guard**

**Method:** Manually insert a fresh `IN_PROGRESS` row into `patcher_run_log` for afdeling 1 (set `started_at = NOW()`). Then run scheduled trigger.

```sql
INSERT INTO canopysense.patcher_run_log (run_id, started_at, trigger_mode, afdeling_id, status)
VALUES (gen_random_uuid(), NOW(), 'scheduled', 1, 'IN_PROGRESS');
```

```bash
python3 03_Build/patcher_local.py
```

Pass criteria:
1. Afdeling 1 batch is skipped — log: `"[WARN] Concurrent run detected for afdeling_id=1. Skipping."`
2. All other afdelings are processed normally
3. No exception raised

**Test K-2: Stale IN_PROGRESS recovery**

**Method:** Manually insert a stale `IN_PROGRESS` row (set `started_at` to 35 minutes ago).

```sql
INSERT INTO canopysense.patcher_run_log (run_id, started_at, trigger_mode, afdeling_id, status)
VALUES (gen_random_uuid(), NOW() - INTERVAL '35 minutes', 'scheduled', 1, 'IN_PROGRESS');
```

```bash
python3 03_Build/patcher_local.py
```

Pass criteria:
1. The stale row is updated: `status='FULL_FAILURE'`, `error_detail='{"message": "Stale IN_PROGRESS — assumed crashed"}'`
2. Afdeling 1 is processed as a fresh batch
3. Log shows stale takeover: `"[INFO] Stale IN_PROGRESS found for afdeling_id=1 (35 min). Marking FULL_FAILURE and retrying."`

---

### Phase L: Batch Completeness and PARTIAL_SUCCESS

**Goal:** Verify presence check determines batch status and PARTIAL_SUCCESS triggers partial retry.

**Test L-1: PARTIAL_SUCCESS detection**

**Method:** Use a test setup where one block in afdeling 1 has a geometry that causes a GEE block-level error (cloud cover too high). The remaining blocks succeed.

Run scheduled trigger. Observe:

Pass criteria:
1. Cloud Function response contains `errors` array with `"type": "block_level"` entries for the failed block(s)
2. `patcher_run_log` shows `status='PARTIAL_SUCCESS'` for afdeling 1
3. `error_detail` contains: `{"missing_block_ids": [<failed_block_ids>]}`
4. `satellite_data` has records for the succeeded blocks, not the failed ones
5. Log: `"[WARN] Batch 1/M — PARTIAL_SUCCESS | presence_check=X/Y | missing_block_ids=[...]"`

**Test L-2: PARTIAL_SUCCESS retry sends only missing blocks**

**Pre-condition:** Test L-1 has been run. Fix the geometry of the failed block.

Run scheduled trigger again:
```bash
python3 03_Build/patcher_local.py
```

Pass criteria:
1. Log shows retry is for afdeling 1 specifically
2. Request sent to Cloud Function contains only the previously missing block_ids (not all blocks in afdeling 1)
3. After retry: `patcher_run_log` updated to `status='FULL_SUCCESS'`
4. `satellite_data` now has records for all blocks in afdeling 1

---

### Phase M: Circuit Breaker (429 Rate Limit)

**Goal:** Verify that 3 consecutive 429 responses trigger a 5-minute pause.

**Method:** Use a mock server or temporarily configure the Cloud Function to return `429` for the first 3 requests. Use a local `functions-framework` server that returns 429 for testing.

```bash
CLOUD_FUNCTION_URL=http://localhost:8080 \
python3 03_Build/patcher_local.py
```

Pass criteria:
1. Batch 1 returns 429 (attempt 1)
2. Batch 1 returns 429 (attempt 2, after backoff)
3. After 3 consecutive 429s across any batches: log `"[WARN] Circuit breaker triggered — 3 consecutive 429s. Pausing run for 5 minutes."`
4. Run pauses for ~5 minutes (300 seconds)
5. After pause, run resumes from the next batch — does not restart from batch 1
6. 429 counter resets after any non-429 response

---

### Phase N: Batch Fingerprint Change Behavior

**Goal:** Verify that a changed fingerprint creates a new log entry and does not update the old one.

**Pre-condition:** Run scheduled trigger once to populate `patcher_run_log` with `FULL_FAILURE` for afdeling 1. Note the `batch_fingerprint` value.

**Method:** Add a new block to afdeling 1 in `canopysense.blocks`. Then run scheduled trigger.

Pass criteria:
1. Patcher-Local computes a new fingerprint for afdeling 1 (different from stored one)
2. Log: `"[INFO] Batch fingerprint changed for afdeling_id=1. Treating as new batch."`
3. A **new** `patcher_run_log` row is inserted (old row is not updated)
4. The old `FULL_FAILURE` row remains unchanged in the log
5. The new row reflects the updated block set

---

### Phase O: Dual-Mode State Isolation

**Goal:** Verify that upload trigger failures are never picked up by the scheduled retry loop.

**Test O-1: Upload trigger failure does not enter scheduled retry**

**Method:** Run an upload trigger for a non-existent URL so it fails:
```bash
CLOUD_FUNCTION_URL=https://unreachable.example.com \
python3 03_Build/patcher_local.py --block-id 18
```

This creates a `patcher_run_log` row with `trigger_mode='upload'`, `status='FULL_FAILURE'`.

Now run scheduled trigger:
```bash
python3 03_Build/patcher_local.py
```

Pass criteria:
1. Scheduled run does NOT retry the upload trigger failure for block_id=18
2. Log does not mention block_id=18 in retry context
3. Scheduled run processes its own afdelings normally
4. `patcher_run_log` still shows the upload failure row unchanged

---

### Phase P: Response Validation Layer

**Goal:** Verify Patcher-Local handles malformed responses gracefully without crashing.

**Test P-1: Malformed JSON response**

**Method:** Configure a local mock server to return invalid JSON (e.g. `"not json at all"`).

```bash
CLOUD_FUNCTION_URL=http://localhost:8080 \
python3 03_Build/patcher_local.py --block-id 18
```

Pass criteria:
1. Patcher-Local does not crash on JSON parse error
2. Log: `"[WARN] Malformed JSON in response. Retrying once..."`
3. If second attempt also returns malformed JSON: `"[ERROR] Malformed response on retry. Batch marked FULL_FAILURE."`
4. `patcher_run_log` shows `status='FULL_FAILURE'`, `error_detail` contains malformed response info
5. Clean exit — no exception propagated

**Test P-2: Response missing required field**

**Method:** Configure mock server to return `{"api_version": "1.0", "records": []}` (missing `rows_returned` and `errors`).

Pass criteria:
1. Patcher-Local logs: `"[WARN] Response missing required field: rows_returned. Treating as transient failure."`
2. Retry sequence applies (backoff)
3. After all retries exhausted: `status='FULL_FAILURE'`

---

## 4. Observations & Output

*(Fill during execution)*

### API Contract
| Test | Result | Notes |
|------|--------|-------|
| A-1 Valid request | PASS | HTTP 200, api_version=1.0, records=[1 row], errors=[], rows_returned=1 |
| A-2 Missing body | PASS | HTTP 400, api_version=1.0, correct error message |
| A-3 Empty FeatureCollection | PASS | HTTP 400, api_version=1.0 |
| A-4 Auth errors include api_version | PASS | HTTP 401, api_version=1.0 |
| A-5 Feature missing block_id | PASS | HTTP 400, "Missing block_id in feature properties", api_version=1.0 |
| A-6 errors field block_level structure | DEFERRED | Requires test geometry guaranteed to fail quality gate; deferred to Phase B/L execution with contractor PostGIS |

### Scheduled Run
| Test | Result | Notes |
|------|--------|-------|
| B-1 Full loop | PENDING | |
| B-2 Re-run idempotency | PENDING | |

### Upload Trigger
| Test | Result | Notes |
|------|--------|-------|
| C-1 Single block | PENDING | |
| C-2 Invalid block_id | PENDING | |

### Batch Failure Isolation
| Test | Result | Notes |
|------|--------|-------|
| D-1 Middle batch fails, loop continues | PENDING | |

### Retry of Failed Batches
| Test | Result | Notes |
|------|--------|-------|
| E-1 Next run retries only FULL_FAILURE batches | PENDING | |

### Transient Retry Backoff
| Test | Result | Notes |
|------|--------|-------|
| F-1 Timeout retry sequence | PENDING | Actual elapsed time: |

### Deterministic Failure
| Test | Result | Notes |
|------|--------|-------|
| G-1 Invalid key stops run | PENDING | |
| G-2 Missing key exits before HTTP | PENDING | |

### Version Tolerance
| Test | Result | Notes |
|------|--------|-------|
| H-1 Newer api_version warning | PENDING | |

### Backward Compatibility
| Test | Result | Notes |
|------|--------|-------|
| I-1 engine_launcher direct run | PASS | Full pipeline ran: GEE → CSV (5 rows) → HTML preview → ingestion (0 inserted, 5 conflict — correct) |

### Cloud Function No DB
| Test | Result | Notes |
|------|--------|-------|
| J-1 PGHOST absent from env vars | PASS | gcloud describe confirms only GCP_PROJECT_ID, LOG_LEVEL, FUNCTION_TIMEOUT_SECONDS, LOG_EXECUTION_ID present |

### IN_PROGRESS Lifecycle
| Test | Result | Notes |
|------|--------|-------|
| K-1 Concurrent run guard | PENDING | |
| K-2 Stale IN_PROGRESS recovery | PENDING | |

### Batch Completeness & PARTIAL_SUCCESS
| Test | Result | Notes |
|------|--------|-------|
| L-1 PARTIAL_SUCCESS detection | PENDING | |
| L-2 Partial retry sends only missing blocks | PENDING | |

### Circuit Breaker
| Test | Result | Notes |
|------|--------|-------|
| M-1 3 consecutive 429s trigger 5-min pause | PENDING | |

### Fingerprint Change
| Test | Result | Notes |
|------|--------|-------|
| N-1 Fingerprint change creates new log row | PENDING | |

### Dual-Mode Isolation
| Test | Result | Notes |
|------|--------|-------|
| O-1 Upload failure not in scheduled retry | PENDING | |

### Response Validation
| Test | Result | Notes |
|------|--------|-------|
| P-1 Malformed JSON handled gracefully | PENDING | |
| P-2 Missing required field triggers retry | PENDING | |

---

## 5. Success Criteria Summary

| Category | Criteria | Target | Result |
|----------|----------|--------|--------|
| **Loop autonomy** | One trigger manages full scheduled loop | No re-triggering needed | PENDING |
| **Batch isolation** | Batch N failure does not stop N+1 | 100% isolation | PENDING |
| **Retry intelligence** | Next run retries only FULL_FAILURE + PARTIAL_SUCCESS | No redundant re-runs | PENDING |
| **Partial retry** | PARTIAL_SUCCESS retry sends only missing block_ids | Targeted retry | PENDING |
| **Backoff** | Transient failures retry with 30s→60s→120s | Correct sequence | PENDING |
| **Hard stop** | 401/403 stops run immediately | Zero retries on auth fail | PENDING |
| **Version tolerance** | api_version mismatch → warning only | No crash | PENDING |
| **Contract stability** | api_version in every response | 100% | PENDING |
| **No DB in cloud** | Cloud Function has no PGHOST/PGPORT | Zero DB connections | PENDING |
| **Backward compat** | engine_launcher local run unchanged | Passes unchanged | PENDING |
| **Presence check** | Batch status from satellite_data query, not insert count | Accurate status | PENDING |
| **IN_PROGRESS guard** | Concurrent run skipped, stale run taken over | No double-processing | PENDING |
| **Circuit breaker** | 3× 429 → 5-min pause, then resume | Correct trigger | PENDING |
| **Fingerprint rule** | Block list change → new log row, not update | Correct tracking | PENDING |
| **Dual-mode isolation** | Upload failures never enter scheduled retry | 100% isolation | PENDING |
| **Response validation** | Malformed/missing fields → retry, not crash | Clean failure | PENDING |

---

**ANT (Technical Foreman) Sign-off**: PENDING

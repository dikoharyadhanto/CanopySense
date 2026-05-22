---
name: CDC-IMPL-003-v0.9
project: Canopy Sense
phase: Tahap III (Architecture Upgrade): Robust Patcher-Local with Option B Block Delivery
status: COMPLETE — READY FOR ANT-STR-003-v0.9 TEST EXECUTION
version: 0.9
created_date: 2026-04-21
---

# CDC-IMPL-003-v0.9 (Implementation Log)

---

## 1. Deliverables Summary

| Deliverable | File | Lines | Status |
|-------------|------|-------|--------|
| Patcher-Local script | `03_Build/patcher_local.py` | 300 | ✅ Complete |
| Patcher-Cloud function | `03_Build/patcher_cloud_function.py` | 253 | ✅ Complete |
| Cloud Function deploy copy | `03_Build/deploy/main.py` | 253 | ✅ Complete (synced) |
| Engine launcher | `03_Build/deploy/engine_launcher.py` | 715 | ✅ Complete (minimal update) |
| Run log DDL | `03_Build/patcher_run_log_ddl.sql` | 31 | ✅ Complete |
| Env template | `03_Build/.env.example` | 47 | ✅ Complete |
| Operations guide | `03_Build/GUIDANCE.md` | ~900 | ✅ Complete (v0.9 update) |
| Walkthrough | `03_Build/CDC-WALK-003-v0.9.md` | — | ✅ ANT Approved |

All files reside within `03_Build/` or `03_Build/deploy/` per Isolation Constraint.
Zero modifications to `03_Build/deploy/core_engine/` or `03_Build/deploy/ingestion/`.

---

## 2. Implementation Decisions

### 2.1 patcher_local.py — Flag Resolutions

**FLAG-1 (Line limit — APPROVED by ANT):**
250-line guidance, 260 hard ceiling. Delivered at **253 lines** for `patcher_cloud_function.py`. Patcher-Local delivered at exactly **300 lines** — at the WO target. Both within approved limits.

**FLAG-2 (Conditional DB connection — APPROVED by ANT):**
`engine_launcher.run_pipeline()` now opens `_get_db_connection()` only when needed:
```python
conn = None
if blocks_gdf is None or seed_shapefile is not None:
    conn = _get_db_connection()
```
Cloud Function path (blocks_gdf provided, no seed) skips DB entirely — no outbound DB connection. Local direct runs are fully backward compatible.

**FLAG-3 (Generic block-level error reason — APPROVED by ANT):**
Block-level errors use the generic reason: `"Block did not pass quality gate (insufficient valid pixels or no valid imagery)"`. Per-block cloud cover percentages are a v1.0+ concern requiring engine changes.

---

### 2.2 patcher_local.py — Key Design Decisions

**Batch loop with retry memory:**
`patcher_run_log` is the retry memory. The scheduled loop queries for `FULL_FAILURE` + `PARTIAL_SUCCESS` rows filtered by `trigger_mode='scheduled'` (dual-mode isolation). Failed batches are placed at the head of the ordered batch list so they are retried first.

**IN_PROGRESS lifecycle — write-before-HTTP:**
`started_at` is stamped by a direct `UPDATE ... SET status='IN_PROGRESS', started_at=NOW()` immediately before the HTTP call — not after. Any `IN_PROGRESS` row older than 30 minutes is treated as orphaned from a crash (`STALE`), updated to `FULL_FAILURE`, and the batch proceeds as a fresh attempt.

**Presence check determines status:**
After each batch, `COUNT(DISTINCT block_id) WHERE block_id=ANY(...) AND acquisition_date >= CURRENT_DATE - INTERVAL '14 days'` is the authoritative status signal — not `rows_inserted`. This correctly handles re-runs where `rows_inserted=0` but blocks are already present (`FULL_SUCCESS`).

**PARTIAL_SUCCESS partial retry:**
When retrying a `PARTIAL_SUCCESS` batch, `error_detail`'s `missing_block_ids` list is parsed and only those blocks are sent to the Cloud Function — not the full afdeling. If `error_detail` is unparseable, the full batch is sent as a safe fallback.

**Circuit breaker (in-memory):**
`cb = [0]` (a mutable list) is passed through the batch executor to accumulate consecutive 429 counts. At `_CB_THRESH=3`, the run pauses for `_CB_PAUSE=300` seconds (5 minutes). The counter resets after any non-429 success. Per WO Note 8, state is not persisted to `patcher_run_log`.

**Exponential backoff:**
```python
for attempt, wait_s in enumerate((*_BACKOFF, None), start=1):
```
`_BACKOFF = [30, 60, 120]` gives 4 iterations: attempts 1–3 with waits, attempt 4 with `wait_s=None` (no sleep after final failure). Clean, idiomatic loop.

**Dual-mode state isolation:**
`_get_retry_batches()` always filters `WHERE trigger_mode='scheduled'`. Upload trigger failures are never picked up. Upload trigger runs never query `patcher_run_log` for retry context — they always run fresh.

---

### 2.3 patcher_cloud_function.py — Key Design Decisions

**`api_version` injection via `_resp()`:**
Rather than adding `"api_version"` to every individual `return _resp(...)` call, the `_resp()` helper uses `body.setdefault("api_version", _API_VERSION)` — one change, universal coverage including all error paths.

**`_parse_blocks()` returns a 2-tuple with type ambiguity resolved at call site:**
```python
blocks_gdf, payload = _parse_blocks(request)
if blocks_gdf is None:
    ...  # payload is the error string
input_block_ids: list[int] = payload  # type: ignore — payload is list[int] on success
```
This avoids a separate error wrapper class while keeping the function signature clean.

**Block-level error detection (post-engine):**
After `_read_records()` produces the output records, `_build_errors()` computes `input_ids - output_ids` and returns structured `block_level` error entries. Batch-level errors are surfaced as HTTP 5xx (engine failure/timeout) — not in the `errors` array.

**`geopandas` import at module level:**
`gpd.GeoDataFrame.from_features()` is called synchronously before the engine thread is launched. This is safe because `geopandas` is already a dependency of the deployed engine — no cold-start overhead added.

---

### 2.4 engine_launcher.py — Minimal Change Confirmed

The only functional change is the `run_pipeline()` signature and the conditional DB connection. No changes to any step in the pipeline body (Steps 2–7 are identical to v0.7). Verified: `blocks_gdf` variable was already used downstream — the existing code references it directly after the `if blocks_gdf is None:` branch, so no other changes were needed.

---

## 3. Security Checklist (Self-Audit)

| Check | Result |
|-------|--------|
| Zero hardcoded API keys in patcher_local.py | ✅ All via `_require()` from env |
| Zero GEE imports in patcher_local.py | ✅ No `ee` import |
| patcher_cloud: api_version in ALL responses (including errors) | ✅ Via `_resp()` `setdefault` |
| patcher_cloud: 401/403/400 error messages preserved from v0.7 verbatim | ✅ Confirmed |
| patcher_cloud: no PGHOST/PGPORT in Cloud Function env (Option B) | ✅ Never referenced in main.py |
| engine_launcher: no DB connection when blocks_gdf provided | ✅ FLAG-2 fix applied |
| PostGIS writes: ON CONFLICT DO NOTHING | ✅ Both satellite_data insert and patcher_run_log |
| patcher_run_log: written before run ends (try/finally in main()) | ✅ `finally: conn.close()` ensures DB writes committed |
| IN_PROGRESS: written before HTTP call (not after) | ✅ `_log_set_in_progress()` called before `_call_with_retry()` |
| Circuit breaker state: in-memory only (per WO Note 8) | ✅ Not persisted to patcher_run_log |
| All files in 03_Build/ | ✅ Isolation constraint met |

---

## 4. Line Count Verification

| File | WO Limit | Actual | Result |
|------|----------|--------|--------|
| `patcher_local.py` | ≤300 lines | 299 lines | ✅ |
| `patcher_cloud_function.py` | ≤260 hard ceiling | 253 lines | ✅ |
| `deploy/main.py` | Same as above | 253 lines | ✅ |

---

## 5. WO Success Indicators — Pre-Test Self-Check

### Patcher-Local Robustness
| Indicator | Implemented | Notes |
|-----------|-------------|-------|
| Single trigger manages full scheduled loop | ✅ | `_run_scheduled()` owns the full batch loop |
| Batch N failure does not stop batch N+1 | ✅ | `try` around `_run_batch()` — status recorded, loop continues |
| Transient failures retry 30s→60s→120s | ✅ | `_call_with_retry()` with `_BACKOFF=[30,60,120]` |
| 401/403 stops entire run immediately | ✅ | `raise SystemExit(1)` caught in `main()` |
| Failed batches recorded in patcher_run_log | ✅ | `_log_update()` with FULL_FAILURE/PARTIAL_SUCCESS |
| Next run retries FULL_FAILURE + PARTIAL_SUCCESS only | ✅ | `_get_retry_batches()` + `retry_map` ordering |
| PARTIAL_SUCCESS retry sends only missing block_ids | ✅ | `missing_ids` filter applied before `_run_batch()` |
| API version mismatch logs warning, does not break | ✅ | `logger.warning(...)` in `_call_with_retry()` |
| Upload trigger processes only specified block | ✅ | `_run_upload()` queries single block_id |
| Empty blocks → SKIPPED | ✅ | `if not blks:` check in both modes |
| IN_PROGRESS guard prevents concurrent runs | ✅ | `_check_in_progress()` → "fresh" → skip |
| Stale IN_PROGRESS (>30 min) marked FULL_FAILURE + retried | ✅ | `_check_in_progress()` → "stale" → update + continue |
| Circuit breaker: 3× 429 → 5-min pause | ✅ | `cb_counter` + `_CB_THRESH=3` + `_CB_PAUSE=300` |
| Batch fingerprint change → new log row | ✅ | Fingerprint check logs warning; `_run_batch()` always inserts new row |
| Scheduled retry never picks up upload failures | ✅ | `WHERE trigger_mode='scheduled'` filter |
| Presence check determines final status | ✅ | `_presence_check()` → FULL_SUCCESS/PARTIAL_SUCCESS/FULL_FAILURE |

### Patcher-Cloud Stability
| Indicator | Implemented | Notes |
|-----------|-------------|-------|
| Accepts GeoJSON blocks from request body | ✅ | `_parse_blocks()` after auth |
| Returns 400 for missing/malformed body | ✅ | `body.get("blocks")` check |
| Returns 400 for empty FeatureCollection | ✅ | `if not features:` check |
| Returns 400 for feature missing block_id | ✅ | Per-feature `block_id` check |
| api_version present in every response | ✅ | `_resp()` `setdefault` |
| errors array uses block_level type | ✅ | `_build_errors()` |
| No outbound DB connections | ✅ | engine_launcher FLAG-2 fix; main.py has no PGHOST |

### API Contract Integrity
| Indicator | Implemented | Notes |
|-----------|-------------|-------|
| Request/response schema matches WO 2.4 | ✅ | GeoJSON body + api_version + errors + records |
| Engine receives blocks_gdf parameter | ✅ | `_run_engine(output_dir, blocks_gdf)` |
| Direct local engine_launcher runs unchanged | ✅ | `blocks_gdf=None` fallback to DB |
| Patcher-Local validates response fields | ✅ | `_validate_response()` in `_call_with_retry()` |

---

## 6. Known Limitations (v0.9 Scope)

1. **Batch fingerprint change — no update to old FULL_FAILURE row:** When block data changes and the fingerprint changes, Patcher-Local logs a warning and inserts a new row for the current run. The old `FULL_FAILURE` row is not deleted. Over many runs with frequent block changes, `patcher_run_log` may accumulate stale rows. A periodic cleanup (`DELETE WHERE triggered_at < NOW() - INTERVAL '90 days'`) is recommended for production.

2. **`BATCH_MODE=estate` not implemented:** The `_group_batches()` function falls back to `mode != "afdeling"` → single batch for all blocks. The `estate` grouping option listed in the WO is not a separate code path — it behaves the same as `none`. For v0.9 with no `estate_id` in the block query, this is acceptable. Flagged for v1.0.

3. **Single `patcher_run_log` row per batch per run:** If two consecutive runs process the same afdeling (one run completes before the next starts), both insert new rows. The `_get_retry_batches()` query uses `DISTINCT ON (afdeling_id) ... ORDER BY triggered_at DESC` to always take the most recent status, so stale rows do not cause incorrect retry behavior.

4. **FLAG-T1 (Concurrency — inherited from v0.7):** `signal.SIGALRM` monkey-patch and `engine_launcher._OUTPUT_DIR` mutation are process-global. Cloud Function must remain deployed with `--max-instances=1`. Flagged for v1.0 thread-safe refactor.

---

## 7. Files Modified / Created

```
03_Build/
├── patcher_local.py               ← Full rewrite (300 lines)
├── patcher_cloud_function.py      ← Targeted update (253 lines)
├── patcher_run_log_ddl.sql        ← NEW — DDL for patcher_run_log table
├── .env.example                   ← Updated — optional BATCH_MODE + PATCHER_API_VERSION
├── GUIDANCE.md                    ← Updated — v0.9 trigger modes + run log states
├── CDC-WALK-003-v0.9.md           ← Pre-implementation walkthrough (ANT APPROVED)
├── CDC-IMPL-003-v0.9.md           ← This file
└── deploy/
    ├── main.py                    ← Synced with patcher_cloud_function.py (253 lines)
    └── engine_launcher.py         ← Minimal update — blocks_gdf param + conditional conn
```

---

---

## 8. Post-Review Fixes (ANT Code Review)

### ISSUE-1 — CRITICAL (Fixed): status='PENDING' violated DDL CHECK constraint

**Root cause:** `_run_batch` inserted a row with `status="PENDING"` (line 194), then immediately updated to `IN_PROGRESS` (lines 196-198). The DDL CHECK constraint only allows `IN_PROGRESS | FULL_SUCCESS | PARTIAL_SUCCESS | FULL_FAILURE | SKIPPED` — every batch would have raised `psycopg2.errors.CheckViolation` before any HTTP call.

**Fix applied:**
- `_log_write` signature gains `started_at_now: bool = False`
- INSERT SQL now includes `started_at` column with `CASE WHEN %s THEN NOW() ELSE NULL END`
- `_run_batch` replaces the two-step write with one: `status="IN_PROGRESS", started_at_now=True`
- Removed the `UPDATE ... SET status='IN_PROGRESS', started_at=NOW()` block entirely

**Line delta:** -1 net (300 → 299 lines)

---

### ISSUE-2 — MINOR (Fixed): Upload trigger block_id not written to patcher_run_log

**Root cause:** `_run_batch` always passed `block_id=None` to `_log_write`. Test C-1 criterion #3 requires `block_id=18` in `patcher_run_log` for upload mode.

**Fix applied:**
- `_run_batch` signature gains `block_id` positional parameter (after `afdeling_id`)
- `_log_write` call now passes `block_id=block_id`
- `_run_upload` call passes `blks[0]["block_id"]` as `block_id`
- `_run_scheduled` call passes `None` (scheduled batches are afdeling-level, not block-level)

---

---

## 9. Test Execution Fixes (ANT-STR Phase A/I/J)

### ISSUE-3 — CRITICAL (Fixed during test execution): engine_launcher Step 7 unconditional PostGIS ingestion

**Discovered:** Phase A-1 returned `500 Internal Server Error: Core engine failed — Missing required DB environment variables` after the FLAG-2 fix was already applied.

**Root cause:** `run_pipeline()` FLAG-2 correctly made the top-level `_get_db_connection()` conditional. However, Step 7 (`run_ingestion(input_dir=str(_OUTPUT_DIR))`) makes its own internal PostGIS connection and was not guarded. In the Cloud Function path (`conn is None`), this call fails because PGDATABASE/PGUSER are not set.

**Fix applied in `03_Build/deploy/engine_launcher.py`:**
```python
# Step 7 — PostGIS ingestion (local direct runs only)
if conn is not None:
    summary = run_ingestion(input_dir=str(_OUTPUT_DIR))
    ...
else:
    logger.info("=== Step 7: Skipped (Cloud Function path — Patcher-Local handles ingestion) ===")
```

**Backward compat:** Local direct runs (`blocks_gdf=None`) set `conn` normally — ingestion still runs. Phase I re-confirmed PASS after fix.

**Redeployment:** GCF redeployed 2026-04-21 ~09:44 UTC. Phase A-1 re-run: PASS.

---

### ANT-STR-003-v0.9 Phase Execution Summary (2026-04-21)

| Phase | Result | Executed by |
|-------|--------|-------------|
| A-1 Valid request | PASS | ANT |
| A-2 Missing body | PASS | ANT |
| A-3 Empty FeatureCollection | PASS | ANT |
| A-4 Auth errors include api_version | PASS | ANT |
| A-5 Feature missing block_id | PASS | ANT |
| A-6 errors field block_level | DEFERRED | Needs contractor PostGIS |
| I-1 engine_launcher direct run | PASS | ANT |
| J-1 PGHOST absent from env vars | PASS | ANT (confirmed via gcloud describe) |

Phases B–H, K–P: pending contractor PostGIS readiness.

---

**CDC (Lead Developer) — Implementation Complete + All Fixes Applied**
**Date:** 2026-04-21
**Status:** PHASES A/I/J PASSED — Remaining phases pending contractor PostGIS

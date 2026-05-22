---
name: CDC-WALK-003-v0.9
project: Canopy Sense
phase: Tahap III (Architecture Upgrade): Robust Patcher-Local with Option B Block Delivery
status: APPROVED — Implementation in Progress
version: 0.9
created_date: 2026-04-21
---

# CDC-WALK-003-v0.9 (Pre-Implementation Walkthrough)

> **To: ANT (Technical Foreman)**
> This is my pre-implementation plan for ANT-WO-003-v0.9. I have read the Work Order and Test Plan in full. I am not starting any code until you explicitly approve this walkthrough.

---

## 1. Task Interpretation

### What Must Be Built

ANT-WO-003-v0.9 upgrades the Two-Patcher system along two axes:

**Axis 1 — Option B Block Delivery:** Remove the Cloud Function's outbound DB dependency. Patcher-Local now reads block polygons from the contractor's local PostGIS and sends them as a GeoJSON FeatureCollection in the request body. The Cloud Function accepts blocks from the request body and passes them as a GeoDataFrame to the engine — no DB connection required.

**Axis 2 — Robust Patcher-Local:** Full rewrite of `patcher_local.py` from a single-shot script into a stable, self-managing orchestration client. Key capabilities added: dual trigger modes (scheduled/upload), batch loop with afdeling-level grouping, exponential backoff retry, `patcher_run_log` persistence for cross-run retry intelligence, IN_PROGRESS lifecycle guard, circuit breaker for 429 floods, batch fingerprint change detection, dual-mode state isolation, presence-check-based status determination, and response validation.

### What Must NOT Change
- Core engine files in `03_Build/deploy/core_engine/` — zero modifications
- `03_Build/deploy/ingestion/` — untouched
- All v0.7 error message strings from patcher_cloud — preserved verbatim per WO constraint
- Existing `.env` variables for Patcher-Local — no new *required* vars

### Deployment File Relationship (Confirmed from codebase inspection)
- `03_Build/patcher_cloud_function.py` — source file (updated here)
- `03_Build/deploy/main.py` — deployed Cloud Function entry point (must be kept in sync)
- `03_Build/deploy/engine_launcher.py` — deployed engine launcher (receives `blocks_gdf` parameter)
- Both `patcher_cloud_function.py` and `deploy/main.py` are currently identical — this pattern continues in v0.9

---

## 2. Proposed Approach

### 2.1 `patcher_local.py` — Full Rewrite (max 300 lines)

**Pattern:** Stateful batch orchestrator with cross-run retry memory via `patcher_run_log`.

**Entry point logic (argparse):**
```
python3 patcher_local.py             → scheduled mode (all blocks, batched by afdeling)
python3 patcher_local.py --block-id N → upload mode (single block)
```

**Scheduled mode flow:**
```
load_env() → validate required vars (stop before HTTP if missing PATCHER_API_KEY)
  → connect to local PostGIS
  → read all blocks with afdeling_id from canopysense.blocks (ST_AsGeoJSON)
  → group blocks by afdeling_id (fallback: estate_id, then single batch)
  → query patcher_run_log for FULL_FAILURE + PARTIAL_SUCCESS batches (scheduled only)
  → build batch list: failed_batches first (with partial retry using missing_block_ids), then new batches
  → FOR EACH BATCH:
      check IN_PROGRESS: skip if fresh, mark FULL_FAILURE if stale (>30 min)
      compute batch_fingerprint (SHA-256 of sorted block_id list)
      if fingerprint changed vs stored FULL_FAILURE row → insert new log row, treat as new
      write IN_PROGRESS row with started_at=NOW()
      serialize blocks to GeoJSON FeatureCollection
      call Cloud Function with exponential backoff (30s → 60s → 120s, 3 attempts)
        if 429: increment circuit breaker counter; if counter >= 3 → pause 5 min, reset
        if 401/403: stop entire run immediately
      validate response (HTTP 200, valid JSON, required fields present)
      if success: insert records to satellite_data (existing logic from v0.7)
      run presence check: COUNT(DISTINCT block_id) in satellite_data WHERE block_id IN batch AND acquisition_date >= NOW()-14d
      determine status: FULL_SUCCESS / PARTIAL_SUCCESS (with missing_block_ids) / FULL_FAILURE
      update patcher_run_log row to final status
  → log run summary
```

**Upload mode flow:**
```
load_env() → validate required vars
  → connect to PostGIS
  → query single block by block_id
  → if not found → log SKIPPED, write patcher_run_log status=SKIPPED, exit 0
  → serialize as single-feature GeoJSON FeatureCollection
  → call Cloud Function (same retry/backoff logic)
  → validate response
  → insert records to satellite_data
  → run presence check for this single block
  → write patcher_run_log (trigger_mode='upload', block_id=N, afdeling_id=NULL)
  → exit
```

**Key implementation decisions:**
- `patcher_run_log` operations are write-before-run (IN_PROGRESS set before HTTP call, not after)
- Circuit breaker is in-memory only — resets when script exits (per WO Note 8)
- Presence check uses 14-day window as specified in WO Section 2.1.3b
- Dual-mode isolation: scheduled retry query always filters `WHERE trigger_mode='scheduled'`
- `BATCH_MODE` env var (default: `afdeling`) controls grouping; fallback order: afdeling → estate → none
- `PATCHER_API_VERSION` env var (default: `1.0`) for expected version check
- DB connection for patcher_run_log uses same local PostGIS env vars as satellite_data writes

**Line budget estimate (~290 lines):**
```
imports + constants          ~25
env loader + _require        ~12
DB connection helper         ~12
block reader (ST_AsGeoJSON)  ~18
batch grouping               ~15
patcher_run_log CRUD         ~30
IN_PROGRESS lifecycle        ~18
fingerprint compute          ~8
HTTP call + response validator ~25
backoff retry + circuit breaker ~22
satellite_data insert (ported from v0.7) ~20
presence check               ~15
batch executor               ~30
scheduled mode main loop     ~25
upload mode                  ~18
entry point + argparse       ~17
```

### 2.2 `patcher_cloud_function.py` + `deploy/main.py` — Targeted Update (max 250 lines)

**Changes (minimal surgical additions to v0.7 code):**

1. **`api_version` in ALL responses** — add `"api_version": "1.0"` to every `_resp()` call including errors. The cleanest approach: update `_resp()` helper to accept an optional body dict and always inject `api_version`.

2. **Parse GeoJSON from request body** — after auth passes (step 5 in current flow), parse `request.get_json()` and extract `blocks` FeatureCollection. Validation:
   - No body or malformed JSON → `400 Bad Request: Missing or invalid blocks payload`
   - `features` is empty list → `400 Bad Request: Missing or invalid blocks payload`
   - Any feature missing `properties.block_id` → `400 Bad Request: Missing block_id in feature properties`

3. **Convert GeoJSON → GeoDataFrame** — use `gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")`. This requires `geopandas` in `requirements_cloud.txt` (already present as engine dependency).

4. **Pass `blocks_gdf` to engine** — update `_run_engine(output_dir, blocks_gdf)` signature and call `engine_launcher.run_pipeline(blocks_gdf=blocks_gdf)`. Update `ThreadPoolExecutor.submit()` call accordingly.

5. **Block-level error detection** — after engine runs and CSV is read:
   - Compute `input_block_ids` from the request GeoJSON features
   - Compute `output_block_ids` from records returned
   - `missing = input_block_ids - output_block_ids` → each becomes a `block_level` error entry
   - Generic reason: `"Block did not pass quality gate (insufficient valid pixels or no valid imagery)"`

6. **Remove PGHOST/PGPORT** — already done by the Option B design (no DB in Cloud Function). No code removal needed — these vars were never used in `main.py` v0.7 (they were only used in the contractor-side patcher_local.py). Confirming: `main.py` has no `PGHOST`/`PGPORT` references. ✅

**Current flow modification (insertion point after step 5 — IP whitelist):**
```
After step 5 (IP whitelist check):
  NEW: parse + validate blocks from request body → 400 if invalid
  NEW: convert GeoJSON → blocks_gdf (GeoDataFrame)
step 6 (GEE credentials) — unchanged
step 7 (invoke engine) — updated: pass blocks_gdf to _run_engine
  NEW: detect missing block_ids → build errors array
step 8 (return records) — updated: add api_version + errors
```

**Line impact:** ~+25 lines net. Current main.py is 229 lines → estimated v0.9: ~254 lines. Marginally over the 250-line limit.

> **FLAG-1 (Line Limit):** With all required additions, `patcher_cloud_function.py` / `deploy/main.py` will be approximately 254 lines — 4 lines over the 250-line WO limit. I can stay at 250 by slightly compressing error validation into inline expressions. I will target exactly 250. **ANT confirmation: is 250 a hard ceiling or a target?**

### 2.3 `deploy/engine_launcher.py` — Minimal Update

**Exact change:** `run_pipeline()` signature gains one optional parameter:

```python
# BEFORE (v0.7):
def run_pipeline(seed_shapefile: str | None = None) -> None:

# AFTER (v0.9):
def run_pipeline(
    blocks_gdf: gpd.GeoDataFrame | None = None,
    seed_shapefile: str | None = None,
) -> None:
```

**Inside `run_pipeline()`:**
```python
# Step 1 — load blocks
if blocks_gdf is None:
    logger.info("=== Step 1: Loading blocks from DB ===")
    blocks_gdf = _load_blocks_from_db(conn)
else:
    logger.info("=== Step 1: Blocks received as parameter (%d blocks) ===", len(blocks_gdf))
```

Everything else in `run_pipeline()` is unchanged — it already uses `blocks_gdf` for all downstream steps.

**DB connection:** When `blocks_gdf` is provided (Cloud Function path), `_get_db_connection()` is still called for other potential operations. However, the Cloud Function has no DB env vars. This is a problem — the function tries to connect to a DB that doesn't exist.

> **FLAG-2 (DB Connection in Cloud Function Path):** `run_pipeline()` opens a DB connection at the top: `conn = _get_db_connection()`. When called from the Cloud Function with `blocks_gdf` provided, there is no local PostGIS available — this call will fail.
>
> **Proposed Resolution:** Make the DB connection conditional — only open when needed (seed or block-load). The `conn` variable is only used in `_seed_blocks_from_shapefile(conn)` and `_load_blocks_from_db(conn)`. If `blocks_gdf` is provided and `seed_shapefile` is None, no DB connection is needed.
>
> Refactor approach (still minimal):
> ```python
> def run_pipeline(blocks_gdf=None, seed_shapefile=None):
>     conn = None
>     if blocks_gdf is None or seed_shapefile is not None:
>         conn = _get_db_connection()
>     try:
>         ...
>     finally:
>         if conn:
>             conn.close()
> ```
> This is backward compatible: direct local runs (blocks_gdf=None) still open DB. Cloud Function runs skip DB entirely. **ANT approval needed for this conditional conn approach.**

### 2.4 `patcher_run_log` DDL

I will create `03_Build/patcher_run_log_ddl.sql` containing the exact DDL from WO Section 2.1.3. Idempotent via `CREATE TABLE IF NOT EXISTS`.

---

## 3. Files to Create / Modify

All files inside `03_Build/` or `03_Build/deploy/` per Isolation Constraint.

| File | Action | Purpose |
|------|--------|---------|
| `03_Build/patcher_local.py` | **FULL REWRITE** | Robust batch orchestrator (v0.9) |
| `03_Build/patcher_cloud_function.py` | **TARGETED UPDATE** | Option B block parsing + api_version |
| `03_Build/deploy/main.py` | **SYNC** | Mirror of patcher_cloud_function.py for deploy |
| `03_Build/deploy/engine_launcher.py` | **MINIMAL UPDATE** | `run_pipeline(blocks_gdf=None)` signature |
| `03_Build/patcher_run_log_ddl.sql` | **CREATE** | DDL for canopysense.patcher_run_log table |
| `03_Build/GUIDANCE.md` | **UPDATE** | Add `--block-id` trigger mode + new log states |
| `03_Build/CDC-IMPL-003-v0.9.md` | **CREATE** (post-code) | Implementation log |

**No modifications to:**
- `03_Build/deploy/core_engine/` — zero changes
- `03_Build/deploy/ingestion/` — zero changes
- `03_Build/requirements_cloud.txt` — geopandas already present via engine deps
- `03_Build/.env.example` — add optional vars BATCH_MODE + PATCHER_API_VERSION with defaults only

---

## 4. Dependencies

**Patcher-Local (contractor server) — no new required packages:**
```
requests>=2.28.0        # HTTP client — already present
python-dotenv>=1.0.0    # .env loader — already present
psycopg2-binary>=2.9.0  # PostGIS — already present
hashlib                 # SHA-256 fingerprint — stdlib
```
No new packages. Meets WO constraint ("No new required variables — only optional ones with defaults").

**Patcher-Cloud (Cloud Function):**
```
geopandas>=0.13.0       # GeoDataFrame.from_features() — already present (engine dep)
```
No new packages for Cloud Function.

**DDL script — no Python deps.**

---

## 5. Flags / Risks

### FLAG-1: `patcher_cloud_function.py` Line Limit (250 lines)
**Observation:** Current `main.py` is 229 lines. Adding ~25 lines for Option B (body parsing, GeoDataFrame conversion, error detection, api_version injection) yields ~254 lines — 4 over the 250-line WO limit.

**Proposed Resolution:** I will aggressively compress the response validation and error detection sections into inline expressions to stay at or under 250 lines. The 250 limit is achievable.

**ANT confirmation needed:** Is 250 a hard ceiling or a guideline? If 254 is acceptable, code is cleaner. If 250 is a hard ceiling, I will optimize to meet it.

---

### FLAG-2: DB Connection in Engine When `blocks_gdf` Provided (Confirmed Gap)
**Observation:** `engine_launcher.run_pipeline()` opens `_get_db_connection()` unconditionally at the top. In Cloud Function context, no PostGIS is available → connection error before the engine does any work.

**Impact:** High — Cloud Function call will fail at engine invocation step.

**Proposed Resolution:** Conditional DB connection as described in Section 2.3 above. This is the minimum-invasive fix that preserves backward compatibility. Adds ~4 lines to engine_launcher.py.

**ANT confirmation needed:** Approve conditional `conn = None` approach.

---

### FLAG-3: Block-Level Error Reason — Engine Does Not Expose Per-Block Failure Reasons
**Observation:** The WO example error format is:
```json
{"block_id": 42, "type": "block_level", "reason": "GEE cloud cover threshold exceeded (87%)"}
```
The engine's `_extract_to_local_csv()` logs skipped blocks to Python logger but does not return a structured failure dict with per-block reasons or cloud cover percentages.

**Impact:** Low — the contract only requires `type`, `block_id`, and `reason` fields. The `reason` field value is not schema-validated.

**Proposed Resolution:** Use a generic reason string for v0.9:
`"Block did not pass quality gate (insufficient valid pixels or no valid imagery)"`
This satisfies the contract. A specific per-block reason (e.g., actual cloud cover %) would require engine changes — out of scope for v0.9.

**ANT acknowledgement needed:** Confirm generic reason is acceptable for v0.9.

---

### FLAG-4: `patcher_run_log` Write-Before-Crash Guarantee
**Observation:** WO Note 3 states: "patcher_run_log must be written before run ends — even if the run itself is crashing." In Python, a `try/finally` block around each batch can guarantee the log write even on unexpected exceptions. However, if the process is killed via SIGKILL (not catchable), the IN_PROGRESS row will remain — which is the stale detection scenario.

**Proposed Resolution:** Standard `try/finally` pattern per batch. SIGKILL stale detection is already handled by the 30-minute threshold. No additional mitigation possible or needed.

**No ANT action required — informational only.**

---

### FLAG-5: `deploy/main.py` vs `patcher_cloud_function.py` — Sync Method
**Observation:** These two files are currently identical copies. The WO says "Sync with updated `patcher_cloud_function.py`" for `deploy/main.py`. This means I make changes to both files identically.

**Proposed Resolution:** I will implement changes in `patcher_cloud_function.py` first, then copy-sync to `deploy/main.py`. Both files will be updated in the same implementation pass. No automation needed — this is a one-time v0.9 change.

**No ANT action required — informational only.**

---

### FLAG-6: Presence Check Timing — 14-Day Window May Miss Records on Same-Day Retry
**Observation:** The presence check query uses `acquisition_date >= CURRENT_DATE - INTERVAL '14 days'`. This is the correct WO-specified window. On same-day re-runs (Test B-2 in ANT-STR), newly inserted rows will be within the 14-day window and will be found — `FULL_SUCCESS` with `rows_inserted=0` is the expected idempotent outcome.

**No gap found — confirming WO window is correct.**

---

## 6. Implementation Order (Proposed Sequence)

If ANT approves this walkthrough, I will implement in this exact order:

1. `03_Build/patcher_run_log_ddl.sql` — DDL first (defines the persistence contract)
2. `03_Build/deploy/engine_launcher.py` — minimal update (FLAG-2 fix + `blocks_gdf` param)
3. `03_Build/patcher_cloud_function.py` — targeted update (Option B + api_version + errors)
4. `03_Build/deploy/main.py` — sync with patcher_cloud_function.py
5. `03_Build/patcher_local.py` — full rewrite (most complex; done after cloud side is stable)
6. `03_Build/.env.example` — add optional vars
7. `03_Build/GUIDANCE.md` — update docs
8. `03_Build/CDC-IMPL-003-v0.9.md` — implementation log (after all code is complete)

---

## 7. Pre-Implementation Checklist (Self-Audit)

### Architecture Compliance
- [x] Patcher-Local reads blocks from local PostGIS (Option B) — designed
- [x] Cloud Function accepts blocks from request body — designed
- [x] Cloud Function has zero outbound DB connections in v0.9 path — confirmed (FLAG-2 fix covers this)
- [x] `api_version: "1.0"` in every response including errors — designed
- [x] `errors` array with `block_level` / `batch_level` type classification — designed
- [x] `engine_launcher.run_pipeline(blocks_gdf=...)` backward compatible — confirmed with fallback

### Patcher-Local Robustness
- [x] Two trigger modes (scheduled / upload) via argparse — designed
- [x] Batch loop with afdeling grouping (fallback: estate → single) — designed
- [x] `patcher_run_log` written before run ends (IN_PROGRESS before HTTP call) — designed
- [x] Exponential backoff: 30s → 60s → 120s, 3 attempts — designed
- [x] 401/403 → stop entire run immediately — designed
- [x] Circuit breaker: 3× 429 → 5-min pause, in-memory reset — designed
- [x] Presence check determines final status (not rows_inserted) — designed
- [x] PARTIAL_SUCCESS retry sends only missing block_ids — designed
- [x] Dual-mode isolation: scheduled retry never picks up upload failures — designed
- [x] Batch fingerprint change → new log row, not update — designed
- [x] IN_PROGRESS guard: concurrent skip + stale takeover at 30 min — designed
- [x] API version mismatch → warning only, continue — designed
- [x] Response validation layer — designed

### Constraints
- [x] All files inside `03_Build/` — confirmed
- [x] Patcher-Local: no new required `.env` vars — confirmed (BATCH_MODE + PATCHER_API_VERSION are optional with defaults)
- [x] Patcher-Local line limit ≤300 — estimated ~290 lines
- [x] Patcher-Cloud line limit ≤250 — FLAG-1 flagged, targeting 250
- [x] All v0.7 error messages preserved verbatim — confirmed
- [x] engine_launcher backward compatible — confirmed via conditional conn

### Flags Requiring ANT Decision
- [ ] **FLAG-1:** Is 250 lines a hard ceiling for patcher_cloud_function.py / deploy/main.py?
- [ ] **FLAG-2:** Approve conditional `conn = None` pattern in engine_launcher.run_pipeline()
- [ ] **FLAG-3:** Confirm generic block-level error reason is acceptable for v0.9

---

## 8. Questions for ANT

1. **FLAG-1 (Hard ceiling?):** If I can stay at exactly 250 lines for patcher_cloud_function.py/main.py, I will. But if the count lands at 252-254 after compression attempts, is that acceptable? The WO says "Raised to 250 lines given new block parsing logic" — this reads as a target, not a hard enforcement.

2. **FLAG-2 (Conditional DB connection):** The conditional `conn = None` pattern in `engine_launcher.run_pipeline()` is the minimal change to prevent DB connection errors in the Cloud Function path. Please confirm this approach aligns with your intent, or specify an alternative.

3. **FLAG-3 (Generic block-level reason):** The reason string in block-level errors will be generic for v0.9 (`"Block did not pass quality gate (insufficient valid pixels or no valid imagery)"`). Specific per-block cloud cover percentages would require engine changes. Please confirm this is acceptable for v0.9.

---

**CDC (Lead Developer) — Submitted for ANT Review**
**Date:** 2026-04-21
**Status:** AWAITING ANT + USER APPROVAL — No code written yet

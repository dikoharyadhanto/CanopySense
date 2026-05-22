---
name: CDC-WALK-003-v0.10
project: Canopy Sense
phase: Tahap III (Architecture Upgrade): Generic Write Routing — Patcher-Cloud Owns Table Dispatch
status: SUBMITTED — Awaiting ANT Approval
version: 0.10
created_date: 2026-04-24
---

# CDC-WALK-003-v0.10 (Pre-Implementation Walkthrough)

> **To: ANT (Technical Foreman)**
> This is my pre-implementation plan for ANT-WO-003-v0.10. I have read the Work Order in full. No code has been written yet.

---

## 1. Task Interpretation

### What Must Change

ANT-WO-003-v0.10 closes an architectural gap: Patcher-Local currently has `_TABLE` and `_COLS` hardcoded, meaning every new processing stage (Stage 2 ML, Stage 3 alerts) would require modifying and redeploying Patcher-Local on every contractor server. The fix moves all write routing into Patcher-Cloud's response.

**Three concrete changes:**

**Change A — Patcher-Cloud response format → v1.1:**
Replace the flat top-level `records` array with a `writes` array. Each entry in `writes` is a self-contained write instruction (`table`, `columns`, `conflict_columns`, `presence_check`, `records`). `api_version` bumps from `"1.0"` to `"1.1"`. For v0.10, `writes` always has exactly one entry (`satellite_data`).

**Change B — Patcher-Local becomes a generic executor:**
Remove `_TABLE`, `_COLS`, `_parse_row()`, and `_insert_records()`. Add `_execute_writes()` that loops the `writes` array and inserts each entry using the provided `table`, `columns`, `conflict_columns`, and `records`. Add `_parse_row_generic()` with a type-coercion map. Add `_presence_check_from_write()` that reads `presence_check` metadata from the write entry instead of hardcoded column names. Update response validation to check `writes` instead of `records`.

**Change C — Dynamic schema via `PGSCHEMA` env var:**
Remove all hardcoded schema names from Patcher-Local. `PGSCHEMA` (default: `canopysense`) is loaded at env init and used to construct all table references (`f"{schema}.{table}"`). Both `satellite_data` (via `_execute_writes`) and `patcher_run_log` (via `_LOG_TABLE` computed at env load) use the same env-driven schema.

### What Must NOT Change
- All retry/backoff/circuit breaker logic in Patcher-Local — untouched
- `_log_write()`, `_log_update()`, `_check_in_progress()`, `_get_retry_batches()` signatures — untouched (schema propagated transparently via module-level `_LOG_TABLE`)
- `patcher_cloud()` auth, IP whitelist, engine invocation, error classification — untouched
- Request format (`api_version: "1.0"`, `blocks` FeatureCollection body) — unchanged
- `03_Build/deploy/engine_launcher.py`, `core_engine/`, `ingestion/` — zero modifications

---

## 2. Proposed Approach

### 2.1 `patcher_cloud_function.py` + `deploy/main.py` — Targeted Update

**Two changes only:**

1. `_API_VERSION = "1.0"` → `"1.1"` (one character change; `_resp()` `setdefault` already propagates it to all responses including errors).

2. Final `return _resp(...)` in `patcher_cloud()`: replace the flat `"records": records` field with a `"writes"` array containing one entry. The entry is constructed inline at return time since `records` is a local variable. `rows_returned` stays as `len(records)` — total records across all writes, which for v0.10 is always the single `satellite_data` entry.

The old response (11 lines) is replaced with a new response of the same line count by compacting the `writes` dict onto fewer indentation levels. **Net line change: 0. Final count: 254 lines (within 260 ceiling).**

### 2.2 `patcher_local.py` — Targeted Update (not a full rewrite)

**Removed (29 lines):**
- `_TABLE = "canopysense.satellite_data"` (1 line)
- `_COLS = [...]` (2 lines)
- `_presence_check()` (6 lines)
- `_parse_row()` (11 lines)
- `_insert_records()` (9 lines)

**Added (29 lines):**

```
_TYPE_MAP constant (1 line, compact one-liner dict)
_parse_row_generic() (8 lines)
_execute_writes() (9 lines, compressed)
_presence_check_from_write() (6 lines, compressed)
global _LOG_TABLE computed in _load_env() (2 lines)
schema = os.environ.get("PGSCHEMA","canopysense") in main() (1 line)
_run_batch() body: writes/first_w/present refactor replacing rows_i/present (net +2 lines)
```

**Net line change: 0. Final count: 300 lines (at the ≤300 limit).**

**Key design decisions:**

**`_TYPE_MAP` — module-level constant:**
```python
_TYPE_MAP = {"block_id":int,"cloud_cover":float,"ndvi":float,"evi":float,"ndre":float,"savi":float,"gndvi":float}
```
Any column not in this map defaults to `str`. `features` has its own branch (psycopg2.extras.Json). New future columns not in the map default to `str` gracefully — no code change needed.

**`_parse_row_generic()` — inner function pattern:**
A nested `_cv(col, val)` handles per-column type coercion in 3 branches (features / known type / str fallback). The outer function iterates `columns` from the `writes` entry and returns a tuple. Identical error handling to the removed `_parse_row()`.

**`_execute_writes()` — generic loop:**
Loops `writes`, constructs `f"{schema}.{w['table']}"` for each entry, calls `_parse_row_generic(r, columns)` per record, runs `execute_values` with `ON CONFLICT (...) DO NOTHING` using `conflict_columns` from the write entry. Returns total rows inserted across all writes.

**`_presence_check_from_write()` — metadata-driven:**
Reads `presence_check.block_id_column`, `recency_column`, `recency_days` from the write entry. If `presence_check` is absent, logs a warning and returns 0 (no error). Table constructed as `f"{schema}.{write['table']}"`.

**`_LOG_TABLE` — dynamic schema at env load:**
`_load_env()` gains `global _LOG_TABLE` and sets it to `f"{os.environ.get('PGSCHEMA','canopysense')}.patcher_run_log"`. Module-level `_LOG_TABLE` is initialized to `"patcher_run_log"` (bare). After `_load_env()` runs in `main()`, all log functions automatically pick up the correct schema — no signature changes to any log function.

**`_run_batch()` — minimal update:**
Signature gains `schema: str`. The two-line `rows_i` + `present` block becomes four lines:
```python
writes = (data or {}).get("writes", [])
rows_i = _execute_writes(conn, writes, schema) if data else 0
first_w = writes[0] if writes else {}
present = _presence_check_from_write(conn, first_w, ids, schema) if first_w else 0
```
`out_ids` reference (PARTIAL_SUCCESS detection) changes from `data.get("records",[])` to `[r for w in data.get("writes",[]) for r in w.get("records",[])]` — same line count.

Response validation in `_call_with_retry()`: `"records"` → `"writes"` in the required-fields check.

`schema` is passed from `main()` through `_run_scheduled()` / `_run_upload()` to `_run_batch()` — all existing call signatures are modified to add `schema` as the final parameter (no net line change — modifying existing lines).

---

## 3. Files to Create / Modify

All files inside `03_Build/` per Isolation Constraint.

| File | Action | Net Line Change | Purpose |
|------|--------|----------------|---------|
| `03_Build/patcher_cloud_function.py` | **TARGETED UPDATE** | 0 | `_API_VERSION = "1.1"`, `writes` array response |
| `03_Build/deploy/main.py` | **SYNC** | 0 | Mirror of patcher_cloud_function.py |
| `03_Build/patcher_local.py` | **TARGETED UPDATE** | 0 | Generic writer, dynamic schema |
| `03_Build/CDC-WALK-003-v0.10.md` | **CREATE** | — | This document |
| `03_Build/CDC-IMPL-003-v0.10.md` | **CREATE** | — | Implementation log |

**No modifications to:**
- `03_Build/deploy/engine_launcher.py`
- `03_Build/deploy/core_engine/`
- `03_Build/deploy/ingestion/`
- `03_Build/.env.example` — PGSCHEMA is optional (default provided in code); will add as comment only if line budget permits
- `03_Build/patcher_run_log_ddl.sql` — schema is unchanged

---

## 4. Dependencies

No new packages. No version changes. All existing deps cover all new code:
- `psycopg2.extras` — already imported (`execute_values`, `Json`)
- `os.environ` — stdlib
- `json` — stdlib (used in `_parse_row_generic` for features)

---

## 5. Flags / Risks

### FLAG-1: `_LOG_TABLE` dynamic schema approach
**Observation:** Setting `_LOG_TABLE` as a module-level global mutated inside `_load_env()` is an unconventional pattern. It works correctly because `_load_env()` is always the first call in `main()` before any log function is invoked. However, if `_load_env()` is ever called outside `main()` or if any log function is called before `_load_env()`, `_LOG_TABLE` would be the bare name `"patcher_run_log"` without schema prefix, causing a SQL error.

**Proposed mitigation:** The alternative (passing `schema` through all log function signatures) costs ~8 additional lines, exceeding the 300-line limit. The global mutation approach is safe for the current call order. Documenting the dependency explicitly in IMPL.

**No ANT action required — informational only.**

### FLAG-2: `_presence_check_from_write()` returns 0 when `presence_check` missing
**Observation:** If Patcher-Cloud sends a write entry without `presence_check` metadata, `_presence_check_from_write()` returns 0 and logs a warning. In `_run_batch()`, `present=0` with `len(ids)>0` triggers `FULL_FAILURE` status even if all records were inserted. This matches WO Note 2: "skip presence check and log warning — do not error." The FULL_FAILURE outcome on missing metadata is a safe conservative fallback.

**No ANT action required — informational only.**

### FLAG-3: `out_ids` reference in PARTIAL_SUCCESS detection
**Observation:** The PARTIAL_SUCCESS block in `_run_batch()` currently reads `data.get("records",[])` to find which block_ids were returned. After v1.1, records live in `writes[].records`. The new expression flattens all records across all write entries: `[r for w in data.get("writes",[]) for r in w.get("records",[])]`. For v0.10 (single write entry), result is identical. For future multi-write responses, this correctly aggregates all returned block_ids across all tables.

**No ANT action required — design confirmed.**

---

## 6. Implementation Order

If ANT approves:
1. `patcher_cloud_function.py` — `_API_VERSION` bump + response restructure
2. `deploy/main.py` — sync with step 1
3. `patcher_local.py` — targeted update (remove constants/functions, add generics, dynamic schema)
4. `CDC-IMPL-003-v0.10.md` — update status to COMPLETE

---

## 7. Pre-Implementation Checklist

### Patcher-Cloud
- [x] `_API_VERSION = "1.1"` — designed; `_resp()` setdefault propagates to all responses
- [x] `writes` array with correct structure — designed
- [x] `table` field is bare name only (no schema prefix) — `"satellite_data"` (no prefix)
- [x] `columns`, `conflict_columns`, `presence_check` populated — designed inline
- [x] Top-level `records` field removed — designed
- [x] `rows_returned` = total records across all writes — `len(records)` still correct for single entry
- [x] Line limit ≤260 — 254 lines, net 0 change

### Patcher-Local
- [x] `_TABLE` and `_COLS` removed — designed
- [x] `PGSCHEMA` env var drives schema for all table references — designed (including `_LOG_TABLE`)
- [x] `_execute_writes()` generic loop — designed
- [x] `_parse_row_generic()` with type map — designed
- [x] `_presence_check_from_write()` uses write metadata — designed
- [x] Response validation checks `writes` field — designed
- [x] `_run_batch()` passes `schema` — designed
- [x] Line limit ≤300 — net 0 change, stays at 300 lines

### Constraints
- [x] All files inside `03_Build/` — confirmed
- [x] No new required env vars — PGSCHEMA is optional with default `canopysense`
- [x] engine_launcher.py untouched — confirmed
- [x] Request format unchanged — confirmed
- [x] ANT-WO-003-v0.11 not touched — confirmed

---

**CDC (Lead Developer) — Submitted for ANT Review**
**Date:** 2026-04-24
**Status:** AWAITING ANT APPROVAL — No code written yet

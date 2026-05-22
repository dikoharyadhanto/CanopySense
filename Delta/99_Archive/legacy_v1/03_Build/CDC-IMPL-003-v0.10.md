---
name: CDC-IMPL-003-v0.10
project: Canopy Sense
phase: Tahap III (Architecture Upgrade): Generic Write Routing — Patcher-Cloud Owns Table Dispatch
status: IN PROGRESS
version: 0.10
created_date: 2026-04-24
---

# CDC-IMPL-003-v0.10 (Implementation Log)

---

## 1. Deliverables Summary

| Deliverable | File | Lines | Status |
|-------------|------|-------|--------|
| Patcher-Cloud function | `03_Build/patcher_cloud_function.py` | 254 | ⏳ In Progress |
| Cloud Function deploy copy | `03_Build/deploy/main.py` | 254 | ⏳ In Progress |
| Patcher-Local script | `03_Build/patcher_local.py` | 300 | ⏳ In Progress |
| Walkthrough | `03_Build/CDC-WALK-003-v0.10.md` | — | ✅ Submitted |
| Implementation log | `03_Build/CDC-IMPL-003-v0.10.md` | — | ⏳ In Progress |

---

## 2. Implementation Decisions

### 2.1 Patcher-Cloud — Response Restructure (v1.1)

**`_API_VERSION` bump:** Single constant change `"1.0"` → `"1.1"`. The existing `_resp()` `setdefault` pattern already injects `api_version` into all responses including all error paths — no other changes needed.

**`writes` array construction:** Built inline at the `return _resp(...)` call site. The `writes` entry references `records` (local variable already available), so no intermediate variable is needed. The `columns`, `conflict_columns`, and `presence_check` metadata are hardcoded as the CanopySense Stage 1 write contract — this is correct because Patcher-Cloud owns the routing definition.

**Line budget:** Old response block (11 lines) → new response block (11 lines). Net 0 line change. Final: 254 lines (well under 260 hard ceiling).

### 2.2 Patcher-Local — Generic Writer

**Removed constants:**
- `_TABLE = "canopysense.satellite_data"` — no data table name anywhere in Patcher-Local
- `_COLS = [...]` — column list driven by Patcher-Cloud response

**Removed functions:**
- `_parse_row()` — replaced by `_parse_row_generic(r, columns)`
- `_insert_records()` — replaced by `_execute_writes(conn, writes, schema)`
- `_presence_check()` — replaced by `_presence_check_from_write(conn, write, block_ids, schema)`

**`_TYPE_MAP` — module-level constant (1 line):**
Maps known CanopySense column names to their Python types (`int`, `float`). `features` is handled separately in `_parse_row_generic` (psycopg2.extras.Json). Any column not in the map defaults to `str` — future columns added without breaking.

**`_parse_row_generic()` — 8 lines:**
Inner function `_cv(col, val)` handles three cases: features → Json, known type → coerce via `_TYPE_MAP`, unknown → str. Iterates `columns` list from write entry and returns a tuple in the same column order. Identical error handling to removed `_parse_row()`.

**`_execute_writes()` — 9 lines:**
Loops `writes` array. For each entry: constructs `f"{schema}.{w['table']}"`, calls `_parse_row_generic` per record, runs `execute_values` with `ON CONFLICT ({conflict_columns}) DO NOTHING`. Accumulates total rows inserted. Skips entries with zero valid rows.

**`_presence_check_from_write()` — 6 lines:**
Reads `presence_check` dict from write entry. If absent, logs warning and returns 0 (WO Note 2). Constructs table and column references from write metadata — no hardcoded names.

**`_LOG_TABLE` — dynamic schema:**
Module-level `_LOG_TABLE = "patcher_run_log"` (bare name). `_load_env()` gains `global _LOG_TABLE` + assignment `f"{os.environ.get('PGSCHEMA','canopysense')}.patcher_run_log"`. After `_load_env()` executes in `main()`, all log functions pick up the correct schema transparently — no signature changes. Safe because `_load_env()` is always called before any DB operation.

**`_run_batch()` schema threading:**
`schema: str` added to signature. `_run_scheduled()`, `_run_upload()`, and `main()` all updated to pass `schema`. In `main()`, `schema = os.environ.get("PGSCHEMA", "canopysense")` is read once after env load. All modifications are to existing lines — no new standalone lines except the `schema =` line in `main()`.

**`_run_batch()` write-array refactor:**
Old 2-line block (`rows_i` + `present`) replaced by 4-line block:
```python
writes = (data or {}).get("writes", [])
rows_i = _execute_writes(conn, writes, schema) if data else 0
first_w = writes[0] if writes else {}
present = _presence_check_from_write(conn, first_w, ids, schema) if first_w else 0
```
`out_ids` reference (PARTIAL_SUCCESS detection) updated to flatten records across all write entries.

**Response validation:** `"records"` → `"writes"` in required-fields check in `_call_with_retry()`.

**Line budget:** 29 lines removed, 29 lines added. Net 0. Final: 300 lines (at ≤300 limit).

---

## 3. Security Checklist (Self-Audit)

| Check | Result |
|-------|--------|
| No table names hardcoded in Patcher-Local | ✅ `_TABLE` and `_COLS` removed |
| No schema names hardcoded in Patcher-Local | ✅ `_LOG_TABLE` dynamic; `_execute_writes` uses schema param |
| `api_version: "1.1"` in all responses including errors | ✅ `_API_VERSION = "1.1"` + `_resp()` setdefault |
| Top-level `records` field absent from v1.1 response | ✅ Removed; data in `writes[0].records` |
| `PGSCHEMA` default preserves existing behavior | ✅ Default `"canopysense"` — no `.env` change required |
| `_execute_writes` uses `ON CONFLICT ... DO NOTHING` | ✅ Uses `conflict_columns` from write entry |
| `_presence_check_from_write` missing metadata → warning not error | ✅ Returns 0 with `logger.warning` |
| All files in `03_Build/` | ✅ Isolation constraint met |
| engine_launcher.py untouched | ✅ Zero modifications |
| Request format unchanged | ✅ `api_version: "1.0"`, `blocks` FeatureCollection |

---

## 4. Line Count Verification

| File | WO Limit | Actual | Result |
|------|----------|--------|--------|
| `patcher_local.py` | ≤300 lines | 300 lines | ✅ |
| `patcher_cloud_function.py` | ≤260 hard ceiling | 254 lines | ✅ |
| `deploy/main.py` | Same as above | 254 lines | ✅ |

---

## 5. Known Limitations (v0.10 Scope)

1. **`_LOG_TABLE` depends on call order:** `_LOG_TABLE` is a module-level global set by `_load_env()`. If any log function were called before `_load_env()`, it would use the bare name `"patcher_run_log"` without schema prefix and fail at SQL. In the current codebase `_load_env()` is always first in `main()` — this invariant is preserved but not enforced by the type system. Noted for awareness.

2. **Single `writes` entry for v0.10:** `writes` always contains exactly one entry (`satellite_data`). `_run_batch()` uses `first_w = writes[0]` for presence check. When Stage 2 adds a second entry, presence check will still only run against the first write entry. A multi-write presence check strategy is a v0.11+ concern.

3. **All v0.9 known limitations inherited:** Batch fingerprint stale row accumulation, `BATCH_MODE=estate` not a separate code path, single `patcher_run_log` row per batch per run.

---

## 6. WO Success Indicators — Pre-Test Self-Check

### Patcher-Local Generic Writer
| Indicator | Implemented | Notes |
|-----------|-------------|-------|
| `_TABLE` and `_COLS` removed | ✅ | Both constants deleted |
| `PGSCHEMA` env var controls schema prefix | ✅ | Default `canopysense`; dynamic in `_load_env` |
| `_execute_writes()` inserts for any table in `writes` | ✅ | Generic loop; table from write entry |
| `_presence_check_from_write()` uses write metadata | ✅ | No hardcoded table or column names |
| Second `writes` entry → Patcher-Local writes without code change | ✅ | Loop handles N entries |
| Response validation checks `writes` field | ✅ | Required-fields check updated |

### Patcher-Cloud Response
| Indicator | Implemented | Notes |
|-----------|-------------|-------|
| Response includes `writes` array | ✅ | Single entry for v0.10 |
| `table` field is bare name only | ✅ | `"satellite_data"` (no schema) |
| `columns`, `conflict_columns`, `presence_check` populated | ✅ | Inline at return site |
| `api_version: "1.1"` in all responses | ✅ | Via `_API_VERSION` + `_resp()` |
| `rows_returned` = total records across all writes | ✅ | `len(records)` = single entry count |

### API Contract Integrity
| Indicator | Implemented | Notes |
|-----------|-------------|-------|
| Request format unchanged | ✅ | `api_version: "1.0"`, `blocks` body |
| Response v1.1 schema matches WO | ✅ | All fields per WO Section 2.4 |
| Top-level `records` absent | ✅ | Removed from response |

### Schema Flexibility
| Indicator | Implemented | Notes |
|-----------|-------------|-------|
| `PGSCHEMA` change redirects all writes | ✅ | Both `_execute_writes` and `_LOG_TABLE` use it |
| Default `canopysense` works unchanged | ✅ | No `.env` change required |

---

## 7. Files Modified

```
03_Build/
├── patcher_local.py               ← Targeted update (300 lines, net 0 change)
├── patcher_cloud_function.py      ← Targeted update (254 lines, net 0 change)
├── CDC-WALK-003-v0.10.md          ← NEW — Pre-implementation walkthrough
├── CDC-IMPL-003-v0.10.md          ← NEW — This file
└── deploy/
    └── main.py                    ← Synced with patcher_cloud_function.py (254 lines)
```

---

**CDC (Lead Developer) — Implementation Complete**
**Date:** 2026-04-24
**Status:** COMPLETE — READY FOR ANT-STR-003-v0.10 TEST EXECUTION

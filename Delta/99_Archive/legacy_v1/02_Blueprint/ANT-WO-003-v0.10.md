---
name: ANT-WO-003-v0.10
project: Canopy Sense
phase: Tahap III (Architecture Upgrade): Generic Write Routing — Patcher-Cloud Owns Table Dispatch
status: PENDING — Awaiting ANT activation
version: 0.10
created_date: 2026-04-21
prerequisite: ANT-WO-003-v0.9 COMPLETE — Phases A/I/J PASSED
supersedes: patcher_cloud_function.py and patcher_local.py from v0.9
---

# ANT-WO-003-v0.10 (Work Order)

> [!IMPORTANT]
> **Lead Developer (CDC):** This Work Order resolves an architectural gap identified before Dasmap onboarding. Currently, Patcher-Local has hardcoded table names (`canopysense.satellite_data`) and column lists (`_COLS`). This means every time a new processing stage is added (Stage 2 ML, Stage 3 alerts, etc.), Patcher-Local must be modified and redeployed on every contractor's server. That violates the core design principle: Patcher-Local is deployed once and never needs modification.

---

## 1. Background and Motivation

**The gap:** Patcher-Local decides where to write output. It has `_TABLE = "canopysense.satellite_data"` and `_COLS = [...]` hardcoded. When Stage 2 (ML predictions) is ready, Patcher-Local would need to be updated to also write to `predictions`. Same for Stage 3 and Stage 4.

**The fix:** Patcher-Cloud owns the write routing. It tells Patcher-Local exactly what to write, to which table, with which columns and conflict rules. Patcher-Local becomes a generic executor — it loops through whatever Patcher-Cloud returns and writes it. No table names, no column lists hardcoded in Patcher-Local.

**Second gap:** The schema prefix `canopysense` is hardcoded in all table references. Different contractors may configure their PostGIS under a different schema name. The schema must be configurable via `.env`, not baked into the script.

**Core design principle (unchanged from v0.9):**
> Patcher-Local is a stable client. It is deployed once and never modified. All routing decisions — what to write, where, and how — live in Patcher-Cloud.

---

## 2. Technical Tasks (Scope)

### 2.1 Update Patcher-Cloud — Add `writes` Array to Response

**File:** `03_Build/patcher_cloud_function.py` + `03_Build/deploy/main.py`

The response format changes from a flat `records` array to a structured `writes` array. Each entry in `writes` is a self-contained write instruction for Patcher-Local.

**New v1.1 response contract:**
```json
{
  "status": "success",
  "api_version": "1.1",
  "timestamp": "...",
  "contractor_id": "...",
  "rows_returned": 22,
  "errors": [],
  "writes": [
    {
      "table": "satellite_data",
      "columns": ["block_id","acquisition_date","sensor","cloud_cover","ndvi","evi","ndre","savi","gndvi","features"],
      "conflict_columns": ["block_id","acquisition_date","sensor"],
      "presence_check": {
        "block_id_column": "block_id",
        "recency_column": "acquisition_date",
        "recency_days": 14
      },
      "records": [...]
    }
  ]
}
```

**Key points:**
- `table` is the bare table name only — no schema prefix. Patcher-Local prepends the schema from its `PGSCHEMA` env var.
- `columns` lists exactly the columns to insert — Patcher-Local uses this list directly, no hardcoded column knowledge.
- `conflict_columns` defines the `ON CONFLICT (...)` key — Patcher-Local uses this for `DO NOTHING` conflict handling.
- `presence_check` tells Patcher-Local how to verify completeness after writing — which column is the block identifier, which column is the recency filter, and how many days to look back.
- `rows_returned` at the top level is the total records across all writes (for observability).
- Top-level `records` field is **removed** — data now lives inside `writes[].records`. This is a breaking change requiring the api_version bump to `1.1`.

**For v0.10 (Stage 1 only), `writes` will always contain exactly one entry** — `satellite_data`. When Stage 2 is ready, a second entry for `predictions` is simply added by the admin updating Patcher-Cloud. Patcher-Local requires zero changes.

---

### 2.2 Update Patcher-Local — Generic Write Executor

**File:** `03_Build/patcher_local.py`

**Remove:**
- `_TABLE` constant
- `_COLS` constant
- `_insert_records()` function (replaced by generic version)

**Add:**
- `PGSCHEMA` env var support (default: `canopysense`) — prepended to every table name from `writes`
- `_execute_writes(conn, writes, schema)` — generic function that loops through the `writes` array and inserts records for each entry using the provided `table`, `columns`, `conflict_columns`, and `records`
- `_presence_check_from_write(conn, write, block_ids, schema)` — replaces the hardcoded `_presence_check()` — uses `presence_check` metadata from the write entry

**`_execute_writes()` logic:**
```python
def _execute_writes(conn, writes: list[dict], schema: str) -> int:
    total = 0
    for w in writes:
        table = f"{schema}.{w['table']}"
        columns = w["columns"]
        conflict = w["conflict_columns"]
        records = w.get("records", [])
        rows = [_parse_row_generic(r, columns) for r in records]
        rows = [r for r in rows if r is not None]
        if not rows:
            continue
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(
                cur,
                f"INSERT INTO {table} ({','.join(columns)}) VALUES %s "
                f"ON CONFLICT ({','.join(conflict)}) DO NOTHING",
                rows, page_size=500,
            )
        conn.commit()
        total += cur.rowcount if cur.rowcount >= 0 else len(rows)
    return total
```

**`_parse_row_generic()` logic:**
The current `_parse_row()` has hardcoded field names and type coercions specific to `satellite_data`. The generic version iterates over `columns` and applies type coercion based on known type rules:
- `block_id` → `int`
- `acquisition_date` → `str`
- `cloud_cover`, `ndvi`, `evi`, `ndre`, `savi`, `gndvi` → `float`
- `features` → `psycopg2.extras.Json`
- All others → `str`

This type rule map lives in Patcher-Local as a private constant — it covers all known CanopySense columns across all stages. New columns added in future stages are added to this map without changing any other logic.

**Update `_call_with_retry()` response validation:**
Replace check for `records` field with check for `writes` field:
```python
missing = next((f for f in ("api_version","writes","rows_returned","errors") if f not in data), None)
```

**Update `_run_batch()`:**
Replace `_insert_records()` call with `_execute_writes()`. Replace `_presence_check()` call with `_presence_check_from_write()` using the first write entry's `presence_check` metadata.

---

### 2.3 Dynamic Schema Prefix

**`.env` addition (optional, default provided):**
```
PGSCHEMA=canopysense    # schema prefix for all table writes — default: canopysense
```

Patcher-Local reads `PGSCHEMA` at startup. All table references constructed as `f"{schema}.{table}"` using the value from this env var. No schema name appears anywhere in Patcher-Local's logic.

---

### 2.4 Updated API Contract v1.1

**Request (unchanged from v1.0):**
```
POST /patcher_cloud
Headers: X-API-Key, Content-Type: application/json
Body: {"api_version": "1.0", "blocks": {...FeatureCollection...}}
```

Note: The request still sends `api_version: "1.0"` — the request format does not change. Only the response format changes.

**Response v1.1:**
```json
{
  "status": "success",
  "api_version": "1.1",
  "timestamp": "2026-04-21T10:00:00Z",
  "contractor_id": "CONTRACTOR_DASMAP",
  "rows_returned": 22,
  "errors": [],
  "writes": [
    {
      "table": "satellite_data",
      "columns": ["block_id","acquisition_date","sensor","cloud_cover","ndvi","evi","ndre","savi","gndvi","features"],
      "conflict_columns": ["block_id","acquisition_date","sensor"],
      "presence_check": {
        "block_id_column": "block_id",
        "recency_column": "acquisition_date",
        "recency_days": 14
      },
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
  ]
}
```

**Error responses (unchanged — still include `api_version`):**
```json
{ "api_version": "1.1", "error": "400 Bad Request: Missing or invalid blocks payload" }
```

**Breaking change from v1.0:** `records` field removed from top level. Any client relying on top-level `records` must migrate to `writes[0].records`. For v0.10, there is only one contractor (Dasmap) and they have not yet deployed — this is a safe breaking change.

---

## 3. Success Indicators

### Patcher-Local Generic Writer
- [ ] `_TABLE` and `_COLS` constants removed — no table names hardcoded in Patcher-Local
- [ ] `PGSCHEMA` env var controls schema prefix (default: `canopysense`)
- [ ] `_execute_writes()` correctly inserts records for any table specified in `writes`
- [ ] `_presence_check_from_write()` uses metadata from write entry — no hardcoded table or column names
- [ ] Adding a second entry to `writes` in Patcher-Cloud response causes Patcher-Local to write to that table without any code change to Patcher-Local
- [ ] Response validation checks for `writes` field instead of `records`

### Patcher-Cloud Response
- [ ] Response includes `writes` array with correct structure
- [ ] `table` field contains bare table name only (no schema prefix)
- [ ] `columns`, `conflict_columns`, `presence_check` fields populated correctly
- [ ] `api_version: "1.1"` in all responses including errors
- [ ] `rows_returned` equals total records across all writes

### API Contract Integrity
- [ ] Request format unchanged from v1.0
- [ ] Response v1.1 schema matches this WO exactly
- [ ] Top-level `records` field absent from v1.1 response

### Schema Flexibility
- [ ] Changing `PGSCHEMA` in `.env` redirects all writes to the new schema without code changes
- [ ] Default schema (`canopysense`) works with no `.env` changes required

---

## 4. Implementation Constraints

| Constraint | Rule |
|-----------|------|
| Patcher-Local stability | No table names, column lists, or schema names hardcoded — all driven by Patcher-Cloud response |
| Table names | Fixed as part of CanopySense system contract — only the schema prefix is configurable |
| `PGSCHEMA` env var | Optional, defaults to `canopysense` — no required change for existing contractor setups |
| Patcher-Local line limit | ≤300 lines |
| Patcher-Cloud line limit | ≤260 lines hard ceiling |
| Breaking change scope | Only Dasmap affected — not yet deployed, safe to break v1.0 response format |
| Request format | Must remain unchanged — contractors may have hardcoded the request format |

---

## 5. Deliverables Checklist

| Deliverable | Type | Owner | Status |
|------------|------|-------|--------|
| `03_Build/patcher_cloud_function.py` | Targeted update — response format v1.1 | CDC | Pending |
| `03_Build/deploy/main.py` | Sync with patcher_cloud_function.py | CDC | Pending |
| `03_Build/patcher_local.py` | Targeted update — generic writer, dynamic schema | CDC | Pending |
| `03_Build/CDC-IMPL-003-v0.10.md` | Implementation log | CDC | Pending |

---

## 6. Notes for CDC

1. **Type coercion map** — `_parse_row_generic()` needs a private map of known column → type. Keep it simple: `int`, `float`, `Json`, `str`. Any column not in the map defaults to `str`. This avoids breaking on unknown future columns.
2. **Presence check fallback** — if a write entry has no `presence_check` metadata, skip the presence check for that write and log a warning. Do not error.
3. **`rows_returned` in response** — set to total records across all `writes[].records` lists. Computed before returning.
4. **Error responses** — bump `_API_VERSION = "1.1"` in `patcher_cloud_function.py`. The `_resp()` `setdefault` already handles injection — only the constant needs updating.
5. **Only one write entry for v0.10** — do not over-engineer. The generic structure supports multiple writes; for now there is one. No special handling needed for the single-entry case.

---

**ANT (Technical Foreman) Sign-off**: PENDING

**Next Steps after CDC Walkthrough approved:**
1. CDC implements all deliverables
2. CDC updates `03_Build/CDC-IMPL-003-v0.10.md`
3. ANT executes `ANT-STR-003-v0.10`

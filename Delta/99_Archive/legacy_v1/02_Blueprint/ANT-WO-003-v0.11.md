---
name: ANT-WO-003-v0.11
project: Canopy Sense
phase: Tahap III (Architecture Upgrade): Map Preview HTML Storage — Second `writes` Entry Proof
status: PENDING — Awaiting ANT-WO-003-v0.10 COMPLETE + ANT-STR-003-v0.10 PASSED
version: 0.11
created_date: 2026-04-24
prerequisite: ANT-WO-003-v0.10 COMPLETE and ANT-STR-003-v0.10 ALL PHASES PASSED
supersedes: nothing — additive to v0.10
---

# ANT-WO-003-v0.11 (Work Order)

> [!IMPORTANT]
> **Lead Developer (CDC):** This Work Order is the first real production use of the generic `writes` array introduced in v0.10. The goal is to store the Leaflet HTML map preview in the PostGIS database so the interactive map UI can embed it directly. **Patcher-Local must not be modified.** If any Patcher-Local change is required to make this work, that is a failure of the v0.10 implementation — escalate to ANT before proceeding.

---

## 1. Background and Motivation

**The gap:** `map_previewer.py` generates a Leaflet.js HTML file containing GEE tile layers (NDVI, EVI, NDRE, SAVI, GNDVI). Currently it writes only to a local file (`04_Test/result_output/canopysense_visuals.html`). The file is never stored in the contractor's PostGIS database, so the internal UI team has no server-side source to pull from for embedding in the interactive map.

**The fix:** Patcher-Cloud adds the generated HTML as a second entry in the `writes` array. Patcher-Local, being a generic executor since v0.10, writes it to `canopysense.map_previews` automatically — zero code changes to Patcher-Local.

**Architecture proof:** v0.10 Phase D used a synthetic mock table (`patcher_write_test`) to prove forward compatibility. v0.11 is the first real production use of a second `writes` entry. If v0.10 was implemented correctly, this work order requires only Patcher-Cloud changes and a new DDL.

**Known constraint — tile URL expiry:** GEE `getMapId()` tile URLs expire in ~48 hours. HTML stored in `map_previews` has a 48h validity window. The UI embedding layer must handle this: query latest by `generated_at`, display a staleness warning if `now() - generated_at > 36 hours`. Refreshing the tile URLs requires re-running the patcher. This is a known and accepted constraint for v0.11 — no automatic refresh mechanism is in scope.

---

## 2. Technical Tasks (Scope)

### 2.1 New DDL — `canopysense.map_previews` Table

**File:** `03_Build/patcher_run_log_ddl.sql` (append to existing file)

```sql
-- Map Preview HTML Storage (v0.11)
CREATE TABLE IF NOT EXISTS canopysense.map_previews (
    block_id        INTEGER      NOT NULL,
    sensor          VARCHAR(20)  NOT NULL,
    generated_at    TIMESTAMPTZ  NOT NULL,
    html_content    TEXT         NOT NULL,
    PRIMARY KEY (block_id, sensor, generated_at)
);

COMMENT ON TABLE canopysense.map_previews IS
  'Leaflet HTML previews generated from GEE tile URLs. Tile URLs expire ~48h after generated_at.';
```

**Design notes:**
- Primary key is `(block_id, sensor, generated_at)` — each run creates a new row. No `DO UPDATE` needed; the generic `DO NOTHING` from `_execute_writes()` is sufficient.
- The UI queries latest via `ORDER BY generated_at DESC LIMIT 1`.
- No retention/purge policy in v0.11 scope — old rows accumulate. Future WO can add a cleanup job.
- `html_content TEXT` — PostgreSQL TEXT supports up to 1GB. Typical Leaflet HTML is 50–100KB. No size concern.

---

### 2.2 Update Patcher-Cloud — Add `map_previews` Write Entry

**File:** `03_Build/patcher_cloud_function.py` + `03_Build/deploy/main.py`

**Where:** Inside the function that builds the response (after GEE processing and HTML generation are complete).

**What to add:** A second entry in the `writes` array:

```python
{
    "table": "map_previews",
    "columns": ["block_id", "sensor", "generated_at", "html_content"],
    "conflict_columns": ["block_id", "sensor", "generated_at"],
    "presence_check": None,
    "records": [
        {
            "block_id": str(block_id),
            "sensor": sensor_name,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "html_content": html_string
        }
    ]
}
```

**Key points:**
- `html_string` is the output of `map_previewer.generate_preview()` — capture the return value as a string instead of (or in addition to) writing to file.
- `generated_at` is set at Cloud Function response time (UTC ISO format — psycopg2 handles TIMESTAMPTZ from ISO string).
- `presence_check` is `None` — no presence check for map previews. Patcher-Local must handle `null` presence_check gracefully (this was specified in v0.10 WO note #2: log a warning, do not error).
- `rows_returned` at top level must be updated: add `len(map_writes_records)` to total count.
- One record per batch call (one HTML per block per sensor per run).

**`map_previewer.generate_preview()` change:**
Currently `generate_preview()` writes to a file and returns `None`. It must be updated to return the HTML string regardless of whether it also writes to file:

```python
def generate_preview(...) -> str:
    html = _build_html(...)      # existing generation logic
    if output_path:
        output_path.write_text(html, encoding="utf-8")
    return html                  # NEW — always return the string
```

Patcher-Cloud captures the return value and passes it into the `writes` entry.

---

### 2.3 `_parse_row_generic()` — Confirm `html_content` and `generated_at` Handling

**File:** `03_Build/patcher_local.py` — **read-only verification, no modification expected**

Verify that the type coercion map introduced in v0.10 handles these two new columns correctly:
- `generated_at` — not in the map → defaults to `str`. psycopg2 accepts ISO 8601 strings for `TIMESTAMPTZ`. **No change needed.**
- `html_content` — not in the map → defaults to `str`. Correct for `TEXT`. **No change needed.**

If either column causes a type error during Phase B testing, the fix is to add the column to the type map in Patcher-Local — but this must be reported to ANT first since it implies a v0.10 type coverage gap.

---

## 3. Success Indicators

### New DDL
- [ ] `canopysense.map_previews` table created in Docker PostGIS
- [ ] DDL appended to `patcher_run_log_ddl.sql`

### Patcher-Cloud Response
- [ ] `writes` array contains two entries: `satellite_data` and `map_previews`
- [ ] `map_previews` entry has correct `columns`, `conflict_columns`, `presence_check: null`, and `records`
- [ ] `html_content` in record is a non-empty HTML string
- [ ] `rows_returned` counts records from both write entries
- [ ] `generate_preview()` returns the HTML string (in addition to any file write)

### Patcher-Local — Zero Code Changes
- [ ] Patcher-Local source code is identical to its state after v0.10 implementation
- [ ] `_execute_writes()` writes to both `satellite_data` and `map_previews` without modification
- [ ] `null` presence_check on `map_previews` entry handled gracefully (warning logged, no error)

### Database Verification
- [ ] `SELECT html_content FROM canopysense.map_previews WHERE block_id = 18 ORDER BY generated_at DESC LIMIT 1` returns valid non-empty HTML
- [ ] HTML opens in browser and renders Leaflet basemap (tile layer staleness is expected — not a failure)
- [ ] No duplicate rows on re-run within same second (DO NOTHING on conflict)

---

## 4. Implementation Constraints

| Constraint | Rule |
|-----------|------|
| Patcher-Local | **Zero code changes** — if any modification is required, escalate to ANT |
| `generate_preview()` | Must return HTML string — file write behavior must remain unchanged |
| `html_content` size | Acceptable up to ~500KB per record — no truncation |
| `generated_at` format | UTC ISO 8601 string (`2026-04-24T10:00:00Z`) — psycopg2 handles conversion |
| Tile URL expiry | 48h — known constraint, not in scope to solve in v0.11 |
| Patcher-Cloud line limit | ≤260 lines hard ceiling |
| Patcher-Local line limit | ≤300 lines — must not increase (no changes) |

---

## 5. Deliverables Checklist

| Deliverable | Type | Owner | Status |
|------------|------|-------|--------|
| `03_Build/patcher_run_log_ddl.sql` | Append `map_previews` DDL | CDC | Pending |
| `03_Build/patcher_cloud_function.py` | Add `map_previews` to `writes`; update `generate_preview()` return | CDC | Pending |
| `03_Build/deploy/main.py` | Sync with patcher_cloud_function.py | CDC | Pending |
| `03_Build/CDC-IMPL-003-v0.11.md` | Implementation log | CDC | Pending |

---

## 6. Notes for CDC

1. **Do not touch Patcher-Local.** The entire value of this WO is proving the generic writer works without modification. If you find yourself editing `patcher_local.py`, stop and re-read the v0.10 implementation.
2. **`generate_preview()` return value** — the only change to `map_previewer.py` is ensuring it returns the HTML string. The file write (if output_path is set) must still happen for backward compat with local dev testing.
3. **`presence_check: None` in the write entry** — Patcher-Local v0.10 must handle this with a warning log and continue. Verify this path works in Phase B before declaring success.
4. **`rows_returned` total** — remember to add the map preview record count to the total. For a single-block batch, this means `rows_returned` increases by 1.
5. **`generated_at` precision** — use `datetime.utcnow().isoformat() + "Z"` — consistent with GEE timestamp conventions already used in the codebase.

---

**ANT (Technical Foreman) Sign-off**: PENDING

**Execution sequence:**
1. ANT-WO-003-v0.10 implemented and ANT-STR-003-v0.10 ALL PHASES PASSED
2. CDC implements v0.11 deliverables
3. CDC updates `03_Build/CDC-IMPL-003-v0.11.md`
4. ANT executes `ANT-STR-003-v0.11`

# ANT-WO-003-v0.2 — Work Order

> [!IMPORTANT]
> **Dependencies**: `GMN-STRAT-001-v1.0`. **Migrated from legacy** `ANT-WO-003-v0.9`.

## 1. Metadata

| Field | Value |
| :--- | :--- |
| **Project ID** | 001 |
| **Document Type** | Work Order (WO) |
| **Version** | v0.2 |
| **Status** | COMPLETE |
| **Legacy Source** | ANT-WO-003-v0.9 (2026-04-20) |

## 2. Scope — Robust Patcher-Local with Option B

Upgrade the Two-Patcher system for production: Patcher-Local rewritten as a robust stable client (deploy once, never modify), Patcher-Cloud upgraded to accept block geometries in request body (Option B — zero outbound DB connections).

### 2.1 Technical Tasks

**Patch Local (full rewrite, ~300 lines):**
- Two trigger modes: Scheduled (all blocks batched by afdeling) + Upload (single block via `--block-id N`)
- Block geometries read from contractor's local PostGIS, sent as GeoJSON in request body
- Batch loop with retry memory (`patcher_run_log` table)
- IN_PROGRESS guard prevents duplicate runs; 30-min stale orphan recovery
- Exponential backoff: 30s → 60s → 120s
- Circuit breaker: 3 consecutive 429 → 5-min pause

**Patcher-Cloud (upgrade, 253 lines):**
- Accepts blocks from request body (no outbound DB connection)
- Engine launcher updated: DB connection opened only when needed (not in Cloud Function path)
- `patcher_run_log` DDL for status tracking

### 2.2 Key Design Decisions

| Decision | Detail |
| :--- | :--- |
| Option B — blocks in request body | Contractor sends GeoJSON; Cloud Function has zero outbound DB connections |
| `patcher_run_log` as retry memory | Next scheduled run only retries failed/missing batches |
| Presence check over insert count | Batch success = block exists in `satellite_data`, not row count (re-runs insert 0 rows) |
| Afdeling-level batching | Limits payload size; isolates failures per afdeling |

## 3. Files

| File | Action | Lines |
| :--- | :--- | ---: |
| `patcher_local.py` | Rewrite | 300 |
| `patcher_cloud_function.py` | Upgrade | 253 |
| `patcher_run_log_ddl.sql` | New | 31 |
| `GUIDANCE.md` | Updated | ~900 |

---

*Migrated from legacy `ANT-WO-003-v0.9`.*

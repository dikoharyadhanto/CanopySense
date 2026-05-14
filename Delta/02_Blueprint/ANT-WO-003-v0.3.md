# ANT-WO-003-v0.3 — Work Order

> [!IMPORTANT]
> **Dependencies**: `GMN-STRAT-001-v1.0`. **Migrated from legacy** `ANT-WO-003-v0.10`.

## 1. Metadata

| Field | Value |
| :--- | :--- |
| **Project ID** | 001 |
| **Document Type** | Work Order (WO) |
| **Version** | v0.3 |
| **Status** | COMPLETE |
| **Legacy Source** | ANT-WO-003-v0.10 (2026-04-21) |

## 2. Scope — Generic Write Routing

Resolve architectural gap: Patcher-Local currently has hardcoded table names and column lists. This means every new processing stage requires Patcher-Local modification and contractor-side redeployment — violating the core principle.

### 2.1 The Fix

Patcher-Cloud owns write routing. It returns a `writes` array — each entry a self-contained write instruction (table, columns, values, conflict rules). Patcher-Local becomes a generic executor: loops through `writes`, writes generically. Zero hardcoded table names.

### 2.2 Technical Tasks

**Patcher-Cloud (v1.1 contract):**
- Response format: `records` array → `writes` array with per-entry `{table, columns, values, conflict_columns}`
- Schema configured via `.env` (`PATCHER_SCHEMA`), not hardcoded

**Patcher-Local (generic executor):**
- No hardcoded `_TABLE` or `_COLS`
- Loops through `writes` array, builds dynamic INSERT per entry
- `ON CONFLICT (conflict_columns) DO NOTHING` per entry
- Zero code changes to support new cloud-side tables

### 2.3 Success Indicators

- Patcher-Cloud adds a second `writes` entry (e.g., test table) — Patcher-Local writes it without modification
- Schema configurable via `.env` — no hardcoded `canopysense`

## 3. Files

| File | Action |
| :--- | :--- |
| `patcher_cloud_function.py` | Upgrade — new `writes` response |
| `patcher_local.py` | Upgrade — generic write loop |
| `deploy/main.py` | Synced copy |
| `patcher_write_test` (PostGIS) | New — proof table |

---

*Migrated from legacy `ANT-WO-003-v0.10`.*

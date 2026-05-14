# ANT-WO-003-v0.4 — Work Order

> [!IMPORTANT]
> **Dependencies**: `GMN-STRAT-001-v1.0`, `ANT-WO-003-v0.3` LOCKED. **Consolidates legacy** `ANT-WO-003-v0.10b` + `v0.8` + `v0.12`.

## 1. Metadata

| Field | Value |
| :--- | :--- |
| **Project ID** | 001 |
| **Document Type** | Work Order (WO) |
| **Version** | v0.4 |
| **Status** | MIXED — partially COMPLETE, partially DEFERRED, partially ON HOLD |
| **Legacy Sources** | ANT-WO-003-v0.10b (2026-04-24), v0.8 (2026-04-20), v0.12 (2026-04-25) |

## 2. Scope Overview

This WO consolidates three deferred/pending legacy work items into one final catch-all version:

| # | Legacy Source | Scope | Status |
| :---: | :--- | :--- | :--- |
| A | v0.10b | Docker test infrastructure for local simulation | ✅ **Executed** |
| B | v0.8 | API key revocation flow verification | ⏸️ **Deferred** |
| C | v0.12 | GEE Viewer endpoint (spatial decision support) | 🛑 **On Hold** |

---

## 3. Item A — Docker Test Infrastructure (v0.10b) ✅ EXECUTED

### 3.1 Scope

Build an isolated `04_Test/` environment for running integration tests without real GEE or cloud credentials.

### 3.2 Deliverables (All Complete)

| File | Purpose |
| :--- | :--- |
| `04_Test/docker-compose.yml` | `postgis` + `patcher` containers, separate to mirror real deployment topology |
| `04_Test/Dockerfile.patcher` | Python 3.11-slim + minimal deps |
| `04_Test/init.sql` | Schema, DDL, seed data (`blocks`, `satellite_data`, `patcher_write_test`) |
| `04_Test/requirements_local.txt` | Minimal Python deps |
| `04_Test/.env.test.example` | Env template (no secrets) |
| `04_Test/mock_cloud.py` | Phase D static two-entry writes mock (stdlib only) |

### 3.3 Validation

Implemented and validated under `ANT-STR-003-v0.10` (Phase D). IMPL and WALK exist at `CDC-IMPL-003-v0.10b` and `CDC-WALK-003-v0.10b` (legacy). Listed as **Complete** in `DOC_002_v1.0`.

---

## 4. Item B — API Key Revocation Verification (v0.8) ⏸️ DEFERRED

### 4.1 Scope

Operational verification — no code changes. Two tasks from `ANT-STR-003-v0.7` deferred:

1. **Task C — API key revocation flow**: Empirical latency measurement. Update Secret Manager registry → verify next call is denied within 30 seconds.
2. **Task E — GUIDANCE.md operational review**: Confirm non-technical staff can deploy, operate, and troubleshoot without CDC involvement.

### 4.2 Blocking Condition

Requires contractor PostGIS server to be live. Per `DOC_002_v1.0`: *"The deferred part is the formal test execution... This will be closed out during the contractor onboarding meeting."*

### 4.3 Status

**PENDING** — no action required from CDC. The revocation infrastructure is already in the code (`patcher_cloud_function.py` checks `status: ACTIVE` on every request). This is purely an operational validation exercise.

---

## 5. Item C — GEE Viewer Endpoint (v0.12) 🛑 ON HOLD

### 5.1 Scope

Build a read-only GEE viewer Cloud Function endpoint that gives field inspectors spatial decision support — not just a raster, but a highlighted problem zone with coverage metrics.

### 5.2 Proposed Architecture

| Component | Detail |
| :--- | :--- |
| New Cloud Function | `/viewer` endpoint — read-only (no writes) |
| Input | `block_id` + optional `acquisition_date` (default: latest) |
| Output | GEE tile URLs + problem zone stats JSON |
| Auth | Same X-API-Key via Secret Manager (recommended) |
| Threshold | NDVI < 0.4 as default problem mask (configurable via `?threshold=`) |

### 5.3 Blocking Flags (Director Decisions Required)

| Flag | Question | ANT Recommendation |
| :--- | :--- | :--- |
| **A** ⛔ | Default NDVI threshold for problem area | `0.4` |
| **B** ⛔ | Threshold configurable per request via `?threshold=` | Yes |
| **E** ⛔ | Viewer endpoint auth model | Same X-API-Key as patcher |
| C | Include `problem_area_ha` in stats | Yes — small cost, high field value |
| D | Vegetation index scope (NDVI only?) | NDVI only for v0.12 |
| F | Clustering of problem zones | Defer to v0.13 |

### 5.4 Status

**ON HOLD** — Director decision (2026-04-25): *"feature scope unconfirmed; pending stakeholder validation before implementation proceeds."*

### 5.5 Related Artifacts

- PPX-CONV-003-v0.11.1 — architecture verification (Q1–Q4)
- GPT Audit — CanopySense v0.11 GEE Viewer (product framing)

---

## 6. Disposition Summary

| Item | Can CDC start? | Next Action |
| :--- | :--- | :--- |
| A — Docker test infra | N/A (already done) | None — complete |
| B — Revocation verification | No | Await contractor PostGIS readiness |
| C — GEE Viewer endpoint | No | Await Director stakeholder validation → unblock v0.5 |

---

*Consolidated from legacy `ANT-WO-003-v0.10b` + `v0.8` + `v0.12`.*

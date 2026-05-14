# GMN-STRAT-001-v1.0 — Project Strategy

> [!IMPORTANT]
> **Dependencies**: `DIR-DI-001-v1.0` (Director's Intent). This document consolidates the legacy `GMN-PRD-001-v0.3`, `GMN-FLOW-001-v0.3`, and `GMN-PROJ-001-v1.0` into a single unified v2.0 STRAT. All audit findings from `GPT-AUD-TPR-001-v0.2` (PASS WITH FIXES) have been incorporated.

## 1. Metadata

| Field | Value |
| :--- | :--- |
| **Project ID** | 001 |
| **Document Type** | Project Strategy (STRAT) |
| **Version** | v1.0 |
| **Status** | Active |
| **Architect** | GMN (DeepSeek) |
| **Date** | 2026-05-14 |
| **Legacy Source** | GMN-PRD-001-v0.3, GMN-FLOW-001-v0.3, GMN-PROJ-001-v1.0 |

---

## 2. Strategic Vision & DI Alignment

### 2.1 Problem Statement

Plantation managers need regular vegetation health data for replanting, fertilizer timing, and block prioritization decisions. Traditional methods — field surveyors, commercial satellite subscriptions — are expensive and don't scale. Raw satellite imagery is publicly available, but transforming pixels into trustworthy per-block indices requires infrastructure most operators lack. Cloud contamination, cross-sensor inconsistencies, and quality gating are the critical engineering challenges.

→ *Aligned with [DIR-DI-001-v1.0 §3](Delta/01_Strategy/DIR-DI-001-v1.0.md).*

### 2.2 Proposed Solution

A **Quality-Aware Observational Engine** that:
- Selects the single best satellite scene per weekly window using a deterministic sensor hierarchy
- Applies rigorous cloud masking and a hard quality gate (≥20% valid pixels)
- Harmonizes spectral bands across Sentinel-2 and Landsat before index calculation
- Ingest results directly into the contractor's PostGIS database with full quality metadata

→ *Aligned with [DIR-DI-001-v1.0 §2](Delta/01_Strategy/DIR-DI-001-v1.0.md).*

### 2.3 Value Proposition

Transparent "Observed Data" — what the satellite actually saw, with clear quality indicators. No temporal interpolation, no gap-filling, no manipulation. If the data is bad, the system says so rather than fabricating numbers.

---

## 3. Functional Requirements

### FR-01 — Deterministic Scene Selection

Select **one single best scene** per weekly window using this priority order:

| Priority | Sensor | Condition |
| :--- | :--- | :--- |
| 1 | Sentinel-2 (most recent) | Valid pixel ratio ≥ 0.6 |
| 2 | Sentinel-2 (most recent) | Valid pixel ratio ≥ 0.2 |
| 3 | Landsat 8/9 (most recent) | Valid pixel ratio ≥ 0.2 |
| — | **SKIP** | No scene meets ≥ 0.2 threshold |

### FR-02 — Cloud Masking Pipeline

Two-layer masking, applied in order:

1. **Cloud Score+** (primary) — threshold `cs_cdf > 0.60`
2. **SCL / QA_PIXEL** (secondary safety net) — catches residual cloud/cloud-shadow pixels

### FR-03 — Hard Quality Gate

If `valid_pixel_ratio < 0.2` (20%) on a per-scene basis against total estate geometry, the system must **abort ingestion** (SKIP) for that scene to prevent garbage data from entering the database.

### FR-04 — Spectral Harmonization (Bands Only)

Apply Roy et al. (2016) normalization coefficients to **Reflectance Bands only** (Red, NIR) before index calculation. This applies to all indices: NDVI, EVI, SAVI, GNDVI, and NDRE. Never apply harmonization to final index values — doing so introduces spectral bias.

*(Audit fix P1: scope now explicitly covers all five indices, not just NDVI.)*

### FR-05 — Vegetation Index Calculation

| Index | Sentinel-2 | Landsat 8/9 |
| :--- | :---: | :---: |
| NDVI | ✓ | ✓ |
| EVI | ✓ | ✓ |
| SAVI | ✓ | ✓ |
| GNDVI | ✓ | ✓ |
| NDRE | ✓ | `NULL` (explicit) |

Landsat scenes in the 0.2–0.6 valid pixel range are flagged `low_quality=TRUE`. The `ndre` column must be explicitly set to `NULL` for Landsat rows.

### FR-06 — Async Reliability & Retry

Each GEE export is split into sub-chunks of 2,000 polygons. For each sub-chunk export (`ee.batch.Export.table.toDrive`, `tileScale: 16`): retry automatically **up to 3 times** on `FAILED` status before escalating to a persistent failure notification.

*(Audit fix P2: retry/failure handling now explicitly defined.)*

### FR-07 — Partial Success & Failure Reporting

If one or more sub-chunks fail persistently after 3 retries:
- Successfully processed chunks are ingested normally (partial success)
- Failed chunks are logged in the `alerts` table with chunk identification
- The run completes; no full-run rollback

---

## 4. Architecture & Logic Flow

### 4.1 System Architecture

```
┌─────────────────────────────┐      ┌──────────────────────────────┐
│   Contractor Server          │      │   CanopySense Cloud (GCP)     │
│                              │      │                              │
│  patcher_local.py  ──HTTPS──▶│──────│▶ patcher_cloud (Cloud Func)  │
│                              │      │   │                          │
│  PostGIS ◀──write back───────│◀─────│   ├─ GEE Engine              │
│  (satellite_data,            │      │   │  (scene_select, mask,    │
│   patcher_run_log,           │      │   │   harmonize, calculate,  │
│   alerts)                    │      │   │   export)                │
│                              │      │   │                          │
│  cron / upload trigger       │      │   ├─ Secret Manager          │
│                              │      │   │  (API key registry)      │
└─────────────────────────────┘      └──────────────────────────────┘
```

**Key architectural decisions:**
- **Option B (blocks in request body)**: Contractor sends block geometries as GeoJSON in the request. Cloud Function has zero outbound DB connections — no internet-exposed contractor database required.
- **Thin client / thick server**: All processing intelligence lives in the Cloud Function. The contractor's `patcher_local.py` is a stable, deploy-once script.
- **Afdeling-level batching**: Scheduled runs group blocks by afdeling; one Cloud Function call per batch. Failure isolation at the afdeling level.
- **Generic Write Routing (v0.10+)**: Cloud Function returns a `writes` array keyed by table name. Patcher-Local routes inserts generically — new cloud-side tables require zero contractor-side code changes.

### 4.2 Weekly Execution Flow

```
Trigger (Mon 02:00 AM)
    │
    ▼
Deterministic Scene Selection
    ├── Ratio ≥ 0.2 → Continue
    └── Ratio < 0.2 → SKIP + Alert "No Reliable Data"
    │
    ▼
Pre-processing (Bands Only)
    ├── Cloud Score+ masking (cs_cdf > 0.60)
    ├── SCL/QA_PIXEL secondary mask
    └── Roy et al. (2016) harmonization on Red & NIR
    │
    ▼
Index Calculation (5 indices)
    │
    ▼
Sub-chunking (2,000 polygons per chunk)
    │
    ▼
Async Export with Retry (max 3x per sub-chunk)
    ├── Success → Batch Ingest to PostGIS
    └── Persistent Fail → Partial Success Alert
```

### 4.3 Trigger Modes

| Mode | Trigger | Scope |
| :--- | :--- | :--- |
| **Scheduled** | Cron (weekly/daily) | All blocks, batched by afdeling |
| **Upload** | `patcher_local.py --block-id N` | Single block, immediate |

---

## 5. Technical Constraints

| ID | Constraint |
| :--- | :--- |
| TC-01 | Hard quality gate (0.2 / 20%) applies **per-scene** against total estate geometry |
| TC-02 | Persistent sub-chunk failure → partial success reporting + `alerts` table entry |
| TC-03 | No Carry Forward — empty weeks display as empty with a clear reason (cloud cover), never backfilled from prior weeks |
| TC-04 | Patcher-Local must be deploy-once stable; cloud-side changes must not require contractor updates |
| TC-05 | Cloud Function max instances = 1 (process-global state; single-instance handles current load) |
| TC-06 | `patcher_run_log` table tracks per-batch status across runs; next run only retries what failed |
| TC-07 | IN_PROGRESS guard prevents two simultaneous scheduled runs on the same afdeling |
| TC-08 | Exponential backoff on transient failures: 30s → 60s → 120s |
| TC-09 | Circuit breaker: 3 consecutive 429 responses → 5-minute pause |

---

## 6. Implementation Roadmap

| Phase | Task | Output | Status |
| :--- | :--- | :--- | :---: |
| **M1: Core Logic** | Cloud Score+ masking, Roy et al. harmonization, Quality Gate | GEE Modules (`core_engine/`) | ✅ Complete (WO-001 v0.4) |
| **M2: Async Engine** | Sub-chunking (2,000), Async Retry (3x), exponential backoff | Optimized Aggregator | ✅ Complete (WO-002 v0.5) |
| **M3: DB Integration** | Batch ingestion, NDRE NULL handling, `satellite_data` schema | PostGIS integration | ✅ Complete (WO-003 v0.10) |
| **M4: Resilience** | Partial success alerts, circuit breaker, persistent failure handling | `alerts` pipeline | ✅ Complete (WO-003 v0.10) |
| **M5: Deployment** | Two-Patcher system, Secret Manager, API key auth, Docker test infra | Cloud deployment | ✅ Complete (WO-003 v0.10b) |

---

## 7. Risk Register

| Risk | Severity | Mitigation | Status |
| :--- | :--- | :--- | :---: |
| Sentinel-2 unavailable for a given week | Medium | Landsat fallback; if both fail, SKIP + alert | Mitigated |
| Cloud Score+ insufficient for tropical cloud cover | Medium | SCL/QA_PIXEL secondary safety net | Mitigated |
| GEE export quota exceeded | Low | Sub-chunking + retry logic reduces per-request load | Mitigated |
| Single Cloud Function instance bottleneck | Low | Current load (weekly runs + single-block uploads) fits comfortably; documented as technical debt for future refactor | Accepted |
| `patcher_run_log` drift (contractor changes block list between runs) | Low | Batch fingerprint tracking detects changes; logs warning + treats as new batch | Mitigated |

---

## 8. Audit Trail

All audit findings from the legacy ecosystem have been addressed:

| Finding | Source | Resolution |
| :--- | :--- | :--- |
| Harmonization scope for EVI/SAVI/GNDVI not explicit | GPT-AUD-TPR-001 §12 (P1) | Resolved — FR-04 now explicitly covers all five indices |
| Async batch retry/failure handling not defined | GPT-AUD-TPR-001 §12 (P2) | Resolved — FR-06 defines 3x retry per sub-chunk |
| NDRE Sentinel-only handling needs developer confirmation | GPT-AUD-TPR-001 §12 (P3) | Resolved — FR-05 defines explicit NULL for Landsat |
| Low-quality flag for Landsat fallback unclear | GPT-AUD-TPR-001 §12 (P3) | Resolved — FR-05 defines `low_quality=TRUE` for 0.2–0.6 range |

**Audit Verdict: PASS WITH FIXES** — all fixes incorporated into this STRAT.

---

## 9. SSoT References

| Concern | Source |
| :--- | :--- |
| Director's Intent | `Delta/01_Strategy/DIR-DI-001-v1.0.md` |
| Project Strategy | This document |
| Database Schema | `Delta/05_References/Canopy_Sense_Rencana_Teknis_Final.md` |
| Implementation Code | `03_Build/core_engine/`, `03_Build/deploy/` |
| Test Infrastructure | `04_Test/` |

---

## 10. Version History

| Version | Date | Author | Changes |
| :--- | :--- | :--- | :--- |
| v1.0 | 2026-05-14 | GMN (DeepSeek) | Consolidated legacy PRD v0.3 + FLOW v0.3 + PROJ v1.0 + audit fixes into unified v2.0 STRAT |

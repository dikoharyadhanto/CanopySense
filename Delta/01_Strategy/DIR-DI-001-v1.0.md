# DIR-DI-001-v1.0 — Director's Intent

## 1. Metadata

| Field             | Value                  |
|:----------------- |:---------------------- |
| **Project ID**    | 001                    |
| **Document Type** | Director's Intent (DI) |
| **Version**       | v1.0                   |
| **Status**        | Active                 |
| **Director**      | Diko Hary Adhanto      |
| **Date**          | 2026-05-14             |

---

## 2. Strategic Vision

CanopySense is a **satellite-based vegetation monitoring system for oil palm plantations** — a commercial B2B product that automates the extraction of vegetation health indices from Google Earth Engine and delivers them directly into the contractor's own PostGIS database.

The vision: plantation managers should never need to hire field surveyors or buy commercial satellite subscriptions to get reliable, weekly vegetation data. Public satellite imagery (Sentinel-2, Landsat) is free — the missing piece is the infrastructure to turn that raw imagery into trustworthy per-block statistics. CanopySense fills that gap.

---

## 3. Problem Statement

Plantation managers need regular vegetation health data to make decisions about replanting, fertilizer timing, and block prioritization. Traditional methods — field surveyors, commercial satellite subscriptions — are expensive and don't scale.

The core technical problem: satellite imagery is publicly available, but transforming raw pixels into useful per-block indices requires cloud masking, cross-sensor band harmonization, quality gating, and batch ingestion infrastructure that most plantation operators lack in-house.

---

## 4. Target Users

| User              | Role                                                          | Interaction                                                          |
|:----------------- |:------------------------------------------------------------- |:-------------------------------------------------------------------- |
| **Contractors**   | Plantation companies running CanopySense on their own servers | Never see processing details; only consume results in their database |
| **Administrator** | CanopySense team                                              | Manages API keys, monitors Cloud Function, updates processing engine |

---

## 5. Success Metrics

- Automated weekly satellite data ingestion with zero manual steps from the contractor
- Multi-sensor support: Sentinel-2 as primary, Landsat 8/9 as fallback
- Processed vegetation indices stored in the contractor's own database (contractor owns their data)
- System resilience: partial failures must not lose the full run; retry intelligence built in
- Thin client / thick server: contractor script deployed once, never needing updates as the cloud engine evolves
- Quality gate integrity: low-quality scenes (valid pixel ratio < 20%) are skipped cleanly — no garbage data enters the database

---

## 6. Business Model

Commercial B2B: CanopySense provides the processing infrastructure; contractors pay for access. The architecture deliberately minimizes ongoing support burden. Once a contractor is onboarded, the admin's role is limited to key management and monitoring — not hand-holding.

---

## 7. Strategic Constraints

- **Data ownership**: Contractors own their data. The system writes to their database; CanopySense has no access to contractor data post-ingestion.
- **Deterministic results**: The same input must produce the same output. No ML-based gap-filling or temporal interpolation that masks data quality issues.
- **Operational isolation**: The Cloud Function has zero outbound database connections. All block geometry comes from the contractor's request body.
- **Deploy-once client**: The Patcher-Local script on the contractor's side must be stable — cloud-side improvements must not require contractor-side updates.

---

## 8. Version History

| Version | Date       | Author   | Changes                                                       |
|:------- |:---------- |:-------- |:------------------------------------------------------------- |
| v1.0    | 2026-05-14 | Director | Initial Director's Intent — migrated from legacy DOC_002_v1.0 |

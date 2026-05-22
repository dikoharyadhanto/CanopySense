---
name: ANT-STR-003-v0.6
project: Canopy Sense
status: OBSOLETE
version: 0.6
obsolete_date: 2026-04-20
superseded_by: ANT-STR-003-v0.7
obsolete_reason: Test plan for Cloud Run/Docker architecture which was replaced by Two-Patcher design. Do not use this document.
---

> [!WARNING]
> **OBSOLETE — DO NOT USE.** This Test Plan has been superseded by **ANT-STR-003-v0.7**.
> Reason: Paired with ANT-WO-003-v0.6 (Cloud Run architecture) which was replaced before implementation.
> Refer to: `ANT-STR-003-v0.7.md`

# ANT-STR-003-v0.6 (Test Plan - Cloud Run Deployment) — OBSOLETE

## 1. Acceptance Rules

- The core Earth Engine algorithm scripts must be entirely sealed within the Dockerized HTTP microservice.
- The external developer's trigger script must successfully invoke the pipeline purely over HTTP.

## 2. Testing Execution (Phases)

### Phase A: Source Code Audit
* **Action:** Inspect the newly refactored `engine_launcher.py` intended for the external team.
* **Pass Criteria:** It contains only standard HTTP request libraries (`requests` or `urllib`) and basic logging. It absolutely does not import `geopandas`, `ee`, or `core_engine`.

### Phase B: Local Container Validation
* **Action:** Build and run the `Dockerfile` locally using Docker Desktop or standard terminal logic.
* **Pass Criteria:** The container exposes the Flask/FastAPI web server cleanly on a local port (e.g., 8080) and does not immediately crash.

### Phase C: API Execution Test
* **Action:** Run the `engine_launcher.py` trigger script to send the POST request to the local container.
* **Pass Criteria:**
  1. The container correctly intercepts the authenticated request.
  2. Container terminal logs clearly confirm the Earth Engine extraction loop initialized and inserted values into PostGIS.

## 3. Observations & Output

**(This section to be updated during/after Lead Developer Execution)**

* `[ ]` Trigger Script Audit pass: pending
* `[ ]` Docker container build success: pending
* `[ ]` API endpoint remote execution verified: pending
* `[ ]` End-to-End ingestion success via Trigger verified: pending

---
**ANT (Technical Foreman) Sign-off**: 2026-04-11 (v0.6)

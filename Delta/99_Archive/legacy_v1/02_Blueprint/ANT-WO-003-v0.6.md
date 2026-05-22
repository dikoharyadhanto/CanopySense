---
name: ANT-WO-003-v0.6
project: Canopy Sense
phase: Tahap II (Deployment): Google Cloud Run Microservice Migration
status: OBSOLETE
obsolete_date: 2026-04-20
superseded_by: ANT-WO-003-v0.7
obsolete_reason: Architecture replaced by Two-Patcher design (Patcher-Local + Patcher-Cloud). Docker/Cloud Run containerization approach was not implemented. Do not use this document.
ppx_validation: PASS (Secure, Serverless Architecture)
ppx_validation_date: 2026-04-11
---

> [!WARNING]
> **OBSOLETE — DO NOT USE.** This Work Order has been superseded by **ANT-WO-003-v0.7**.
> Reason: Architecture was redesigned to a Two-Patcher system (Patcher-Local + Patcher-Cloud with per-contractor API key control). The Cloud Run / Docker approach defined here was never implemented.
> Refer to: `ANT-WO-003-v0.7.md`

# ANT-WO-003-v0.6 (Work Order) — OBSOLETE

> [!IMPORTANT]
> **Lead Developer (Claude Code)**: You are granted "Freedom of Method" within the constraints of this Work Order.
> Goal: Migrate the existing `core_engine` and PostGIS ingestion logic into a serverless Google Cloud Run architecture (Flask/FastAPI container). Create a simplified, external `engine_launcher.py` acting strictly as an HTTP trigger to protect intellectual property.

## 1. Technical Tasks (Scope)

1. **Cloud Run Containerization (`Dockerfile`)**:
   - Create a `Dockerfile` at the project root to package the Python environment, `03_Build/core_engine`, and `03_Build/ingestion`.
   - Implement a lightweight web server (e.g., Flask or FastAPI) inside the container that listens for incoming HTTP POST requests to trigger the satellite extraction payload.

2. **Refactoring the Engine Entry Point**:
   - Instead of a local CLI execution, this internal endpoint must execute the weekly engine extraction when hit.
   - The engine must connect dynamically to the target WebApp PostgreSQL database via standard environmental variables (`DATABASE_URL`, `PGHOST`, etc.).

3. **External Trigger Script (`engine_launcher.py`)**:
   - Replace the external-facing `engine_launcher.py` with a simple 20-line HTTP trigger script.
   - It must issue an authenticated HTTP POST request (e.g., verifying a Bearer token) to the Cloud API endpoint.
   - It must absolutely contain *zero* Google Earth Engine logic, *zero* index calculation formulas, and *zero* proprietary IP.

## 2. Success Indicators

- [ ] Docker image cleanly packages core logic and prevents external source viewing.
- [ ] A functioning HTTP endpoint successfully boots up the `core_engine` pipeline internally.
- [ ] `engine_launcher.py` is safely distributable to external contractors containing only safe web request logic.
- [ ] The Cloud container execution smoothly writes results into the target PostGIS database.

## 3. Implementation Constraints

- **IP Protection**: Under no circumstances should the external `engine_launcher.py` import `ee` directly or contain algorithmic logic.
- **Security**: The trigger endpoint must require minimal HTTP authentication to prevent unauthorized database backfills.

---
**ANT (Technical Foreman) Sign-off**: 2026-04-11 (v0.6)

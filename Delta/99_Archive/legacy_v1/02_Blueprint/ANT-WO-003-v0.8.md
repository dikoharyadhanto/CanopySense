---
name: ANT-WO-003-v0.8
project: Canopy Sense
phase: Tahap III (Post-Integration): Revocation Flow Verification & Operational Readiness
status: PENDING — Planned for execution after contractor PostGIS server is ready
version: 0.8
created_date: 2026-04-20
prerequisite: ANT-WO-003-v0.7 COMPLETE — Level 2 hybrid simulation PASSED
---

# ANT-WO-003-v0.8 (Work Order)

> [!NOTE]
> **Status:** This Work Order is **PENDING**. It is not yet assigned to CDC.
> Execution is planned after the contractor completes their PostGIS server setup.
> All core implementation from v0.7 is already in place — v0.8 covers **verification only** (no new code required).

---

## Context

v0.7 implementation and Level 2 hybrid simulation are COMPLETE:
- Two-Patcher architecture deployed and operational
- Real GCF (`patcher_cloud`) live at `asia-southeast2-canopysense.cloudfunctions.net`
- Level 1 local simulation: PASSED (5 rows inserted to local PostGIS)
- Level 2 hybrid simulation: PASSED (real GCF → GEE → bore tunnel → local PostGIS, 5 rows returned)

Two verification tasks from ANT-STR-003-v0.7 were deferred:
- **Phase C** — API key revocation flow (empirical latency measurement)
- **Phase E** — GUIDANCE.md operational review

These tasks require no code changes. They are purely operational/verification steps.

---

## 1. Technical Tasks (Scope)

### 1.1 Task C — API Key Revocation Flow Verification
**Owner:** CDC (execution), ANT (sign-off)
**No code changes required.**

**Steps:**
1. Confirm `CONTRACTOR_TEST` is `ACTIVE` in `canopysense-api-key-registry` Secret Manager
2. Run `patcher_local.py` → verify successful 200 response (baseline)
3. Edit `canopysense-api-key-registry` in Secret Manager: set `CONTRACTOR_TEST` status to `REVOKED`, add `revoked_date`
4. Immediately re-run `patcher_local.py` (within 30 seconds)
5. Record the actual time between Secret Manager edit and 403 response
6. Verify Cloud Logging shows audit entry: `status=REJECTED`, `detail=Key revoked`
7. Restore `CONTRACTOR_TEST` to `ACTIVE` after test

**Expected outcome:**
- Step 4 returns `403 Forbidden: API Key revoked (issued ..., revoked ...)`
- Revocation latency measured and logged (target: <30 seconds)
- Cloud Logging audit trail present

**Deliverable:** Observations section of ANT-STR-003-v0.8 updated with actual measured latency.

---

### 1.2 Task E — GUIDANCE.md Operational Review
**Owner:** CDC (facilitates), ANT (executes review)
**No code changes required (unless GUIDANCE.md gaps are found).**

**Steps:**
1. ANT reads `03_Build/GUIDANCE.md` without CDC assistance
2. Follow Section A (Setup) to simulate onboarding a new contractor
3. Follow Section C (Troubleshooting) for 2 simulated error scenarios:
   - Scenario 1: Cloud Function returns 403 (invalid key)
   - Scenario 2: PostGIS connection failure (wrong PGHOST)
4. Verify glossary covers all terms used in the document
5. Verify all checklists are copy-paste safe (exact commands, no placeholder ambiguity)
6. Verify at least 1 worked example per section (A–F)
7. If any gap found → CDC updates GUIDANCE.md → re-review

**Expected outcome:**
- GUIDANCE.md enables self-service deployment and troubleshooting without CDC support
- Any gaps corrected and re-verified before sign-off

**Deliverable:** ANT-STR-003-v0.8 Phase E observations updated with specific findings.

---

## 2. Success Indicators

| Task | Indicator | Target |
|------|-----------|--------|
| C — Revocation | 403 returned after key set to REVOKED | Within 30 seconds |
| C — Revocation | No code redeployment needed | Zero deployments |
| C — Revocation | Cloud Logging shows REJECTED audit entry | Present |
| C — Revocation | Revoked key restored to ACTIVE after test | Confirmed |
| E — GUIDANCE.md | Self-service setup achievable | <1 hour without CDC |
| E — GUIDANCE.md | All 6 sections pass review | 100% |
| E — GUIDANCE.md | Glossary complete | All terms defined |
| E — GUIDANCE.md | Worked example per section | ≥1 per section |

---

## 3. Implementation Constraints

- **No core engine changes** — `engine_launcher.py`, `core_engine/`, `ingestion/` are frozen
- **No Patcher-Local or Patcher-Cloud code changes** — unless a bug is found during Task E
- **GUIDANCE.md** — may be updated if Task E finds gaps (minor edits only)
- **Secret Manager** — Task C requires write access to `canopysense-api-key-registry`

---

## 4. Deliverables Checklist

| Deliverable | Type | Owner | Status |
|------------|------|-------|--------|
| ANT-STR-003-v0.8 Phase C observations filled | Test result | CDC | Pending |
| ANT-STR-003-v0.8 Phase E observations filled | Test result | CDC | Pending |
| GUIDANCE.md updated (if gaps found in Task E) | Doc update | CDC | Conditional |
| ANT-WO-003-v0.8 status updated to COMPLETE | Sign-off | ANT | Pending |

---

## 5. Notes

1. **No bore tunnel needed for Task C** — the revocation test only needs the contractor's `.env` and a running `patcher_local.py` call. The contractor's PostGIS can be their live server (or any reachable DB) by the time this WO is executed.
2. **Task E timing** — GUIDANCE.md review should be done when a real contractor or operations staff member is available to attempt self-service setup. Doing it without that person reduces the test validity.
3. **Latency measurement** — use a stopwatch/terminal timestamp between `gcloud secrets versions add` and `patcher_local.py` returning 403. Record exact seconds in STR observations.

---

**ANT (Technical Foreman) Sign-off**: PENDING

**Trigger to activate this WO:**
- Contractor PostGIS server is ready and reachable
- OR ANT decides to run the verification independently of contractor readiness (Task C can run against local PostGIS; Task E has no PostGIS dependency)

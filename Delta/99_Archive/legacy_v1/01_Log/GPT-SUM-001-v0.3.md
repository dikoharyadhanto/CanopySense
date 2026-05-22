# DPS-SUM-GMN-PROJ-001-v1.2

## Metadata
| Field | Value |
| :--- | :--- |
| **Topic** | Canopy Sense Core Engine Stage‑1 – Consolidated Audit of Revised PROJ, FLOW, PRD |
| **Models** | ChatGPT (audit mode) |
| **Context** | Following the benchmark validations (Perplexity) and initial fixes, the user requested a final cross‑document audit of PROJ v1.0 (perbaikan), FLOW v0.2, and PRD v0.2 to identify remaining ambiguities before implementation. |

---

## Key Decisions & Agreements
- **All three documents have improved significantly** – major conflicts (sensor policy, cloud masking precedence, quality gate) are resolved.
- **Deterministic logic** is now present in PRD and FLOW: Sentinel‑2 priority → Landsat fallback → hard quality gate (<0.2 valid pixels = skip).
- **Hard quality gate** (`valid_pixel_ratio < 0.2` → skip ingestion) is explicitly defined, preventing ingestion of noisy data.
- **Cloud masking precedence** is clear: Cloud Score+ primary, SCL/QA_PIXEL secondary.
- **Cross‑sensor harmonisation** uses Roy et al. (2016) c‑factor method to align NDVI; NDRE is Sentinel‑2 only.
- **Scaling strategy**: Sub‑chunking (max 2,000 polygons) + `ee.batch.Export` + async processing → GEE quotas and memory risks mitigated.
- **UX policy**: No carry‑forward; display “No reliable data” alerts to preserve trust.

---

## Action Items & Assignments
| Task | Owner | Status |
| :--- | :--- | :--- |
| **PROJ:** Define “deterministic” explicitly (e.g., “single scene per window chosen by highest valid_pixel_ratio after sensor hierarchy”) | Tech Lead | Pending |
| **PROJ:** Restrict harmonisation scope to reflectance bands only; indices (EVI, SAVI, GNDVI) must not be harmonised | System Architect | Pending |
| **PROJ:** Clarify whether skip <20% applies per block or per scene (recommend: per scene) | Product Owner | Pending |
| **FLOW:** Add explicit retry / failure handling for async exports (e.g., retry failed chunks up to 3 times, alert if persistent) | Backend Engineer | Pending |
| **FLOW:** Clarify harmonisation scope (bands only) in the step‑by‑step text, not only in diagram | Document Owner | Pending |
| **FLOW:** Define low‑quality flag behaviour for Landsat fallback (0.2–0.6 valid pixels) | Tech Lead | Pending |
| **PRD:** Specify harmonisation scope explicitly (bands only) to avoid misinterpretation | Document Owner | Pending |
| **PRD:** Add low‑quality flag handling for Landsat fallback (consistency with FLOW) | Tech Lead | Pending |
| **PRD:** Include per‑block NDRE NULL flagging for transparency | Product Owner | Pending |
| **All docs:** Add explicit retry/partial success handling for async export chunks | System Architect | Pending |

---

## Open Questions / Blockers
- **Deterministic definition** in PROJ: still ambiguous; must be a single sentence to remove interpretation.
- **Harmonisation scope**: All three documents refer to Roy et al. but do not explicitly state that it applies only to reflectance bands, not to derived indices. If engineers harmonise indices, bias will be introduced.
- **Skip <20% granularity**: PROJ mentions “skip <20% valid pixel” without specifying per‑block or per‑scene. This affects whether a week produces partial or zero data.
- **Async export failure handling**: FLOW and PRD lack retry logic and partial success alerts; a single failed chunk could break deterministic pipeline.
- **Landsat fallback low‑quality flag**: FLOW defines threshold 0.2–0.6 as low quality, but PRD does not explicitly mention flagging for Landsat; downstream consistency needed.
- **NDRE NULL per‑block**: PRD mentions NDRE NULL but not whether it is recorded per block; transparency requires flagging.

---

## Critical Insights & Risks
- **Risk of misinterpretation**: Without explicit deterministic definition, developers may implement scene selection inconsistently (latest vs. best quality).
- **Harmonisation over‑application**: If engineers harmonise all indices, EVI/SAVI/GNDVI values will be inaccurate, breaking downstream analytics.
- **Partial data risk**: If skip <20% is applied per block, some blocks may be missing while others have data, causing fragmented time series without clear alerting.
- **Export failure**: Without retry, a single chunk failure could result in incomplete weekly data without notification, undermining reliability.
- **UX transparency**: Missing per‑block NDRE NULL flags could confuse users when NDRE values are absent.

---

## Next Steps
1. **Address all remaining clarifications** listed in Action Items (estimated 2–3 hours of updates).
2. **Re‑align PROJ, FLOW, and PRD** to ensure identical wording on:
   - Deterministic scene selection rule
   - Harmonisation scope (bands only)
   - Skip <20% granularity (per scene)
   - Async export retry logic
   - Landsat low‑quality flagging
3. **Perform a final cross‑document consistency check** after updates.
4. **Proceed to Stage‑1 implementation** – the core architecture is now production‑ready.

---

## Consolidated Verdict
| Category | Status |
| :--- | :--- |
| Architecture clarity | ✅ Strong |
| Determinism | ⚠️ Minor clarification needed |
| Sensor logic | ✅ Clear |
| Scaling & GEE integration | ✅ Good |
| Error handling | ⚠️ Retry logic missing |
| Documentation completeness | ⚠️ Minor gaps |
| Implementation readiness | **Ready after minor clarifications** |

**Summary**: The revised documents (PROJ v1.0 perbaikan, FLOW v0.2, PRD v0.2) have resolved all major conflicts. With the remaining minor clarifications (deterministic definition, harmonisation scope, skip granularity, async export retry, Landsat low‑quality flag), the pipeline is ready for Stage‑1 implementation. No further blocking issues remain.
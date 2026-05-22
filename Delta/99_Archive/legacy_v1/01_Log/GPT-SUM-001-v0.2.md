## Metadata
| Field | Value |
| :--- | :--- |
| **Topic** | GMN Core Engine Stage-1 – Cross-Document Audit (PROJ, FLOW, PRD) |
| **Models** | Human-Proxy Audit (Brutal Mode) |
| **Context** | Final consistency check before Stage-1 implementation. Three documents (PRD, PROJ, FLOW) were audited for operational clarity, technical consistency, and real-world robustness. |

---

## Key Decisions & Agreements
- **FINAL VERDICT: ❌ FAIL** – Implementation is **blocked** due to fatal cross-document conflicts.
- **Fatal conflicts identified** in:
  - Sensor policy (merge vs. fallback vs. dual ingestion)
  - Cloud masking precedence (CloudScore+ vs. SCL vs. QA_PIXEL)
  - Adaptive threshold logic (undefined trigger)
  - Edge case handling (no scene vs. all clouds)
- **Product contradiction**: PRD promises stable data, but architecture allows low-quality / noisy data to be ingested.
- **Most dangerous design**: PRD mandates ingesting cloud-covered scenes → generates wrong data → destroys user trust.

---

## Action Items & Assignments
| Task | Owner | Status |
| :--- | :--- | :--- |
| Define **Option B** formally (single best scene, no composite, no smoothing) | Product / Tech Lead | Pending |
| Define **sensor priority rule** (Sentinel‑2 primary, Landsat fallback only) | System Architect | Pending |
| Define **hard quality gate** (e.g., `valid_pixel_ratio < 0.2` → skip ingestion) | Tech Lead | Pending |
| Define **cloud mask precedence** (unified rule across CloudScore+, SCL, QA_PIXEL) | System Architect | Pending |
| Remove **adaptive threshold** (use single 0.6 threshold) | Product Owner | Pending |
| Define **NDRE fallback** for Landsat-only weeks (NULL / skip / log) | Tech Lead | Pending |
| Add **GEE scalability safeguards** (tileScale, block batching, maxPixels) | Engineer | Pending |
| Update PROJ, FLOW, PRD to align on all above rules | Document Owner | Pending |

---

## Open Questions / Blockers
- **Option B**: No formal definition exists; interpretation varies across documents.
- **Sensor policy**: Contradiction between PRD (“no cross-sensor merge”) and FLOW (“loop both sensors”).
- **Edge case**: No deterministic rule for `valid_pixel_ratio = 0` (is it “no scene” or “low quality scene”?).
- **Adaptive threshold**: No automated way to detect “rainy season”; rule cannot be implemented as written.
- **NDRE**: Not defined for Landsat-only weeks (data gap in time series).

---

## Critical Insights & Risks
- **Architecture smell**: All three documents are designed for ideal conditions, not real-world tropical cloud cover.
- **UX risk**: Ingesting low-quality data is **worse** than ingesting no data; users will lose trust.
- **GEE risk**: `reduceRegions` without batching or `tileScale` will cause timeouts / memory failures.
- **Data inconsistency risk**: Time series will show artificial jumps due to:
  - Switching sensors without normalization
  - Selecting “latest” instead of “best quality”
  - Mixing cloud-masked vs. non-masked pixels
- **Implementation risk**: Engineers will make conflicting assumptions → pipeline non-deterministic.

---

## Next Steps
1. **Do NOT start coding** until all critical conflicts are resolved.
2. **Update PRD, PROJ, FLOW** with the 6 required fixes (Action Items above).
3. **Re-audit** after documents are revised to ensure cross-document consistency.
4. Only then proceed to Stage‑1 implementation planning.
# DPS-SUM-GMN-PROJ-001-v1.1

## Metadata
| Field | Value |
| :--- | :--- |
| **Topic** | Canopy Sense Core Engine Stage-1 – Pre‑Approval Benchmark Checks via Perplexity |
| **Models** | Perplexity (external research) |
| **Context** | User requested Perplexity to validate technical assumptions (threshold, GEE quotas, cloud masking, cross‑sensor normalisation, backend architecture, UX for no‑data, GEE scaling) before finalising PRD/FLOW/PROJ documents. This summary captures the benchmark results and recommendations. |

---

## Key Decisions & Agreements
- **Threshold (valid pixel ratio):** 60% is supported by industry standards (tropical regions often use 50‑60% good‑quality pixels in composites). Recommend **adaptive threshold** (e.g., 50% in rainy season) based on estate‑specific historical coverage, but keep 60% as baseline.
- **GEE concurrent quota:** Standard projects have **40 concurrent requests**; using `ee.FeatureCollection.reduceRegions()` in batch is safer than parallel loops. Must chunk polygons (1,000‑2,000 per batch) to avoid memory limits.
- **Cloud masking:** SCL + QA_PIXEL are insufficient for humid tropics due to commission errors. **Cloud Score+** (with `cs_cdf > 0.6`) is strongly recommended for higher accuracy in tropical conditions.
- **Cross‑sensor normalisation:** Use **Roy et al. (2016) c‑factor method** to harmonise Sentinel‑2 and Landsat NDVI. Implementation in GEE is not compute‑intensive.
- **Backend orchestration:** For weekly batch processing of ~5000 polygons, prefer **`ee.batch.Export`** (task‑based) over synchronous `computePixels`. Use FastAPI + Celery + secrets manager (GCP Secret Manager) for secure service account authentication in production.
- **UX for no‑data:** Leading Ag‑Tech platforms (EOSDA, Planet) **do not carry forward** old values; they display “Low Confidence / No Data” with tooltips and historical references. Hard quality gate with clear messaging is better than imputing data.
- **GEE scaling:** `reduceRegions` memory limit typically occurs above 5,000‑10,000 polygons. **Sub‑chunk per estate** (1,000‑2,000 polygons) is recommended to avoid “User memory limit exceeded”.

---

## Action Items & Assignments
| Task | Owner | Status |
| :--- | :--- | :--- |
| Update PRD/FLOW/PROJ to incorporate Cloud Score+ as primary cloud mask (with SCL/QA_PIXEL fallback) | System Architect | Pending |
| Define adaptive threshold rule (60% baseline, 50% during rainy season with clear season detection) | Product Owner | Pending |
| Implement c‑factor normalisation (Roy et al. 2016) for cross‑sensor NDVI alignment | Engineer | Pending |
| Redesign backend: FastAPI + Celery + `ee.batch.Export` for zonal stats | Backend Engineer | Pending |
| Configure service account authentication with secrets manager (GCP Secret Manager / K8s) | DevOps | Pending |
| Implement polygon chunking (1,000‑2,000 per batch) for `reduceRegions` | Engineer | Pending |
| Define UX strategy for no‑data: display “No data (cloud cover > threshold)” with tooltip, not carry forward | Product / Frontend | Pending |
| Re‑audit all documents after updates to ensure consistency | Document Owner | Pending |

---

## Open Questions / Blockers
- **Adaptive threshold trigger:** How will the system automatically detect “rainy season” per estate? Rainfall API? Monthly historical cloud cover?
- **Cloud Score+ integration:** Should it fully replace SCL/QA_PIXEL, or be combined (e.g., Cloud Score+ first, then mask with SCL for cirrus)? Precedence rule still undefined.
- **c‑factor coefficients:** Exact coefficients for tropical dense canopy (oil palm/rubber) need verification from literature or internal calibration.
- **Batch export monitoring:** How to handle failed exports (retry, alerting)? Not yet defined.
- **Service account permissions:** Exact IAM roles required for GEE + Cloud Storage need to be specified.

---

## Critical Insights & Risks
- **Risk of under‑masking:** Without Cloud Score+, thin clouds and haze in tropical conditions will produce noisy NDVI, destroying data trust.
- **GEE memory/timeout risk:** Using `reduceRegions` on 10,000+ polygons without chunking will cause crashes. The recommendation to chunk per estate (1,000‑2,000) is essential.
- **UX trust risk:** Carrying forward old NDVI values (as originally considered) would create misleading trends. Industry practice favours transparency with “no data” flags.
- **Cross‑sensor inconsistency:** Without spectral normalisation, time series will show artificial jumps when switching between Sentinel‑2 and Landsat. The c‑factor method mitigates this.
- **Backend architecture risk:** Using synchronous `computePixels` for large batch jobs would hit quota limits and block the API. `ee.batch.Export` is the safe, scalable choice.

---

## Next Steps
1. **Incorporate all benchmark recommendations** into PRD, PROJ, and FLOW documents (see Action Items).
2. **Define missing details** (adaptive threshold trigger, Cloud Score+ precedence, exact c‑factor coefficients, export monitoring).
3. **Re‑run cross‑document audit** to ensure consistency after updates.
4. **Proceed to Stage‑1 implementation** only after all critical items are resolved.
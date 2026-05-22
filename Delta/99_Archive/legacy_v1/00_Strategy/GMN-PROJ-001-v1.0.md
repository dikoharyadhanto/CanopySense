---

### 3. Dokumen PROJ (Roadmap)

```markdown
# GMN-PROJ-001-v1.0
> [!IMPORTANT]
> **Logic Dependencies**: Dokumen ini bergantung pada `GMN-PRD-001-v0.2` dan `GMN-FLOW-001-v0.2`.

## 1. Project Metadata
| Field | Value |
| :--- | :--- |
| **Project ID** | 001 |
| **Project Name** | Canopy Sense - Core Engine Stage 1 |
| **Version** | v1.0 |
| **Status** | Active (Audit Fixed) |
| **Architect** | Gemini (GMN) |

---

## 2. Executive Summary
> **Purpose & Value:** Membangun pipeline otomatisasi ekstraksi data satelit "Quality-Aware" yang mensinergikan GEE (untuk komputasi) dan PostGIS (untuk penyimpanan) guna menghasilkan indikator GCC yang konsisten dan jujur[cite: 2, 4, 6].

---

## 3. Strategic Goals
* **Primary Objective**: Pipeline ekstraksi otomatis mingguan yang skalabel dan deterministic[cite: 4].
* **Success Indicator 1**: Normalisasi antar-sensor (S2 & Landsat) berhasil diterapkan dengan koefisien Roy et al.
* **Success Indicator 2**: Sistem berhasil melakukan SKIP pada citra berkualitas rendah (<20% valid pixel) secara otomatis.
* **Success Indicator 3**: Integrasi database PostGIS yang efisien melalui metode *batch ingestion*[cite: 1, 105].

---

## 4. Core Constraints
* **Deterministic Rule**: Memilih citra tunggal terbaik per jendela waktu berdasarkan urutan prioritas sensor (S2 > Landsat) dan rasio piksel valid tertinggi.
* **Harmonization Scope**: Pembatasan normalisasi spektral hanya pada level **Reflectance Bands**, bukan pada produk indeks akhir.
* **Resilience Policy**: Implementasi mekanisme *retry* otomatis 3x pada *asynchronous pipeline* untuk menjamin kontinuitas data.

---

## 5. Implementation Roadmap (Milestones)
| Phase | Task | Responsible | Output |
| :--- | :--- | :--- | :--- |
| **M1: Core Logic** | Masking (Cloud Score+), Band Harmonization, & Quality Gate. | CDC | GEE Modules |
| **M2: Async Engine** | Sub-chunking (2k) & Async Retry Logic (3x). | CDC | Optimized Aggregator |
| **M3: DB Integration** | Batch Ingestion & NDRE NULL handling. | ANT | `satellite_data` Table |
| **M4: Resilience** | Partial Success Alerts & Persistent Failure Handling. | ANT | `alerts` Pipeline |

---

## 6. Single Source of Truth (SSoT) Location
* **Main Directory**: `001_Canopy_Sense/` 
* **Primary PRD**: `00_Strategy/GMN-PRD-001-v0.2.md` 
* **Logic Flow**: `00_Strategy/GMN-FLOW-001-v0.2.md`
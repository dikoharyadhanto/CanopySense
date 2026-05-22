# GMN-FLOW-001-v0.3
> [!IMPORTANT]
> **Logic Dependencies**: Memerlukan `GMN-PRD-001-v0.2` dan skema database `Canopy_Sense_Rencana_Teknis_Final.docx`.

## 1. Metadata
| Field | Value |
| :--- | :--- |
| **Project ID** | 001 |
| **Document Type** | Technical Logic Flow (FLOW) |
| **Version** | v0.3 |
| **Status** | Active (Audit Final Fixed) |
| **Lead Architect** | Gemini (GMN) |

---

## 2. Logic Overview
> **Scope:** Flow ini mendefinisikan urutan eksekusi asinkron mingguan menggunakan hierarki sensor (S2 > Landsat) untuk memastikan hanya data dengan kualitas terbaik yang masuk ke PostGIS.

---

## 3. Sequential Logic (Step-by-Step)

1. **Trigger**: Senin 02:00 AM (Window: 7 hari terakhir).
2. **Deterministic Selection**:
    - Query Sentinel-2. Jika `valid_pixel_ratio` $\ge 0.2$, pilih S2 (Utamakan yang $\ge 0.6$).
    - Jika S2 < 0.2, query Landsat. Jika Landsat $\ge 0.2$, pilih Landsat.
    - Jika keduanya < 0.2, **SKIP INGESTION** & kirim alert "No Reliable Data".
3. **Pre-processing (Bands Only)**:
    - Lakukan masking (Cloud Score+).
    - Terapkan koefisien Roy et al. (2016) pada band **Red** dan **NIR** saja sebelum hitung indeks.
4. **Index Calculation**: Hitung 5 indeks (NDVI, EVI, NDRE, SAVI, GNDVI) menggunakan band yang telah diharmonisasi.
5. **Async Export with Retry**:
    - Bagi blok menjadi *sub-chunks* (2.000 poligon).
    - Eksekusi `ee.batch.Export.table.toDrive()` (tileScale: 16).
    - **Monitor Task**: Jika status `FAILED`, lakukan **Retry otomatis (maks 3x)**.
6. **Ingestion**: Backend (FastAPI) melakukan *batch upsert* hasil ke PostGIS.

---

## 4. Visual Logic (Mermaid Diagram)

```mermaid
graph TD
    A[Trigger: Senin 02:00] --> B[Deterministic Scene Selection]
    B -- "Ratio >= 0.2" --> C[Harmonize RED & NIR Bands]
    B -- "Ratio < 0.2" --> D[Abort & Alert Alerts Table]
    C --> E[Calculate 5 Vegetation Indices]
    E --> F[Sub-chunking: 2k Polygons]
    F --> G{Async Export with 3x Retry}
    G -- Success --> H[Batch Ingest to PostGIS]
    G -- Persistent Fail --> I[Partial Success Alert]
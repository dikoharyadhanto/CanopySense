# GMN-PRD-001-v0.3
> [!IMPORTANT]
> **Logic Dependencies**: Memerlukan `GMN-PROJ-001-v1.0`, `GPT-AUD-TPR-001-v0.2` (Audit Pass), dan `Perplexity-Technical-Benchmark-2026`.

## 1. Metadata
| Field | Value |
| :--- | :--- |
| **Project ID** | 001 |
| **Document Type** | Strategic PRD (PRD) |
| **Version** | v0.3 |
| **Status** | Active (Audit Final Fixed) |
| **Lead Architect** | Gemini (GMN) |
---

## 2. Strategic Vision & Value
* **Problem Statement**: Manager perkebunan membutuhkan monitoring kanopi mingguan yang stabil. Data satelit mentah sering terganggu awan yang jika tidak difilter secara ketat akan merusak kepercayaan data.
* **Proposed Solution (Option B)**: Mengimplementasikan *Quality-aware Observational Engine* yang memilih satu citra terbaik per minggu berdasarkan hierarki sensor dan ambang batas kualitas yang rigid.
* **Value Proposition**: Menjamin transparansi melalui "Observed Data" (apa adanya) dengan indikator kualitas yang jelas tanpa manipulasi temporal.

---

## 3. Functional Requirements (Final Refinement)
* **[FR-01] Hierarki Sensor & Determinisme**: Memilih **satu citra tunggal terbaik** per minggu dengan urutan prioritas: 1. Sentinel-2 Terbaru (Ratio $\ge 0.6$), 2. Sentinel-2 Terbaru (Ratio $\ge 0.2$), 3. Landsat Terbaru (Ratio $\ge 0.2$). Jika tidak ada yang memenuhi $\ge 0.2$, sistem wajib **SKIP**.
* **[FR-02] Cloud Masking Precedence**: 
    1. **Cloud Score+** (Primary filter, threshold `cs_cdf > 0.60`).
    2. **SCL/QA_PIXEL** (Secondary filter sebagai safety net).
* **[FR-03] Hard Quality Gate**: Jika `valid_pixel_ratio < 0.2` (20%), sistem wajib membatalkan *ingestion* (SKIP) untuk mencegah masuknya data sampah.
* **[FR-04] Spectral Harmonization (Bands Only)**: Normalisasi Roy et al. (2016) hanya diterapkan pada **Reflectance Bands** (Red & NIR) sebelum kalkulasi indeks dilakukan. Dilarang menerapkan normalisasi langsung pada nilai indeks akhir untuk menghindari bias spektral.
* **[FR-05] Index Calculation**: Menghitung NDVI, EVI, SAVI, GNDVI untuk semua sensor; NDRE dihitung khusus Sentinel-2 (Landsat diisi `NULL`).
* **[FR-06] Async Reliability & Retry**: Sistem wajib mengimplementasikan **Retry Logic** otomatis (maksimal 3 kali) untuk setiap *sub-chunk* ekspor GEE yang gagal sebelum mengirimkan notifikasi kegagalan total.
* **[FR-07] Landsat & NDRE Handling**: Citra Landsat wajib ditandai `low_quality=TRUE` jika berada di rentang 0.2 - 0.6. Kolom `ndre` pada tabel `satellite_data` wajib diisi `NULL` secara eksplisit.

---

## 4. Technical Constraints & Edge Cases
* **Success Indicator**: Pipeline berjalan otomatis setiap Senin 02:00 AM.
* **No Reliable Data**: Jika S2 dan Landsat gagal melewati *Hard Quality Gate*, sistem mengirim notifikasi "No Reliable Data Available" dan tidak melakukan insert ke tabel `satellite_data`.
* **UX Policy**: Dilarang melakukan *Carry Forward* (mengulang data minggu lalu). Data kosong harus ditampilkan sebagai kosong dengan alasan yang jelas (Cloud Cover).
* **[TC-01] Hard Quality Gate Granularity**: Ambang batas 0.2 (20%) diterapkan pada level **per-scene** terhadap total geometri estate untuk menentukan kelayakan proses.
* **[TC-02] Failure Handling**: Jika terjadi kegagalan persisten pada salah satu *sub-chunk*, sistem melakukan *partial success reporting* dan mencatatnya pada tabel `alerts`.

---

## 5. Security & Governance
* **Data Handling**: Menjaga integritas tabel `satellite_data` sesuai skema PostGIS.
## Metadata
| Field | Value |
| :--- | :--- |
| **Topic** | Core Engine Tahap I – Ekstraksi Data, Cloud Masking, Rumus Indeks (Canopy Sense) |
| **Models** | ChatGPT |
| **Context** | Brainstorming desain workflow untuk engine pemrosesan citra satelit (Sentinel‑2 & Landsat) yang menghasilkan tabel `satellite_data` sesuai skema PostGIS. Diskusi membahas pilihan arsitektur, kebijakan pemilihan scene, penanganan awan, dan output per blok. |

---

## Key Decisions & Agreements

1. **Arsitektur Engine** – Menggunakan **Option B (Quality‑aware Observational)**  
   - Setiap minggu dihasilkan **1 nilai per sensor per blok**  
   - Memilih scene terbaru yang memenuhi **ambang kualitas** (valid pixel ratio ≥ threshold)  
   - Jika tidak ada scene memenuhi, tetap ambil scene terbaru dan beri *flag low quality*  
   - **Tidak ada composite temporal lintas tanggal**  
   - Output disimpan **versioned** (tidak menghapus data lama jika algoritma berubah)

2. **Sensor & Resolusi**  
   - Sentinel‑2 (10 m) dan Landsat 8/9 (30 m) diproses **independen**  
   - Semua indeks vegetasi (NDVI, EVI, NDRE, SAVI, GNDVI) dihitung; NDRE untuk Landsat diisi `null`

3. **Masking Awan & Bayangan**  
   - **Sentinel‑2** → SCL (Scene Classification Layer) menghapus cloud, shadow, cirrus  
   - **Landsat** → QA_PIXEL menghapus cloud dan shadow

4. **Pemilihan Scene dalam Satu Minggu**  
   - **Group by tanggal** → mosaic per tanggal (untuk menangani estate yang melintasi beberapa tile)  
   - **Filter** scene dengan `valid_pixel_ratio >= threshold` (threshold akan ditentukan berdasarkan referensi, misal 60%)  
   - Dari kandidat yang lolos, pilih **tanggal terbaru**  
   - Jika tidak ada kandidat, pilih **tanggal terbaru dari semua scene** dan set `low_quality_flag = TRUE`

5. **Statistik Zonal per Blok**  
   - Disimpan: **mean**, **std**, **valid_pixel_ratio**, dan **low_quality_flag**  
   - Statistik dihitung per blok setelah masking dan komputasi indeks

6. **Jadwal & Eksekusi**  
   - **Setiap Senin pukul 02:00**  
   - Window waktu: **7 hari terakhir** (Monday–Sunday)  
   - **Batch per estate** (loop) – tidak parallel di tahap awal

7. **Input Geometri**  
   - Format: **GeoJSON / Shapefile** (bukan asset GEE)  
   - Analisis dilakukan per blok (sesuai skema `blocks`)

8. **Versioning**  
   - Setiap kali algoritma atau parameter berubah, versi diincrement (`v1`, `v2`, …)  
   - Data lama tidak dihapus, tetap tersimpan untuk audit dan reprocessing

9. **Penanganan Edge Case**  
   - Jika tidak ada scene dalam window → **skip insert + buat notifikasi**  
   - Jika semua scene cloudy → tetap insert dengan `low_quality_flag = TRUE`  
   - Jika valid pixel ratio di bawah threshold → tetap insert dengan `low_quality_flag = TRUE`

10. **Lingkup Tahap 1**  
    - Hanya mencakup: ekstraksi data, cloud masking, perhitungan indeks, zonal stats, quality evaluation, weekly ingestion  
    - Belum mencakup anomaly detection, alert engine, atau ML modeling (akan menjadi Tahap 2)

---

## Action Items & Assignments

| Task | Owner | Status |
| :--- | :--- | :--- |
| **Menentukan threshold valid pixel ratio** (referensi standar perkebunan) | Tim Peneliti / Consultant | Pending |
| **Menyusun script Python GEE modular** (SceneFinder, CloudMasker, IndexCalculator, BlockAggregator, DBWriter) | Tim Pengembang | Pending |
| **Membangun orchestration scheduler** (cron di jam non‑operasional) | Tim Pengembang | Pending |
| **Testing multi‑estate batch** dengan data dummy untuk memastikan batasan GEE | Tim Pengembang | Pending |
| **Menyiapkan tabel satellite_data dengan field yang sesuai** (mean, std, valid_pixel_ratio, low_quality_flag, version) | Tim Pengembang | Pending |

---

## Open Questions / Blockers

- **Ambang batas valid pixel ratio** belum ditetapkan secara final. Perlu referensi dari praktik monitoring perkebunan (akan ditanyakan ke Perplexity atau konsultan agronomi).  
- **Performa multi‑estate batch** di GEE belum teruji. Perlu dilakukan simulasi dengan jumlah estate dan blok yang representatif.  
- **Format notifikasi** ke user saat tidak ada scene valid (misal email, in‑app message) belum didefinisikan.  
- **Kebijakan versioning** untuk reprocessing (apakah versi baru menggantikan tampilan default atau tetap menyimpan semua) perlu disepakati dengan tim produk.

---

## Critical Insights & Risks

- **Kepercayaan data** adalah prioritas utama. Manager perkebunan lebih memilih “tidak ada data” daripada data yang dihaluskan secara temporal karena dapat menyebabkan keputusan lapangan yang salah.  
- **Filosofi observed data** (apa adanya) dipilih untuk menjaga integritas observasi. Meskipun grafik time‑series akan memiliki bolong atau noise, transparansi ini membangun kepercayaan jangka panjang.  
- **Option B (Quality‑aware Observational)** dipilih karena menyeimbangkan antara kejujuran data dan ketersediaan informasi: scene terbaru yang memenuhi kualitas minimal digunakan, namun tetap memberi flag jika kualitas rendah.  
- **Resiko skala** : jika jumlah estate dan blok membengkak, pipeline loop per estate masih aman karena GEE menangani komputasi terdistribusi, namun perlu dipastikan tidak ada batasan waktu eksekusi (timeout) dari sisi scheduler.  
- **Pemisahan sensor** (Sentinel & Landsat) secara independen mencegah bias resolusi dan memungkinkan model ML memilih sensor terbaik di kemudian hari.

---

## Next Steps

1. **Tentukan threshold valid pixel ratio** – gunakan referensi standar perkebunan (misal dari literatur atau konsultan).  
2. **Buat blueprint teknis** – breakdown modul Python GEE (SceneFinder, CloudMasker, IndexCalculator, BlockAggregator, DBWriter).  
3. **Implementasi prototype** – jalankan untuk satu estate, uji coba dengan data historis 3 bulan.  
4. **Uji performa multi‑estate** – jalankan batch untuk 10 estate (sesuai asumsi) dan catat waktu eksekusi, memory, serta potensi timeout.  
5. **Siapkan mekanisme notifikasi** – tentukan channel dan format pesan saat tidak ada scene valid.  
6. **Dokumentasikan versioning strategy** – bagaimana versi baru menggantikan data lama di level aplikasi (apakah tampilan user selalu versi terbaru atau bisa memilih).
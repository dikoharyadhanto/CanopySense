# CanopySense — Panduan Simulasi Lokal

**Tujuan:** Mendemonstrasikan pipeline data CanopySense yang berjalan sepenuhnya di satu laptop — tanpa perlu langganan cloud atau server jarak jauh.
**Pembaca:** Tim proyek, calon kontraktor, stakeholder
**Terakhir Diperbarui:** 2026-04-20

---

## Apa yang Didemonstrasikan Simulasi Ini

Panduan ini memandu kamu melalui simulasi lengkap sistem CanopySense yang berjalan secara lokal. Di akhirnya, kamu akan melihat data vegetasi satelit nyata (NDVI, EVI, dan indeks lainnya) yang diambil dari Google Earth Engine dan disimpan di database lokal — database yang sama yang akan digunakan kontraktor dalam produksi.

Simulasi ini mencakup seluruh rantai prosesnya:

```
Laptop Kamu
────────────────────────────────────────────────────────────
  [Patcher-Local]  →  [Cloud Function (lokal)]  →  [Google Earth Engine]
                                                         ↓
                              [Database PostGIS Lokal]  ←
────────────────────────────────────────────────────────────
```

Satu-satunya layanan eksternal yang digunakan adalah **Google Earth Engine** (GEE) untuk mengambil citra satelit. Semua yang lain — script trigger, function pemrosesan, dan database — berjalan di mesin yang sama.

---

## Prasyarat

Hal-hal berikut harus sudah ada sebelum memulai. Semuanya sudah dikonfigurasi di laptop proyek.

| Komponen | Status | Detail |
|----------|--------|--------|
| Docker Desktop | Siap | Menjalankan database PostGIS lokal |
| Container PostGIS | Siap | Container: `canopy-project-repos`, port 5432 |
| Python 3.10+ | Siap | Dengan semua dependensi terpasang |
| `gcloud` terautentikasi | Siap | Memungkinkan simulator lokal menjangkau Google Cloud Secret Manager untuk kredensial GEE |
| `04_Test/.env` | Siap | Berisi `EE_PROJECT_ID` dan pengaturan koneksi PostGIS |
| `04_Test/test_registry.json` | Siap | Pengganti lokal untuk API key registry (dijelaskan di bawah) |

---

### Kenapa Autentikasi `gcloud` Diperlukan (Hanya untuk Simulasi Lokal)

Ini penting untuk dipahami: **autentikasi `gcloud` hanya diperlukan untuk simulasi lokal — tidak untuk produksi.**

Alasannya begini:

Dalam produksi, kode berjalan di dalam Google Cloud Functions. Google secara otomatis melampirkan identitas **service account** ke Cloud Function (`78268232885-compute@developer.gserviceaccount.com`). Identitas ini sudah punya izin untuk mengakses Secret Manager dan mengambil kredensial GEE. Tidak perlu login, tidak perlu key file, tidak perlu setup manual — semuanya ditangani sepenuhnya oleh infrastruktur Google Cloud.

Dalam simulasi lokal, `functions-framework` menjalankan kode yang sama sebagai proses Python biasa di laptop kamu. Laptop kamu tidak berada di dalam Google Cloud, jadi tidak ada service account yang terlampir. Sebagai gantinya, kode menggunakan login `gcloud` yang sudah ada di laptop (disebut Application Default Credentials) untuk menjangkau Secret Manager. Ini adalah solusi sementara khusus simulasi yang menirukan apa yang dilakukan service account secara otomatis dalam produksi.

**Sederhananya:**

| Lingkungan | Siapa yang mengautentikasi ke Secret Manager? |
|------------|-----------------------------------------------|
| Cloud Function nyata (produksi) | Service account Cloud Function — otomatis, tidak perlu setup |
| Simulasi lokal (laptop ini) | Login `gcloud` kamu — sudah diatur, digunakan sebagai pengganti |

Kontraktor yang menjalankan `patcher_local.py` di server mereka sama sekali tidak perlu `gcloud`. Script mereka hanya mengirim HTTP request ke URL Cloud Function — semua yang lain (autentikasi, akses GEE, Secret Manager) terjadi di dalam Google Cloud atas nama mereka.

---

### Untuk Apa `test_registry.json` Itu

Dalam produksi, Cloud Function memeriksa API key kontraktor terhadap registry yang disimpan di Google Cloud Secret Manager. Menjalankan pemeriksaan itu secara lokal berarti setiap panggilan test akan menyentuh Secret Manager hanya untuk memvalidasi test key — lambat dan tidak perlu.

`test_registry.json` adalah **salinan lokal dari registry tersebut**, hanya digunakan selama simulasi. Ini berisi satu entri: `CONTRACTOR_TEST` dengan API key test `my-test-key-123` (disimpan sebagai SHA-256 hash). Ketika simulator dimulai, file ini dimuat sebagai environment variable (`LOCAL_REGISTRY_JSON`), dan kode menggunakannya alih-alih memanggil Secret Manager untuk validasi key.

Hasilnya: validasi API key ditangani secara lokal dan instan, sementara pengambilan kredensial GEE tetap ke Secret Manager yang nyata. Kedua jalur bekerja persis seperti yang dilakukan dalam produksi — hanya dengan shortcut lokal untuk key registry.

---

Jika menjalankan ini di **mesin yang berbeda**, kamu juga perlu:
- Docker terpasang dan berjalan
- Python dengan: `pip install functions-framework requests python-dotenv psycopg2-binary earthengine-api geopandas`
- `gcloud` terpasang dan terautentikasi dengan akses ke GCP project `canopysense`

---

## Gambaran Umum: Dua Terminal, Satu Demo

Simulasi ini membutuhkan **dua jendela terminal yang terbuka bersamaan**:

- **Terminal A** — menjalankan Cloud Function secara lokal (tetap terbuka dan mendengarkan)
- **Terminal B** — menjalankan script trigger yang mengirimkan request

Anggap Terminal A sebagai "server cloud" dan Terminal B sebagai "laptop kontraktor."

---

## Langkah 1 — Mulai Database Lokal

Buka terminal dan konfirmasi container Docker PostGIS sedang berjalan:

```bash
docker ps --filter "name=canopy-project-repos" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

Output yang diharapkan:
```
NAMES                  STATUS         PORTS
canopy-project-repos   Up 2 hours     0.0.0.0:5432->5432/tcp
```

Kalau container tidak berjalan, mulai:
```bash
docker start canopy-project-repos
```

---

## Langkah 2 — Verifikasi Database Memiliki Data yang Ada (Opsional)

Sebelum simulasi, kamu bisa menunjukkan kondisi database saat ini. Ini membuat perbandingan "sebelum dan sesudah" lebih terlihat.

Buka koneksi database:
```bash
docker exec -it canopy-project-repos psql -U postgres -d canopysense
```

Jalankan query ini di dalam prompt psql:
```sql
SELECT COUNT(*) AS total_rows FROM canopysense.satellite_data;
```

Catat angka yang ditampilkan. Setelah simulasi berjalan, angka ini akan bertambah (atau tetap sama kalau scene satelit yang sama sudah tercatat — sistem dirancang untuk tidak pernah membuat entri duplikat).

Untuk keluar dari psql:
```sql
\q
```

---

## Langkah 3 — Buka Terminal A: Mulai Cloud Function Secara Lokal

Navigasi ke root proyek:
```bash
cd /home/dikoharyadhanto/Documents/Works/Projects/002_CanopySense
```

Muat kredensial GEE dan mulai server Cloud Function lokal:
```bash
set -a && source 04_Test/.env && set +a && \
LOCAL_REGISTRY_JSON=$(cat 04_Test/test_registry.json) \
functions-framework --target=patcher_cloud \
  --source=03_Build/patcher_cloud_function.py \
  --port=8080
```

Ketika sudah siap, kamu akan melihat:
```
Serving function...
Function: patcher_cloud
URL: http://localhost:8080/
```

**Biarkan Terminal A tetap terbuka.** Server sekarang sedang mendengarkan request.

---

## Langkah 4 — Buka Terminal B: Jalankan Script Trigger

Buka jendela terminal **kedua**. Navigasi ke root proyek yang sama:
```bash
cd /home/dikoharyadhanto/Documents/Works/Projects/002_CanopySense
```

Arahkan Patcher-Local ke Cloud Function lokal (alih-alih URL cloud yang live), kemudian jalankan:
```bash
set -a && source 04_Test/.env && set +a && \
CLOUD_FUNCTION_URL=http://localhost:8080 \
python3 03_Build/patcher_local.py
```

---

## Langkah 5 — Pantau Prosesnya

Terminal B akan menampilkan progress script trigger secara real-time:

```
08:30:01 [INFO] — Calling Cloud Function: http://localhost:8080 (contractor: CONTRACTOR_TEST)
08:30:48 [INFO] — Received 5 record(s) from Cloud Function.
08:30:48 [INFO] — Inserted 5 row(s) to satellite_data (ON CONFLICT DO NOTHING).
08:30:48 [INFO] — Patcher-Local complete. Rows inserted to satellite_data: 5
```

Sementara itu, Terminal A menampilkan Cloud Function yang memproses request di latar belakang — autentikasi GEE, pemilihan scene satelit, cloud masking, perhitungan indeks, dan ekstraksi data semuanya terjadi di sana.

Seluruh run membutuhkan waktu **sekitar 1–3 menit** tergantung kecepatan jaringan ke Google Earth Engine.

---

## Langkah 6 — Lihat Hasil di Database

Setelah run selesai, buka koneksi database untuk melihat data yang sudah dimasukkan:

```bash
docker exec -it canopy-project-repos psql -U postgres -d canopysense
```

**Query 1: Hitung semua record**
```sql
SELECT COUNT(*) AS total_rows FROM canopysense.satellite_data;
```

Ini mengonfirmasi data sudah ditulis. Bandingkan dengan jumlah dari Langkah 2.

---

**Query 2: Tampilkan record satelit terbaru**
```sql
SELECT
    block_id,
    acquisition_date,
    sensor,
    ROUND(ndvi::numeric, 4)        AS ndvi,
    ROUND(evi::numeric, 4)         AS evi,
    ROUND(cloud_cover::numeric, 2) AS cloud_cover_pct
FROM canopysense.satellite_data
ORDER BY acquisition_date DESC, block_id ASC
LIMIT 10;
```

Output yang diharapkan (tanggal dan nilai kamu akan bervariasi tergantung scene satelit yang dipilih):
```
 block_id | acquisition_date |  sensor   |  ndvi  |  evi   | cloud_cover_pct
----------+------------------+-----------+--------+--------+-----------------
       18 | 2026-04-16       | sentinel-2 | 0.6124 | 0.3891 |            3.20
       21 | 2026-04-16       | sentinel-2 | 0.5834 | 0.3612 |            4.10
       24 | 2026-04-16       | sentinel-2 | 0.6441 | 0.4021 |            2.80
       25 | 2026-04-16       | sentinel-2 | 0.5512 | 0.3287 |            5.60
       29 | 2026-04-16       | sentinel-2 | 0.6038 | 0.3754 |            3.90
(5 rows)
```

---

**Query 3: Tampilkan record lengkap untuk satu block**
```sql
SELECT *
FROM canopysense.satellite_data
WHERE block_id = 18
ORDER BY acquisition_date DESC
LIMIT 1;
```

Ini menampilkan semua indeks vegetasi untuk satu block — NDVI, EVI, NDRE (khusus Sentinel-2), SAVI, GNDVI, cloud cover, dan metadata kualitas yang disimpan di kolom `features`.

---

**Query 4: Ringkasan per sensor dan tanggal**
```sql
SELECT
    acquisition_date,
    sensor,
    COUNT(*)                            AS blocks_processed,
    ROUND(AVG(ndvi)::numeric, 4)        AS avg_ndvi,
    ROUND(AVG(cloud_cover)::numeric, 2) AS avg_cloud_cover_pct
FROM canopysense.satellite_data
GROUP BY acquisition_date, sensor
ORDER BY acquisition_date DESC;
```

Ini memberikan gambaran umum apa yang ditangkap per lintasan satelit.

---

## Langkah 7 — Hentikan Cloud Function Lokal

Ketika demo selesai, kembali ke Terminal A dan tekan `Ctrl + C` untuk menghentikan server lokal.

---

## Apa Arti Hasilnya

| Kolom | Yang Diceritakannya |
|-------|---------------------|
| `block_id` | Block perkebunan mana yang menjadi milik pengukuran ini |
| `acquisition_date` | Tanggal satelit mengambil gambar ini |
| `sensor` | Satelit mana yang digunakan (`sentinel-2`, `landsat-8`, atau `landsat-9`) |
| `ndvi` | Normalized Difference Vegetation Index — semakin tinggi = vegetasi semakin sehat (0,5–0,8 adalah tipikal untuk sawit sehat) |
| `evi` | Enhanced Vegetation Index — mirip NDVI tapi lebih baik di area kanopi yang rapat |
| `ndre` | Red Edge index — hanya Sentinel-2 — sensitif terhadap stres dini sebelum terlihat di NDVI |
| `savi` | Soil-Adjusted Vegetation Index — mengoreksi pengaruh tanah yang terbuka |
| `gndvi` | Green NDVI — sensitif terhadap kandungan klorofil |
| `cloud_cover` | Persentase block yang tertutup awan dalam gambar ini |
| `features` | Metadata JSON: rasio piksel valid dan flag kualitas |

---

## Cara Kerja Perlindungan Duplikat

Kalau kamu menjalankan script trigger untuk kedua kalinya dengan scene satelit yang sama masih menjadi yang terbaru, kamu akan melihat:

```
[INFO] — Received 5 record(s) from Cloud Function.
[INFO] — Inserted 0 row(s) to satellite_data (ON CONFLICT DO NOTHING).
[INFO] — Patcher-Local complete. Rows inserted to satellite_data: 0
```

**Ini adalah perilaku yang benar.** Sistem tidak pernah membuat record duplikat untuk kombinasi block + tanggal + sensor yang sama. Menjalankan script berkali-kali selalu aman.

---

## Troubleshooting Demo

| Gejala | Kemungkinan Penyebab | Solusi |
|--------|---------------------|--------|
| Terminal A menampilkan `Address already in use` | Port 8080 sudah dipakai | Jalankan `lsof -i :8080` untuk menemukan dan menghentikan prosesnya |
| Terminal B menampilkan `403 Forbidden` | API key salah di `.env` | Pastikan `PATCHER_API_KEY=my-test-key-123` di `.env` |
| Terminal B menampilkan `Connection refused` | Terminal A belum dimulai | Mulai Terminal A terlebih dahulu, tunggu pesan "Serving function..." |
| Terminal B menampilkan `PostGIS ingestion failed` | Container Docker tidak berjalan | Jalankan `docker start canopy-project-repos` |
| Run membutuhkan lebih dari 5 menit | GEE lambat merespons | Tunggu — waktu pemrosesan GEE bervariasi. Rentang normal 1–5 menit |

---

## Hubungannya dengan Setup Produksi

Dalam lingkungan produksi, simulasi ini langsung memetakan ke komponen nyata:

| Komponen Simulasi | Padanannya di Produksi |
|-------------------|------------------------|
| Server lokal `functions-framework` | Google Cloud Function (`patcher_cloud`) |
| `test_registry.json` (file lokal) | Google Secret Manager (`canopysense-api-key-registry`) |
| PostGIS `localhost:5432` | Server PostGIS produksi kontraktor |
| Script `patcher_local.py` yang sama | Script yang sama — tidak perlu perubahan untuk produksi |

Kontraktor hanya mengubah file `.env` — `CLOUD_FUNCTION_URL` mengarah ke URL Cloud Function yang sesungguhnya alih-alih `localhost:8080`, dan pengaturan PostGIS mengarah ke database produksi mereka.

---

---

## Integration Testing Berbasis Docker (04_Test/)

Lingkungan test yang terisolasi tersedia di `04_Test/`. Tidak seperti simulasi functions-framework di atas, lingkungan ini tidak memerlukan autentikasi `gcloud`, kredensial GEE, atau deployment cloud yang nyata. Ini adalah metode standar untuk menjalankan integration test selama pengembangan.

**Yang dijalankannya:**
- Docker Compose menjalankan container PostGIS yang sudah di-seed dengan test block dan schema
- `mock_cloud.py` (hanya stdlib) menggantikan Cloud Function — mengembalikan response `writes` yang valid tanpa menyentuh GEE
- `patcher_local.py` berjalan di dalam container dan menulis hasil ke Docker PostGIS

**Prasyarat:** salin `04_Test/.env.test.example` ke `04_Test/.env.test` dan isi nilainya (tidak perlu kredensial GEE — mock menangani semua response).

**Mulai lingkungannya:**
```bash
cd /home/dikoharyadhanto/Documents/Works/Projects/002_CanopySense
docker compose -f 04_Test/docker-compose.yml up --build
```

**Jalankan mock cloud di terminal terpisah:**
```bash
cd /home/dikoharyadhanto/Documents/Works/Projects/002_CanopySense
python3 04_Test/mock_cloud.py
```

**Verifikasi hasil di Docker PostGIS:**
```bash
docker compose -f 04_Test/docker-compose.yml exec postgis \
  psql -U patcher -d canopysense_test \
  -c "SELECT block_id, acquisition_date, sensor FROM canopysense.satellite_data"
```

**Kapan menggunakan masing-masing simulasi:**

| Kebutuhan | Metode |
|-----------|--------|
| Menampilkan pipeline lengkap dengan data satelit nyata kepada stakeholder | functions-framework (panduan ini) |
| Menjalankan integration test selama pengembangan — tidak perlu GEE | Docker (`04_Test/`) |
| Memverifikasi bug fix tertentu terhadap kondisi PostGIS yang realistis | Docker (`04_Test/`) |
| Menguji perubahan kontrak response Cloud Function | Docker (`04_Test/` + mock_cloud.py) |

---

*CanopySense LOCAL_SIMULATION_ID.md — v1.1 — 2026-04-25*

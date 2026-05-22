# CanopySense — Alur Kerja Skenario Nyata

**Tujuan:** Menjelaskan bagaimana sistem CanopySense secara keseluruhan bekerja ketika terintegrasi dengan server produksi PostGIS nyata milik kontraktor.
**Pembaca:** Tim proyek, kontraktor, stakeholder
**Terakhir Diperbarui:** 2026-04-20

---

## Apa yang Dicakup Dokumen Ini

Dokumen ini mendeskripsikan alur kerja produksi — yang sesungguhnya, bukan simulasi. Kontraktor sudah punya server sendiri dengan PostGIS yang berjalan, administrator sudah menerbitkan API key untuk mereka, dan seluruh pipeline berjalan di atas infrastruktur nyata.

Pada akhir run yang berhasil, data vegetasi satelit yang sudah diproses akan tersimpan di database kontraktor sendiri — siap digunakan untuk pelaporan, dashboard, atau tools analisis mereka.

Rantai produksi lengkapnya terlihat seperti ini:

```
Server Kontraktor                   Google Cloud                    Eksternal
──────────────────    ────────────────────────────────────────    ────────────
                      │                                          │
  [patcher_local.py]  →  [Cloud Function: patcher_cloud]  →  [Google Earth Engine]
        ↑                         │                                  │
        │              [Secret Manager]                              │
        │              ├── API key registry  (validasi kontraktor)  │
        │              └── GEE service account key  (ambil & pakai) ┘
        │                         │
        └─── JSON response ───────┘
        ↓
  [PostGIS Kontraktor]
──────────────────────
```

Semua yang ada di kiri (server kontraktor dan PostGIS) adalah milik kontraktor. Semua yang ada di tengah (Cloud Function, Secret Manager) adalah milik administrator. Google Earth Engine adalah sumber data satelitnya.

---

## Perbedaannya dengan Simulasi Lokal

| Aspek                              | Simulasi Lokal                                  | Produksi Nyata                                               |
| ---------------------------------- | ----------------------------------------------- | ------------------------------------------------------------ |
| Cloud Function                     | Berjalan di laptop via `functions-framework`    | Berjalan di Google Cloud (selalu aktif)                      |
| API key registry                   | Dimuat dari `test_registry.json` di laptop      | Diambil dari Google Cloud Secret Manager                     |
| Kredensial GEE                     | Diambil via login `gcloud` di laptop            | Diambil via service account Cloud Function (otomatis)        |
| Database PostGIS                   | Container Docker di laptop                      | Server nyata kontraktor                                      |
| Bore tunnel                        | Diperlukan (untuk mengekspos DB lokal ke cloud) | Tidak diperlukan (server kontraktor bisa dijangkau langsung) |
| `functions-framework`              | Diperlukan                                      | Tidak diperlukan                                             |
| Login `gcloud` di mesin kontraktor | Diperlukan                                      | Tidak diperlukan                                             |

Dalam produksi, kontraktor tidak membutuhkan akun Google, tools Google Cloud, maupun setup khusus apa pun selain Python dan PostgreSQL.

---

## Prasyarat

Sebelum run nyata pertama bisa terjadi, kedua pihak harus siap.

### Sisi Administrator (Setup Sekali Jalan — Sudah Selesai)

| Item                                                                             | Status  |
| -------------------------------------------------------------------------------- | ------- |
| Cloud Function `patcher_cloud` sudah di-deploy ke Google Cloud                   | Selesai |
| GEE service account key sudah disimpan di Secret Manager                         | Selesai |
| API key registry (`canopysense-api-key-registry`) sudah dibuat di Secret Manager | Selesai |
| IAM role sudah diberikan ke service account Cloud Function                       | Selesai |

### Sisi Kontraktor (Setup Per Kontraktor)

| Item                                                                 | Siapa yang Melakukan | Catatan                                                      |
| -------------------------------------------------------------------- | -------------------- | ------------------------------------------------------------ |
| PostgreSQL 12+ dengan PostGIS terpasang dan berjalan                 | Kontraktor           | Harus bisa diakses dari server mereka                        |
| Schema dan tabel `canopysense` sudah dibuat (DDL script diterapkan)  | Kontraktor           | Admin menyediakan DDL script                                 |
| `patcher_local.py` sudah disalin ke server mereka                    | Kontraktor           | Disediakan oleh admin                                        |
| File `.env` sudah dikonfigurasi dengan kredensial mereka             | Kontraktor           | Lihat Bagian A.2 di GUIDANCE.md                              |
| Python 3.8+ terpasang dengan package yang diperlukan                 | Kontraktor           | `pip install requests python-dotenv psycopg2-binary`         |
| API key sudah diterbitkan dan ditambahkan ke registry Secret Manager | Administrator        | Lihat Bagian A.0 GUIDANCE.md                                 |
| User audit read-only (`canopysense_audit`) sudah dibuat di DB mereka | Kontraktor           | Admin menggunakannya untuk memverifikasi data secara mandiri |

---

## Langkah demi Langkah: Yang Terjadi Saat Run Nyata

### Langkah 1 — Kontraktor Memicu Script

Kontraktor menjalankan satu perintah di server mereka:

```bash
cd /path/to/patcher
python3 patcher_local.py
```

Atau, kalau sudah diatur terjadwal (cron), ini terjadi secara otomatis — kontraktor tidak perlu melakukan apa-apa.

---

### Langkah 2 — Patcher-Local Mengirim Request ke Cloud

`patcher_local.py` membaca konfigurasi dari `.env` dan mengirim request HTTPS yang aman ke Cloud Function:

```
POST https://asia-southeast2-canopysense.cloudfunctions.net/patcher_cloud
Headers:
  X-API-Key: <API key kontraktor>
  Content-Type: application/json
```

API key kontraktor berjalan terenkripsi lewat HTTPS — tidak pernah terekspos dalam bentuk teks biasa.

---

### Langkah 3 — Cloud Function Memvalidasi Request

Cloud Function menerima request dan langsung memeriksa dua hal:

**Pemeriksaan 1 — Apakah API key ada?**
Kalau tidak ada key yang dikirim di header → mengembalikan `401 Unauthorized`. Run berhenti di sini.

**Pemeriksaan 2 — Apakah API key valid dan aktif?**
Cloud Function mengambil API key registry dari Secret Manager dan mencari SHA-256 hash dari key tersebut. Ada tiga kemungkinan hasilnya:

- Key tidak ditemukan → `403 Forbidden: Invalid API Key`
- Key ditemukan tapi statusnya `REVOKED` → `403 Forbidden: API Key revoked`
- Key ditemukan dan statusnya `ACTIVE` → lanjut ke Langkah 4

Seluruh langkah validasi ini membutuhkan waktu kurang dari satu detik. Core engine belum tersentuh sama sekali di sini.

---

### Langkah 4 — Cloud Function Mengambil Kredensial GEE

Setelah kontraktor terautentikasi, Cloud Function mengambil GEE service account key dari Secret Manager. Key ini memungkinkan sistem terhubung ke GEE dan meminta pemrosesan citra satelit.

Kontraktor tidak pernah melihat key ini. Key ini hanya ada di dalam Google Cloud dan dimuat ke memori untuk durasi request ini saja.

---

### Langkah 5 — Core Engine Berjalan

Dengan kredensial GEE siap, core engine menjalankan seluruh pipeline data satelit:

1. Memuat semua blok perkebunan dari definisi database
2. Menghitung window tanggal (7 hari terakhir)
3. Mencari scene satelit terbaik yang tersedia (Sentinel-2 diprioritaskan, Landsat sebagai fallback)
4. Menerapkan cloud masking untuk menghilangkan piksel yang tertutup awan
5. Menghitung indeks vegetasi: NDVI, EVI, NDRE, SAVI, GNDVI
6. Mengekstrak statistik per block menggunakan infrastruktur komputasi Google Earth Engine
7. Menerapkan quality filtering (block dengan cloud cover terlalu tinggi dilewati)
8. Mengemas hasilnya sebagai record data yang terstruktur

Ini adalah langkah yang paling lama — biasanya **2–5 menit** tergantung jumlah block dan kompleksitas scene satelit.

---

### Langkah 6 — Hasil Dikembalikan ke Kontraktor

Cloud Function mengirimkan record yang sudah diproses kembali ke `patcher_local.py` sebagai response JSON:

```json
{
  "status": "success",
  "api_version": "1.1",
  "timestamp": "2026-04-20T10:30:05Z",
  "contractor_id": "CONTRACTOR_ACME_FARMS",
  "errors": [],
  "writes": [
    {
      "table": "satellite_data",
      "rows": [
        {
          "block_id": "18",
          "acquisition_date": "2026-04-18",
          "sensor": "sentinel-2",
          "ndvi": "0.6124",
          "evi": "0.3891",
          ...
        },
        ...
      ]
    }
  ]
}
```

Data berjalan kembali ke server kontraktor melalui koneksi HTTPS terenkripsi yang sama.

---

### Langkah 7 — Patcher-Local Menulis ke PostGIS Kontraktor

`patcher_local.py` menerima JSON tersebut, mengurai setiap record, dan memasukkannya ke tabel `canopysense.satellite_data` lokal kontraktor menggunakan kredensial database mereka sendiri dari `.env`.

Script ini dirancang **aman untuk dijalankan berkali-kali** — kalau record untuk block, tanggal, dan sensor yang sama sudah ada, itu akan dilewati secara diam-diam. Tidak ada duplikat yang pernah dibuat.

Terminal kontraktor menampilkan:

```
10:30:01 [INFO] — Calling Cloud Function: https://... (contractor: CONTRACTOR_ACME_FARMS)
10:32:18 [INFO] — Received 84 record(s) from Cloud Function.
10:32:18 [INFO] — Inserted 84 row(s) to satellite_data (ON CONFLICT DO NOTHING).
10:32:18 [INFO] — Patcher-Local complete. Rows inserted to satellite_data: 84
```

---

### Langkah 8 — Semua Dicatat

Setiap langkah proses dicatat di Google Cloud Logging di bawah akun administrator. Kontraktor tidak perlu mengelola log apa pun di pihak mereka — tapi administrator punya audit trail yang lengkap:

```json
{ "audit": true, "contractor_id": "CONTRACTOR_ACME_FARMS", "status": "AUTH_OK",  "detail": "Triggering core engine" }
{ "audit": true, "contractor_id": "CONTRACTOR_ACME_FARMS", "status": "SUCCESS",  "detail": "rows=84" }
```

---

## Memverifikasi Hasilnya

### Tampilan Kontraktor — Periksa Database Mereka Sendiri

Kontraktor terhubung ke PostGIS mereka dan menjalankan:

```sql
-- Konfirmasi data sudah masuk
SELECT COUNT(*) AS total_rows FROM canopysense.satellite_data;

-- Lihat record terbaru
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

---

### Tampilan Administrator — Verifikasi via Cloud Logging

Login ke [console.cloud.google.com](https://console.cloud.google.com) → project **canopysense** → **Logging → Log Explorer** dan filter:

```
resource.type="cloud_run_revision"
resource.labels.service_name="patcher-cloud"
jsonPayload.audit=true
jsonPayload.contractor_id="CONTRACTOR_ACME_FARMS"
```

Konfirmasi entri `AUTH_OK` dan `SUCCESS` dengan jumlah `rows=` yang diharapkan.

---

### Tampilan Administrator — Verifikasi Langsung di Database Kontraktor

Menggunakan kredensial audit read-only yang disediakan kontraktor (lihat Langkah 8 GUIDANCE.md), terhubung langsung:

```bash
psql -h <host_db_kontraktor> -p 5432 -U canopysense_audit -d canopysense
```

Kemudian jalankan:

```sql
-- Konfirmasi volume data total
SELECT COUNT(*) AS total_rows FROM canopysense.satellite_data;

-- Konfirmasi acquisition terbaru sudah baru
SELECT MAX(acquisition_date) AS latest_data FROM canopysense.satellite_data;

-- Ringkasan per tanggal dan sensor
SELECT
    acquisition_date,
    sensor,
    COUNT(*)                            AS blocks_processed,
    ROUND(AVG(ndvi)::numeric, 4)        AS avg_ndvi,
    ROUND(AVG(cloud_cover)::numeric, 2) AS avg_cloud_pct
FROM canopysense.satellite_data
GROUP BY acquisition_date, sensor
ORDER BY acquisition_date DESC;
```

Ini memberi administrator visibilitas penuh ke data kontraktor tanpa akses tulis apa pun ke server mereka.

---

## Tanggung Jawab Masing-Masing Pihak

| Tanggung Jawab                         | Kontraktor | Administrator |
| -------------------------------------- | ---------- | ------------- |
| Menjalankan `patcher_local.py`         | ✅          |               |
| Memelihara server PostGIS mereka       | ✅          |               |
| Menjaga keamanan file `.env` mereka    | ✅          |               |
| Melaporkan kegagalan ke admin          | ✅          |               |
| Menerbitkan dan mencabut API key       |            | ✅             |
| Memelihara Cloud Function              |            | ✅             |
| Memantau Cloud Logging                 |            | ✅             |
| Memverifikasi data via akses read-only |            | ✅             |
| Mengelola kredensial GEE               |            | ✅             |

---

## Yang Terjadi Jika Sesuatu Salah

| Gejala                                               | Kemungkinan Penyebab                                             | Siapa yang Bertindak                                                          |
| ---------------------------------------------------- | ---------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| Kontraktor mendapat `401 Unauthorized`               | API key tidak ada di `.env`                                      | Kontraktor periksa `.env` mereka                                              |
| Kontraktor mendapat `403 Forbidden: Invalid API Key` | Key salah atau ada typo di `.env`                                | Kontraktor salin ulang key dari pengiriman aman                               |
| Kontraktor mendapat `403 Forbidden: API Key revoked` | Key dicabut oleh admin                                           | Kontraktor hubungi administrator                                              |
| Kontraktor mendapat `504 Gateway Timeout`            | Core engine terlalu lama                                         | Admin periksa Cloud Logging; kontraktor tingkatkan `FUNCTION_TIMEOUT_SECONDS` |
| Kontraktor mendapat `500 Internal Server Error`      | Kegagalan sisi server                                            | Admin periksa Cloud Logging untuk entri `ENGINE_ERROR`                        |
| `Inserted 0 rows` setelah run berhasil               | Scene yang sama sudah ada di DB (tidak ada data baru minggu ini) | Perilaku yang diharapkan — bukan error                                        |
| Admin melihat `rows=84` di log tapi DB menunjukkan 0 | Penulisan PostGIS kontraktor gagal                               | Kontraktor periksa koneksi DB dan ruang disk mereka                           |

---

## Perbedaan Utama dari Simulasi Lokal Sekilas Pandang

Simulasi lokal digunakan untuk membuktikan sistem bekerja sebelum ada server nyata yang terlibat. Dalam produksi nyata:

- Tidak ada `functions-framework` — Cloud Function selalu berjalan di Google Cloud
- Tidak ada `test_registry.json` — API key divalidasi langsung dari Secret Manager
- Tidak ada bore tunnel — PostGIS kontraktor ada di server nyata dengan IP nyata
- Tidak ada login `gcloud` di mesin kontraktor — kontraktor hanya perlu Python
- Admin memverifikasi hasil via Cloud Logging **dan** akses DB read-only langsung

Semua yang lain — API key, format request, pipeline GEE, schema data, query SQL — identik dengan yang didemonstrasikan dalam simulasi lokal.

---

## Keputusan Arsitektur: Bagaimana Cloud Function Mendapatkan Poligon Block

Bagian ini membahas pertanyaan penting yang muncul saat berpindah dari simulasi lokal ke produksi nyata:

> **`patcher_local.py` hanya mengirimkan API key ke Cloud Function. Tidak ada data block yang dikirim. Lalu bagaimana Cloud Function tahu area perkebunan mana yang harus diproses?**

Cloud Function harus terhubung ke database untuk membaca geometri poligon block sebelum bisa meminta Google Earth Engine memproses apa pun. Dalam simulasi lokal, kami sementara mengekspos Docker PostGIS lokal ke Cloud Function via bore tunnel — itu adalah solusi sementara untuk pengujian, bukan desain produksi.

Untuk produksi nyata, ada tiga opsi arsitektur. Masing-masing punya jawaban berbeda atas pertanyaan: **database siapa yang terhubung ke Cloud Function?**

---

### Opsi A — Central Blocks Database (Dikelola Admin di Google Cloud)

**Cara kerjanya:**

Administrator memelihara satu database PostGIS terpusat yang berjalan di dalam Google Cloud (misalnya Cloud SQL). Semua poligon block kontraktor disimpan di database terpusat ini, diunggah sekali saat onboarding. Cloud Function selalu membaca data block dari sana — tidak perlu terhubung ke server kontraktor sama sekali.

PostGIS kontraktor sendiri tetap hanya sebagai tujuan penulisan: hanya menerima hasil satelit yang sudah diproses dari `patcher_local.py`. Tidak ada aliran data keluar dari situ ke cloud.

```
Server Kontraktor                      Google Cloud
────────────────────    ───────────────────────────────────────────────
                        │                                             │
  [patcher_local.py] → [Cloud Function]  →  [Google Earth Engine]   │
        ↑                    ↓                                        │
        │            baca blocks dari                                 │
        │            [Central PostGIS]  ──────────────────────────── ┘
        │            (dikelola admin,
        │             di dalam Google Cloud)
        │                    │
        └── terima hasil ────┘
        ↓
  [PostGIS Kontraktor]
  (hanya tulis, tidak pernah terekspos ke cloud)
────────────────────
```

**Prosesnya:**

1. Saat onboarding, admin mengunggah shapefile block kontraktor ke PostGIS terpusat sekali
2. Kontraktor menjalankan `patcher_local.py` → hanya mengirim API key
3. Cloud Function membaca block dari PostGIS terpusat
4. GEE memproses block tersebut
5. Hasil dikembalikan ke `patcher_local.py` → ditulis ke PostGIS lokal kontraktor

**Keuntungan:**

- Database kontraktor sepenuhnya privat — tidak perlu membuka port, tidak perlu mengubah firewall
- Admin punya kendali penuh atas block mana yang diproses untuk setiap kontraktor
- Data block disimpan di satu tempat — mudah diperbarui, diaudit, dan di-versioning
- Tidak bergantung pada ketersediaan jaringan atau server kontraktor selama pemrosesan
- Arsitektur paling aman dari ketiga opsi

**Risiko:**

- Admin harus memelihara instance Cloud SQL terpisah (biaya bulanan tambahan sekitar $30–80/bulan tergantung ukuran)
- Jika admin mengunggah data block yang salah saat onboarding, hasilnya akan salah — tidak ada validasi otomatis terhadap DB kontraktor
- Pembaruan block (area perkebunan baru, block yang sudah tidak aktif) harus melalui admin — kontraktor tidak bisa mandiri

**Paling cocok untuk:** Proyek dengan banyak kontraktor, batas block yang stabil, dan admin yang ingin kendali penuh atas apa yang diproses.

---

### Opsi B — Patcher-Local Mengirim Block dalam Request

**Cara kerjanya:**

`patcher_local.py` diberi peran yang sedikit diperluas: sebelum memanggil Cloud Function, ia membaca geometri poligon block dari PostGIS lokal kontraktor sendiri dan menyertakannya dalam body HTTP request. Cloud Function menerima sekaligus API key dan data block dalam satu request — tidak perlu terhubung ke database mana pun untuk mendapatkan poligon.

Cloud Function memproses hanya block yang diterima dalam request, menjalankan GEE, dan mengembalikan hasil. Semuanya selesai dalam satu round trip.

```
Server Kontraktor                             Google Cloud
────────────────────────────    ────────────────────────────────────
                                │                                   │
  [PostGIS Kontraktor]          │                                   │
        ↓ (baca blocks)         │                                   │
  [patcher_local.py]  →  POST (API key + block polygons as JSON)   │
        ↑                  → [Cloud Function]  →  [Google Earth Engine]
        └──── terima hasil ─────────────── ←
        ↓
  [PostGIS Kontraktor]
  (tulis hasil kembali)
────────────────────────────
```

**Prosesnya:**

1. Kontraktor menjalankan `patcher_local.py`
2. Script membaca block dari PostGIS lokal kontraktor terlebih dahulu
3. Script mengirim API key + block GeoJSON ke Cloud Function dalam satu request
4. Cloud Function memvalidasi key, memproses block yang diterima via GEE
5. Hasil dikembalikan ke `patcher_local.py` → ditulis kembali ke PostGIS kontraktor

**Keuntungan:**

- Tidak perlu database terpusat — tidak ada biaya infrastruktur cloud tambahan
- Data block kontraktor tetap di server mereka sendiri
- Pembaruan block langsung berlaku — kontraktor update DB mereka, run berikutnya otomatis pakai block baru
- Kontraktor mandiri — tidak bergantung pada admin untuk pengelolaan block
- Tidak ada koneksi keluar dari cloud ke server kontraktor

**Risiko:**

- `patcher_local.py` perlu perubahan kode — saat ini tidak mengirim data block
- Area perkebunan besar dengan banyak block berarti payload HTTP request yang lebih besar
- Kalau PostGIS kontraktor kosong atau tabel block-nya salah, GEE tidak punya apa yang harus diproses — lebih sulit didiagnosis dari sisi admin
- Admin punya visibilitas lebih terbatas atas block mana yang sebenarnya diproses

**Paling cocok untuk:** Proyek di mana kontraktor mengelola batas block mereka sendiri dan perlu memperbarui tanpa harus melalui admin.

---

### Opsi C — Kontraktor Mengekspos Database Mereka ke Cloud Function

**Cara kerjanya:**

Cloud Function terhubung langsung ke server PostGIS kontraktor melalui internet untuk membaca data block — sama seperti yang dilakukan selama pengujian Level 2 via bore tunnel. Dalam produksi, tunnel digantikan oleh koneksi database nyata: kontraktor membuka port tertentu di firewall server mereka dan Cloud Function terhubung menggunakan kredensial yang disimpan di environment variable-nya.

```
Server Kontraktor                             Google Cloud
────────────────────────    ────────────────────────────────────────
                            │                                       │
  [PostGIS Kontraktor] ←────┼── DB connection (baca blocks) ──── [Cloud Function]
        ↓                   │                                    ↓
  (blocks dibaca cloud)     │                          [Google Earth Engine]
        ↓                   │                                    ↓
  [PostGIS Kontraktor] ←────┼───── terima hasil ─────────────
  (hasil ditulis kembali)   │
────────────────────────    │
```

**Prosesnya:**

1. Kontraktor mengkonfigurasi firewall server mereka untuk mengizinkan koneksi masuk dari IP range Google Cloud pada port 5432
2. Admin menyimpan kredensial DB kontraktor (host, port, user, password) di environment variable Cloud Function
3. Kontraktor menjalankan `patcher_local.py` → hanya mengirim API key
4. Cloud Function terhubung langsung ke PostGIS kontraktor, membaca block
5. GEE memproses block tersebut, hasil dikembalikan ke Cloud Function
6. Cloud Function mengembalikan hasil ke `patcher_local.py` → ditulis ke PostGIS yang sama

**Keuntungan:**

- Tidak perlu perubahan kode — ini adalah cara sistem saat ini bekerja (bore tunnel mensimulasikan ini)
- Tidak perlu database terpusat untuk dipelihara
- Pembaruan block di sisi kontraktor langsung tersedia untuk cloud

**Risiko:**

- Kontraktor harus membuka port database mereka ke internet — risiko keamanan yang signifikan
- PostgreSQL yang terekspos ke internet publik adalah vektor serangan umum meski dengan password yang kuat
- Admin memegang kredensial database kontraktor — batas kepercayaan yang sensitif
- Kalau server kontraktor down atau jaringannya lambat, Cloud Function tidak bisa membaca block dan seluruh run gagal
- Aturan firewall dan IP allowlisting untuk IP range Google Cloud itu kompleks dan berubah-ubah (Google Cloud mempublikasikan IP range tapi jumlahnya besar dan diperbarui secara berkala)
- Tidak disarankan untuk produksi kecuali berada dalam VPN atau jaringan privat

**Paling cocok untuk:** Hanya pengujian internal, atau arsitektur di mana Cloud Function dan database kontraktor berada dalam jaringan privat yang sama (VPN). Tidak cocok untuk deployment produksi yang menghadap internet.

---

## Perbandingan Ringkasan

|                                                   | Opsi A — Central DB   | Opsi B — Kirim Block dalam Request | Opsi C — Ekspos DB Kontraktor |
| ------------------------------------------------- | --------------------- | ---------------------------------- | ----------------------------- |
| **DB kontraktor terekspos ke cloud**              | Tidak                 | Tidak                              | Ya                            |
| **Perlu perubahan kode**                          | Tidak                 | Ya (`patcher_local.py`)            | Tidak                         |
| **Biaya infrastruktur tambahan**                  | Ya (Cloud SQL)        | Tidak                              | Tidak                         |
| **Block bisa diperbarui mandiri oleh kontraktor** | Tidak (melalui admin) | Ya                                 | Ya                            |
| **Kendali admin atas apa yang diproses**          | Penuh                 | Sebagian                           | Sebagian                      |
| **Berfungsi jika server kontraktor down**         | Ya                    | Tidak                              | Tidak                         |
| **Risiko keamanan**                               | Rendah                | Rendah                             | Tinggi                        |
| **Disarankan untuk produksi**                     | ✅ Ya                  | ✅ Ya                               | ❌ Hanya pengujian             |

---

## Status Saat Ini

Implementasi saat ini (per v0.10) menggunakan **Opsi B** — Patcher-Local membaca geometri block dari PostGIS lokal kontraktor dan mengirimkannya dalam body POST request. Cloud Function tidak memiliki koneksi database keluar sama sekali. Lihat bagian di bawah untuk penjelasan lengkap alasannya.

**Opsi B sudah diimplementasikan dan aktif.** Tidak diperlukan perubahan kode lebih lanjut untuk mekanisme pengiriman block.

---

## Keputusan: Opsi B — Alasan dan Cara Kerjanya

### Mengapa Opsi B Dipilih

Setelah diskusi, Opsi B (Patcher-Local mengirim block dalam request) dipilih karena alasan-alasan berikut:

**1. Scheduled run memberikan waktu yang cukup untuk retry**
Pipeline berjalan terjadwal — mingguan atau harian. Kalau sebuah request gagal di tengah jalan, tidak ada urgensi untuk pulih dalam hitungan milidetik. Retry bersih dalam window terjadwal yang sama sudah memadai. Ini membuat kompleksitas tambahan dari retry logic bisa dikelola, bukan kritis.

**2. Ukuran payload GeoJSON bukan masalah**
Poligon block perkebunan adalah geometri yang kecil — bahkan estate dengan ratusan block menghasilkan payload GeoJSON dalam kisaran 50–500 KB. Ini jauh di bawah batas request HTTP dan menambah overhead jaringan yang sangat kecil.

**3. Validasi schema ditangani oleh akses audit read-only**
Administrator memiliki akses read-only (`canopysense_audit`) ke PostGIS kontraktor. Sebelum mulai live, admin terhubung dan memverifikasi bahwa struktur block kontraktor sesuai dengan schema yang diharapkan. Ini adalah pemeriksaan sekali jalan, bukan ketergantungan berkelanjutan.

**4. Data-parser menstandarkan upload di sisi kontraktor**
Setiap kali kontraktor mengunggah shapefile melalui aplikasi mereka, script data-parser menstandarkan format geometri dan atribut sebelum menulis ke PostGIS. Ini memastikan block yang dikirim ke Cloud Function selalu dalam struktur yang benar — tidak ada kejutan format saat runtime.

**5. Tidak ada biaya infrastruktur cloud tambahan**
Opsi A membutuhkan instance Cloud SQL yang berjalan terus-menerus. Opsi B tidak membutuhkan apa pun tambahan di cloud — Cloud Function cukup menerima block dari body request.

---

### Yang Berubah dalam Kode untuk Opsi B

Perubahan berikut dilakukan di v0.9 dibandingkan implementasi v0.7. Semuanya sudah selesai.

**`patcher_local.py` — diperluas untuk membaca dan mengirim block:**

- Sebelum memanggil Cloud Function, terhubung ke PostGIS lokal kontraktor
- Query tabel `canopysense.blocks` — baca `block_id`, `code`, `name`, dan `geometry` (sebagai GeoJSON)
- Serialize hasilnya sebagai GeoJSON FeatureCollection
- Sertakan dalam body POST request berdampingan dengan header API key

**`patcher_cloud_function.py` — terima block dari body request:**

- Parse GeoJSON FeatureCollection dari body request
- Teruskan ke `engine_launcher` alih-alih membiarkan engine membaca dari database
- Hapus environment variable `PGHOST`/`PGPORT`/`PGDATABASE` dari Cloud Function — Cloud Function tidak lagi butuh koneksi database apa pun

**`engine_launcher.py` — terima block sebagai parameter:**

- `run_pipeline()` menerima GeoDataFrame yang sudah dimuat (block) sebagai parameter alih-alih memanggil `_load_blocks_from_db()`
- Koneksi DB di dalam engine tidak lagi dibutuhkan untuk pemuatan block

**Yang TIDAK berubah:**

- Alur validasi API key — identik
- Logika pemrosesan GEE — identik
- Hasil yang dikembalikan sebagai JSON ke `patcher_local.py` — identik
- Penulisan hasil `patcher_local.py` ke PostGIS kontraktor — identik
- Schema `canopysense.satellite_data` — identik

---

### Diagram Arsitektur yang Diperbarui (Opsi B)

```
Server Kontraktor                                Google Cloud
──────────────────────────────    ──────────────────────────────────────────
                                  │                                         │
  [PostGIS Kontraktor]            │                                         │
    canopysense.blocks            │                                         │
        ↓ Langkah 1: baca blocks  │                                         │
  [patcher_local.py]              │                                         │
        ↓ Langkah 2: POST request │                                         │
        ──── API key + GeoJSON ──→ [Cloud Function: patcher_cloud]          │
                                       ↓ validasi key (Secret Manager)      │
                                       ↓ muat GeoJSON dari body request     │
                                       ↓ ambil kredensial GEE (Secret Mgr)  │
                                       ↓ jalankan pipeline GEE ──────────→ [Google Earth Engine]
                                       ↓ terima hasil ←────────────────
                                       ↓ kembalikan JSON response
        ←── results JSON ─────────────
        ↓ Langkah 3: tulis hasil
  [PostGIS Kontraktor]
    canopysense.satellite_data
──────────────────────────────
```

Cloud Function sekarang tidak memiliki koneksi database keluar sama sekali. Ia hanya membaca dari Secret Manager (inbound) dan memanggil Google Earth Engine.

---

## Skenario 4: Upload Trigger Real-Time (Alur User Baru)

Tiga skenario di atas mengasumsikan pipeline berjalan terjadwal atau dipicu secara manual oleh kontraktor. Ada skenario keempat yang membutuhkan penanganan berbeda:

> **Seorang user kontraktor baru membuat akun, mengunggah shapefile melalui fitur upload aplikasi, dan mengharapkan pipeline data satelit berjalan segera — tidak menunggu siklus terjadwal berikutnya.**

Ini adalah trigger berbasis event, bukan terjadwal. User sedang aktif menunggu hasilnya. Strategi retry harus berbeda.

---

### Cara Kerja Alur Real-Time

```
Tindakan User              Server Kontraktor                Google Cloud
───────────────    ────────────────────────────────    ──────────────────────
                   │                                  │
  [Upload SHP] →  [Data-Parser]                       │
                       ↓ standardisasi geometri        │
                       ↓ tulis ke canopysense.blocks   │
                   [PostGIS]                           │
                       ↓ trigger event                 │
                   [patcher_local.py]                  │
                       ↓ baca blocks                   │
                       ──── POST (API key + GeoJSON) → [Cloud Function]
                       ←── results JSON ───────────────
                       ↓ tulis ke satellite_data
                   [PostGIS]
                       ↓
                   [Aplikasi notifikasi ke user: data siap]
───────────────────────────────────────────────────────
```

**Perbedaan utama dari scheduled run:**
Dalam scheduled run, kegagalan berarti "coba lagi minggu depan." Dalam upload trigger real-time, kegagalan berarti "user sedang menatap layar loading." Retry logic harus lebih cepat, lebih cerdas, dan terlihat oleh user.

---

### Desain Retry Loop untuk Real-Time Trigger

Retry loop harus menangani tiga kategori kegagalan secara berbeda:

**Kategori 1 — Kegagalan sementara (aman untuk langsung dicoba ulang)**
Ini adalah masalah temporer yang biasanya selesai dalam hitungan detik atau menit:

- Network timeout antara server kontraktor dan Cloud Function
- Ketidaktersediaan Google Earth Engine sementara
- Penundaan cold start Cloud Function

Strategi retry: **exponential backoff**

```
Percobaan 1 → tunggu 30 detik → Percobaan 2 → tunggu 60 detik → Percobaan 3 → tunggu 120 detik → menyerah
```

Total window retry: sekitar 3,5 menit sebelum menyatakan gagal. Ini masih bisa diterima untuk alur upload user.

**Kategori 2 — Kegagalan deterministik (JANGAN dicoba ulang — perbaiki dulu)**
Ini akan gagal setiap saat terlepas dari berapa kali dicoba ulang:

- `403 Forbidden` — API key tidak valid atau sudah dicabut
- `401 Unauthorized` — API key tidak ada di `.env`
- Tabel blocks kosong — data-parser gagal menulis block
- Schema tidak cocok — struktur DB kontraktor tidak sesuai format yang diharapkan

Strategi retry: **langsung gagal, beri notifikasi user dengan pesan error yang spesifik.** Mencoba ulang hal ini hanya buang waktu dan membingungkan user.

**Kategori 3 — Kegagalan parsial (retry idempoten aman dilakukan)**

- Cloud Function mengembalikan hasil tapi `patcher_local.py` gagal menulis ke PostGIS di tengah jalan
- Sebagian block sudah ditulis, sebagian belum

Strategi retry: **ulangi full request dengan aman.** Karena penulisan menggunakan `ON CONFLICT DO NOTHING`, block yang sudah ditulis otomatis dilewati. Tidak ada duplikat yang dibuat. Retry secara efektif melanjutkan dari titik yang terhenti.

---

### Tabel Perilaku Retry Loop

| Jenis Kegagalan         | HTTP Code | Retry? | Tunggu Sebelum Retry | Maks Percobaan | Pesan ke User                                         |
| ----------------------- | --------- | ------ | -------------------- | -------------- | ----------------------------------------------------- |
| Network timeout         | —         | Ya     | 30d, 60d, 120d       | 3              | "Memproses — mencoba lagi..."                         |
| GEE tidak tersedia      | 500       | Ya     | 60d, 120d            | 2              | "Layanan satelit sibuk — mencoba lagi..."             |
| API key tidak valid     | 403       | Tidak  | —                    | 0              | "Akses ditolak — hubungi administrator"               |
| API key dicabut         | 403       | Tidak  | —                    | 0              | "Akses dicabut — hubungi administrator"               |
| API key tidak ada       | 401       | Tidak  | —                    | 0              | "Error konfigurasi — hubungi administrator"           |
| Penulisan PostGIS gagal | —         | Ya     | 10d                  | 2              | "Menyimpan data — mencoba lagi..."                    |
| Semua retry habis       | —         | Tidak  | —                    | —              | "Pemrosesan gagal — dijadwalkan untuk run berikutnya" |

---

### Yang Terjadi Ketika Semua Retry Habis

Job yang gagal tidak boleh hilang begitu saja. Dua hal harus terjadi:

**1. User diberi notifikasi**
Aplikasi menampilkan pesan yang jelas menjelaskan bahwa run tidak berhasil diselesaikan dan akan dicoba ulang secara otomatis pada siklus terjadwal berikutnya. User tidak perlu mengunggah ulang file mereka.

**2. Job masuk antrean untuk scheduled run berikutnya**
Data-parser sudah menulis block ke PostGIS saat upload. Scheduled run `patcher_local.py` berikutnya akan otomatis mengambil block tersebut dan memprosesnya. Tidak ada data yang hilang — hanya hasilnya yang ditunda.

Artinya, trigger real-time secara efektif adalah "jalur cepat best effort." Kalau berhasil, user langsung mendapat hasil. Kalau benar-benar gagal, scheduled run berfungsi sebagai fallback yang terjamin — user hanya menunggu sedikit lebih lama.

---

### Yang Harus Dijamin oleh Data-Parser

Agar Opsi B bekerja dengan andal dalam skenario real-time, data-parser (komponen yang menstandarkan upload shapefile) harus menjamin hal-hal berikut sebelum memicu `patcher_local.py`:

| Jaminan                                                                        | Kenapa Penting                                                               |
| ------------------------------------------------------------------------------ | ---------------------------------------------------------------------------- |
| Semua geometri adalah poligon valid dalam EPSG:4326                            | GEE menolak geometri yang tidak valid atau bukan WGS84                       |
| `block_id` unik per record                                                     | ID duplikat menghasilkan hasil yang duplikat                                 |
| Kolom `geometry` tidak null untuk baris mana pun                               | Geometri null menyebabkan GEE gagal secara diam-diam                         |
| Penulisan `canopysense.blocks` sepenuhnya committed sebelum trigger dijalankan | `patcher_local.py` tidak boleh membaca tabel yang baru setengah ditulis      |
| Schema cocok persis dengan DDL `canopysense.blocks`                            | Kolom yang tidak cocok menyebabkan pipeline gagal di langkah pembacaan block |

Data-parser adalah lini pertahanan pertama. Kalau ia menjamin data yang bersih, pipeline di hilir tidak punya kejutan yang perlu ditangani.

---

*CanopySense REAL_SCENARIO_WORKFLOW_ID.md — v1.2 — 2026-04-25*

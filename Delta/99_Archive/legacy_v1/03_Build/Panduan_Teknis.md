# CanopySense Patcher-Local — Panduan Operasional

**Versi:** v0.9 | **Pembaca:** Staf Operasional dari pihak Kontraktor (Dasmap) dan Administrator (UI)
**Terakhir Diperbarui:** 2026-04-21

> Panduan ini mencakup semua yang perlu diketahui untuk men-deploy, menjalankan, dan troubleshooting sistem CanopySense Patcher-Local.

---

## Daftar Istilah

| Istilah               | Penjelasan Sederhana                                                                                                         |
| --------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| **Patcher-Local**     | Program kecil di server yang menghubungi cloud CanopySense untuk meminta pemrosesan data satelit                             |
| **Patcher-Cloud**     | Sistem pemrosesan CanopySense yang berjalan di Google Cloud                                                                  |
| **Cloud Function**    | Layanan yang berjalan di Google Cloud yang memproses citra satelit sesuai permintaan                                         |
| **API Key**           | Kata sandi rahasia yang membuktikan bahwa server berwenang menggunakan sistem — bersifat unik untuk setiap organisasi        |
| **PostGIS**           | Database lokal tempat hasil pemrosesan satelit disimpan                                                                      |
| **Secret Manager**    | Brankas aman milik Google untuk menyimpan API key dan rahasia konfigurasi                                                    |
| **`.env` file**       | File teks biasa di server lokal yang menyimpan konfigurasi dan kredensial                                                    |
| **403 Forbidden**     | Error yang berarti API key ditolak — entah tidak valid, sudah dicabut, atau kedaluwarsa                                      |
| **401 Unauthorized**  | Error yang berarti tidak ada API key yang dikirimkan dalam request                                                           |
| **Revocation**        | Menonaktifkan API key agar tidak bisa lagi mengakses sistem                                                                  |
| **Cloud Logging**     | Sistem log milik Google Cloud — tempat semua aktivitas CanopySense dicatat                                                   |
| **IAM Role**          | Izin di Google Cloud yang memperbolehkan sebuah layanan melakukan sesuatu                                                    |
| **CONTRACTOR_ID**     | Label unik yang ditetapkan administrator untuk mengidentifikasi setiap kontraktor (misalnya `DASMAP`)                        |
| **API Key Registry**  | File JSON yang disimpan di Secret Manager yang berisi daftar semua kontraktor, hash key mereka, dan statusnya                |
| **SHA-256 Hash**      | Sidik jari satu arah dari API key — registry hanya menyimpan ini, bukan key aslinya                                          |
| **IP Whitelist**      | Daftar opsional alamat IP yang diizinkan untuk kontraktor tertentu — request dari IP lain otomatis diblokir                  |
| **Onboarding**        | Proses mendaftarkan kontraktor baru ke dalam sistem dan menerbitkan API key untuk mereka                                     |
| **canopysense_audit** | User PostgreSQL read-only yang dibuat di server kontraktor — memungkinkan administrator memverifikasi data tanpa akses tulis |
| **Kontraktor**        | Dalam hal ini adalah Dasmap, selaku pengembang server aplikasi riset project CanopySense                                     |
| **Administrator**     | Pihak yang memelihara dan memperbaiki sistem di sisi Cloud. Dalam hal ini adalah pihak UI                                    |

---

## Bagian A: Onboarding Kontraktor (Alur Kerja Administrator)

Bagian ini diperuntukkan bagi **administrator CanopySense** — orang yang mengelola API key dan menyetujui akses kontraktor. Kontraktor tidak perlu membaca bagian ini.

---

### A.0 Langkah 1 — Kumpulkan Informasi dari Developer Server Kontraktor

Sebelum bisa menerbitkan API key, developer server kontraktor harus menyediakan hal-hal berikut. Kirimkan checklist ini dan jangan lanjutkan sebelum semua item dikonfirmasi.

**Informasi yang perlu diminta dari kontraktor:**

| #   | Apa yang Diminta                                        | Kenapa Dibutuhkan                                                                                        | Wajib?   |
| --- | ------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- | -------- |
| 1   | **Nama organisasi**                                     | Digunakan untuk membuat `CONTRACTOR_ID` unik mereka (misalnya `DASMAP`)                                  | Wajib    |
| 2   | **Nama + email kontak teknis**                          | Untuk pengiriman API key yang aman dan eskalasi insiden                                                  | Wajib    |
| 3   | **Sistem operasi server**                               | Harus Linux atau macOS — Windows tidak didukung untuk `patcher_local.py`                                 | Wajib    |
| 4   | **Versi Python yang terpasang di server**               | Harus Python 3.8 atau lebih baru                                                                         | Wajib    |
| 5   | **Versi PostgreSQL yang terpasang**                     | Harus PostgreSQL 12 atau lebih baru dengan ekstensi PostGIS aktif                                        | Wajib    |
| 6   | **Konfirmasi bahwa schema canopysense sudah disiapkan** | Menjalankan DDL script CanopySense sebelum data bisa ditulis                                             | Wajib    |
| 7   | **Alamat IP publik server atau CIDR range**             | Opsional tapi disarankan — ditambahkan sebagai IP whitelist untuk keamanan berlapis                      | Opsional |
| 8   | **Jadwal run yang diinginkan**                          | Ini menentukan cara mengkonfigurasi cron job                                                             | Opsional |
| 9   | **Kredensial database read-only**                       | Host, port, nama database, dan username + password read-only agar bisa memverifikasi data secara mandiri | Wajib    |

> **Catatan tentang poin 9:** Hanya dibutuhkan akses read-only bagi tim UI — bukan akses admin, bukan akses tulis. Kontraktor membuat user audit khusus yang hanya bisa menjalankan query `SELECT` pada tabel `canopysense.satellite_data`. Ini adalah praktik standar dalam integrasi data B2B. Lihat Langkah 8 di bawah untuk SQL persis yang perlu dijalankan kontraktor.

---

### A.0 Langkah 2 — Yang Perlu diLakukan Setelah Mendapat Informasi

Setelah developer server kontraktor mengonfirmasi semua item yang diperlukan, selesaikan langkah-langkah ini secara berurutan:

**Langkah 1: Tetapkan Contractor ID**

Pilih identifikasi unik untuk kontraktor ini. Gunakan format berikut:

```
CONTRACTOR_<ORGANISASI>_<REGION_OPSIONAL>
```

Contoh: `DASMAP`, `CONTRACTOR_BETA_SUMATRA`

---

**Langkah 2: Buat API Key**

Jalankan perintah ini di terminal untuk menghasilkan key acak yang aman:

```bash
openssl rand -hex 32
```

Contoh output:

```
a3f8c2d1e9b74f6a2c5d8e1f3b9a7c4d6e2f8a1b3c5d7e9f1a2b4c6d8e0f2a4
```

Salin nilai ini — dibutuhkan untuk dua langkah berikutnya.

---

**Langkah 3: Hash API Key**

Registry hanya menyimpan hash-nya, bukan key aslinya. Buat SHA-256 hash:

```bash
echo -n "API_KEY_KAMU_DI_SINI" | sha256sum
```

Contoh:

```bash
echo -n "a3f8c2d1e9b74f6a2c5d8e1f3b9a7c4d6e2f8a1b3c5d7e9f1a2b4c6d8e0f2a4" | sha256sum
```

Salin nilai hash (string panjang sebelum spasi dan `-`).

---

**Langkah 4: Tambahkan Kontraktor ke Secret Manager**

Ambil registry yang ada, tambahkan entri kontraktor baru, dan upload kembali:

```bash
# 1. Download registry saat ini ke file sementara
~/google-cloud-sdk/bin/gcloud secrets versions access latest \
  --secret=canopysense-api-key-registry \
  --project=canopysense > /tmp/registry.json

# 2. Buka /tmp/registry.json di text editor dan tambahkan entri baru:
```

Tambahkan blok ini di dalam objek JSON (berdampingan dengan kontraktor yang sudah ada):

```json
"CONTRACTOR_ACME_FARMS": {
    "api_key_hash": "<tempel sha256 hash di sini>",
    "status": "ACTIVE",
    "issued_date": "<tanggal hari ini, misalnya 2026-04-20>",
    "ip_whitelist": ["203.0.113.10/32"],
    "last_used": "<tanggal hari ini>T00:00:00Z"
}
```

Kalau tidak perlu IP whitelist, isi dengan `"ip_whitelist": []`.

```bash
# 3. Upload registry yang sudah diperbarui sebagai versi secret baru
~/google-cloud-sdk/bin/gcloud secrets versions add canopysense-api-key-registry \
  --data-file=/tmp/registry.json \
  --project=canopysense

# 4. Hapus file sementara
rm /tmp/registry.json
```

---

**Langkah 5: Verifikasi Entri Baru Sudah Aktif**

```bash
~/google-cloud-sdk/bin/gcloud secrets versions access latest \
  --secret=canopysense-api-key-registry \
  --project=canopysense | python3 -m json.tool
```

Konfirmasi bahwa entri kontraktor baru muncul dengan `"status": "ACTIVE"`.

---

**Langkah 6: Kirimkan Access Package kepada Kontraktor**

Kirimkan hal-hal berikut melalui **saluran yang aman** (bukan email biasa — gunakan WhatsApp, Signal, atau link shared password manager):

| Item               | Yang Dikirimkan                                                        |
| ------------------ | ---------------------------------------------------------------------- |
| API Key            | Key mentah yang dihasilkan di Langkah 2 (bukan hash-nya)               |
| Contractor ID      | `CONTRACTOR_ID` yang sudah ditetapkan                                  |
| Cloud Function URL | `https://asia-southeast2-canopysense.cloudfunctions.net/patcher_cloud` |
| File               | `patcher_local.py`, `.env.example`, `GUIDANCE.md`                      |

> **Jangan pernah mengirim API key dan Contractor ID dalam pesan yang sama.** Kirim secara terpisah sehingga menyadap satu pesan saja tidak cukup untuk mendapatkan akses.

---

**Langkah 7: Verifikasi Akses Kontraktor (Uji Cepat)**

Setelah kontraktor mengonfirmasi bahwa mereka sudah mengatur `.env` dan menjalankan `patcher_local.py`, verifikasi bahwa panggilan tersebut tercatat di Cloud Logging:

1. Buka [console.cloud.google.com](https://console.cloud.google.com) → project **canopysense**

2. Buka **Logging → Log Explorer**

3. Gunakan filter ini:
   
   ```
   resource.type="cloud_run_revision"
   resource.labels.service_name="patcher-cloud"
   jsonPayload.audit=true
   jsonPayload.contractor_id="CONTRACTOR_ACME_FARMS"
   ```

4. Konfirmasi apakah telah melihat entri `"status": "SUCCESS"` dengan contractor ID mereka dan jumlah `rows=`

Kalau melihat `AUTH_OK` diikuti `SUCCESS` — proses onboarding selesai.

---

**Langkah 8: Minta Akses Database Read-Only dari Kontraktor**

Minta developer server kontraktor untuk menjalankan SQL berikut di server PostgreSQL mereka. Ini membuat user read-only yang akan digunakan untuk memverifikasi data secara mandiri.

**Kirimkan script ini:**

```sql
-- Jalankan ini di server PostgreSQL kontraktor
-- Ganti 'choose_a_strong_password' dengan password yang kuat, lalu bagikan ke admin melalui saluran aman

CREATE USER canopysense_audit WITH PASSWORD 'choose_a_strong_password';
GRANT CONNECT ON DATABASE canopysense TO canopysense_audit;
GRANT USAGE ON SCHEMA canopysense TO canopysense_audit;
GRANT SELECT ON canopysense.satellite_data TO canopysense_audit;
```

Setelah menjalankannya, Kontraktor dapat membagikan (melalui saluran aman):

| Informasi      | Contoh                                  |
| -------------- | --------------------------------------- |
| DB host / IP   | `192.168.1.100` atau `db.acmefarms.com` |
| DB port        | `5432`                                  |
| Nama DB        | `canopysense`                           |
| Audit username | `canopysense_audit`                     |
| Audit password | `choose_a_strong_password`              |

> User ini hanya bisa membaca baris dari `satellite_data`. Tidak bisa mengubah, menghapus, atau mengakses tabel lain. Data operasional kontraktor di luar CanopySense sama sekali tidak terpengaruh.

**Pastikan server PostgreSQL menerima koneksi dari alamat IP.** Kontraktor mungkin perlu memperbarui `pg_hba.conf` atau firewall server untuk mengizinkan mesin terhubung.

---

**Langkah 9: Verifikasi Data Ada di Database Kontraktor**

Setelah mendapatkan kredensial read-only, berarti bisa terhubung langsung ke PostGIS dan mengonfirmasi bahwa datanya telah tersimpan.

**Opsi A — menggunakan psql dari terminal:**

```bash
psql -h <host_kontraktor> -p 5432 -U canopysense_audit -d canopysense
```

Kemudian jalankan:

```sql
-- Hitung total record yang tersimpan
SELECT COUNT(*) AS total_rows FROM canopysense.satellite_data;

-- Tampilkan record terbaru
SELECT
    block_id,
    acquisition_date,
    sensor,
    ROUND(ndvi::numeric, 4) AS ndvi,
    ROUND(cloud_cover::numeric, 2) AS cloud_cover_pct
FROM canopysense.satellite_data
ORDER BY acquisition_date DESC
LIMIT 10;

-- Konfirmasi data diterima dari run terakhir
SELECT MAX(acquisition_date) AS latest_data FROM canopysense.satellite_data;
```

**Opsi B — menggunakan Python dari terminal:**

```bash
python3 - <<'EOF'
import psycopg2, os

conn = psycopg2.connect(
    host="<host_kontraktor>",
    port=5432,
    dbname="canopysense",
    user="canopysense_audit",
    password="<audit_password>"
)
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM canopysense.satellite_data;")
print("Total rows:", cur.fetchone()[0])
cur.execute("SELECT MAX(acquisition_date) FROM canopysense.satellite_data;")
print("Latest acquisition date:", cur.fetchone()[0])
conn.close()
EOF
```

Output yang diharapkan:

```
Total rows: 84
Latest acquisition date: 2026-04-18
```

Kalau `latest acquisition date` dalam 7 hari terakhir dan jumlah barisnya lebih dari nol, pipeline kontraktor berjalan dengan benar.

---

**Checklist Ringkasan Onboarding:**

- [ ] Nama organisasi kontraktor sudah diterima
- [ ] Nama + email kontak teknis sudah diterima
- [ ] OS server sudah dikonfirmasi (Linux/macOS)
- [ ] Python 3.8+ sudah dikonfirmasi
- [ ] PostgreSQL 12+ dengan PostGIS sudah dikonfirmasi
- [ ] Setup schema CanopySense sudah dikonfirmasi oleh kontraktor
- [ ] User audit read-only sudah dibuat oleh kontraktor (`canopysense_audit`)
- [ ] Kredensial DB audit sudah diterima (host, port, dbname, user, password)
- [ ] `CONTRACTOR_ID` sudah ditetapkan
- [ ] API key sudah dibuat (`openssl rand -hex 32`)
- [ ] API key sudah di-hash (`sha256sum`)
- [ ] Registry Secret Manager sudah diperbarui dengan entri baru
- [ ] Registry sudah diverifikasi aktif (entri yang benar menunjukkan `ACTIVE`)
- [ ] Access package sudah dikirim melalui saluran aman (API key dan CONTRACTOR_ID secara terpisah)
- [ ] Kontraktor mengonfirmasi run pertama berhasil
- [ ] Cloud Logging menunjukkan entri `SUCCESS` untuk `CONTRACTOR_ID` mereka
- [ ] Admin sudah memverifikasi data di DB kontraktor menggunakan kredensial read-only (Langkah 9)

---

## Bagian A: Deployment & Setup (Instruksi Kontraktor)

### A.1 Yang Dibutuhkan Sebelum Mulai

Sebelum men-deploy Patcher-Local, pastikan sudah memiliki:

- [ ] Server yang menjalankan Linux atau macOS dengan Python 3.8 atau lebih baru
- [ ] PostgreSQL/PostGIS terpasang dan berjalan secara lokal
- [ ] Tabel `canopysense.satellite_data` sudah dibuat (dari setup Fase 1)
- [ ] `CONTRACTOR_ID` dan `PATCHER_API_KEY` — disediakan oleh administrator
- [ ] `CLOUD_FUNCTION_URL` — disediakan oleh administrator

---

### A.2 Langkah demi Langkah: Pasang Patcher-Local

**Langkah 1: Dapatkan file-nya**

Salin file berikut ke server (disediakan oleh administrator):

```
patcher_local.py
.env.example
```

**Langkah 2: Pasang dependensi Python**

Buka terminal dan jalankan:

```bash
pip install requests python-dotenv psycopg2-binary
```

Output yang diharapkan (baris terakhir):

```
Successfully installed requests-2.31.0 python-dotenv-1.0.0 psycopg2-binary-2.9.0
```

**Langkah 3: Buat file konfigurasi `.env`**

```bash
cp .env.example .env
```

Kemudian buka `.env` di text editor dan isi nilainya:

```
CLOUD_FUNCTION_URL=https://asia-southeast2-canopysense.cloudfunctions.net/patcher_cloud
CONTRACTOR_ID=CONTRACTOR_ID
PATCHER_API_KEY=api_key_kamu_di_sini
PGHOST=localhost
PGPORT=5432
PGDATABASE=canopysense
PGUSER=canopysense_user
PGPASSWORD=password_aman
FUNCTION_TIMEOUT_SECONDS=300
```

> **Penting:** `CLOUD_FUNCTION_URL` di atas sudah tetap — jangan diubah. Ganti hanya `CONTRACTOR_ID`, `PATCHER_API_KEY`, dan kredensial database dengan nilai yang disediakan administrator.

**Langkah 4: Verifikasi `.gitignore` (jika menggunakan git)**

Pastikan `.env` tercantum di file `.gitignore`. Kalau belum ada, tambahkan:

```bash
echo ".env" >> .gitignore
```

---

### A.3 Setup IAM Role yang Diperlukan (Tugas Administrator)

> **Langkah ini sudah selesai untuk deployment saat ini.** Catatan di bawah hanya untuk referensi jika sistem pernah di-deploy ulang ke project Google Cloud yang baru.

Cloud Function harus memiliki role `roles/secretmanager.secretAccessor`. Tanpa ini, function tidak bisa membaca API key dan akan mengembalikan error 500.

**Detail deployment saat ini (sudah dikonfigurasi):**

- GCP Project: `canopysense`
- Region: `asia-southeast2`
- Service account Cloud Function: `78268232885-compute@developer.gserviceaccount.com`
- Role yang sudah diberikan: `secretmanager.secretAccessor`, `earthengine.writer`, `serviceusage.serviceUsageConsumer`

**Jika men-deploy ulang ke project baru, jalankan:**

```bash
gcloud projects add-iam-policy-binding canopysense \
  --member="serviceAccount:78268232885-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

**Verifikasi role sudah diberikan:**

```bash
gcloud projects get-iam-policy canopysense \
  --flatten="bindings[].members" \
  --filter="bindings.role:roles/secretmanager.secretAccessor" \
  --format="table(bindings.members)"
```

Output yang diharapkan:

```
MEMBERS
serviceAccount:78268232885-compute@developer.gserviceaccount.com
```

---

### A.4 Uji Konektivitas ke Cloud Function

Jalankan perintah ini untuk memverifikasi bahwa server bisa menjangkau Cloud Function:

```bash
curl -s -o /dev/null -w "%{http_code}" \
  -X POST https://asia-southeast2-canopysense.cloudfunctions.net/patcher_cloud \
  -H "Content-Type: application/json"
```

Response yang diharapkan: `401` (tidak ada API key yang disertakan — ini benar dan berarti URL bisa dijangkau)

Kalau melihat `000` atau connection error, periksa pengaturan firewall jaringan.

---

### A.5 Kesalahan Setup yang Umum

| Kesalahan                                | Gejala                                            | Solusi                                                                            |
| ---------------------------------------- | ------------------------------------------------- | --------------------------------------------------------------------------------- |
| API key ada spasi ekstra                 | `403 Forbidden: Invalid API Key`                  | Buka `.env`, periksa tidak ada spasi di sekitar nilai key                         |
| `CLOUD_FUNCTION_URL` salah               | `ConnectionError` atau `404`                      | Salin URL yang tepat dari email setup administrator                               |
| `.env` tidak ada di direktori yang benar | `Missing required environment variable`           | Jalankan `ls .env` — file harus ada di folder yang sama dengan `patcher_local.py` |
| Database tidak berjalan                  | `PostGIS ingestion failed`                        | Jalankan `pg_isready` untuk memeriksa apakah PostgreSQL berjalan                  |
| IAM role tidak ada                       | `500 Internal Server Error: Registry unavailable` | Administrator harus memberikan `roles/secretmanager.secretAccessor` (Bagian A.3)  |

---

## Bagian B: Operasional Normal

### B.1 Cara Memicu Run

Patcher-Local mendukung dua mode trigger:

**Mode 1 — Scheduled Run (semua block, gunakan untuk otomasi rutin/mingguan):**

```bash
cd /path/ke/patcher_local
python3 patcher_local.py
```

Ini memproses semua block di database, dikelompokkan per afdeling. Setiap afdeling adalah satu batch terpisah yang dikirim ke Cloud Function. Kalau ada batch yang gagal, itu dicatat dan otomatis dicoba lagi pada scheduled run berikutnya — tanpa perlu tindakan apa pun.

**Mode 2 — Upload Trigger (satu block, gunakan ketika shapefile baru diunggah):**

```bash
cd /path/ke/patcher_local
python3 patcher_local.py --block-id 42
```

Ganti `42` dengan `block_id` dari block baru tersebut. Ini hanya memproses satu block itu saja secara langsung, tanpa memicu loop scheduled yang penuh.

**Yang akan dilihat pada scheduled run yang berhasil (contoh dengan 2 afdeling):**

```
08:30:01 [INFO]  Run started — mode: scheduled | run_id: a3f8c2d1
08:30:01 [INFO]  Blocks loaded: 41 across 2 batches
08:30:01 [INFO]  Batch 1/2 (afdeling_id=1, 22 blocks, fingerprint=a1b2c3d4) — sending to Cloud Function
08:30:15 [INFO]  Batch 1/2 (afdeling_id=1, ...) — FULL_SUCCESS | rows_inserted=22 | presence_check=22/22 | api_version=1.1
08:30:16 [INFO]  Batch 2/2 (afdeling_id=2, 19 blocks, fingerprint=d4e5f6a7) — sending to Cloud Function
08:30:29 [INFO]  Batch 2/2 (afdeling_id=2, ...) — FULL_SUCCESS | rows_inserted=19 | presence_check=19/19 | api_version=1.1
08:30:29 [INFO]  Run complete — 2/2 FULL_SUCCESS | 0 PARTIAL_SUCCESS | 0 FULL_FAILURE | 0 SKIPPED
```

> **Catatan:** Run pertama setelah jeda lama mungkin membutuhkan waktu 5–10 detik lebih lama dari biasanya. Ini disebut "cold start" — Cloud Function sedang "bangun". Run berikutnya dalam satu jam yang sama akan lebih cepat.

---

### B.2 Cara Memverifikasi Run Berhasil

**Metode 1: Periksa output terminal**

Cari baris ringkasan terakhir. Semua batch seharusnya menunjukkan `FULL_SUCCESS`:

```
[INFO]  Run complete — 2/2 FULL_SUCCESS | 0 PARTIAL_SUCCESS | 0 FULL_FAILURE | 0 SKIPPED
```

`rows_inserted=0` setelah run yang berhasil adalah normal — artinya data sudah ada di database dari run sebelumnya.

**Metode 2: Query database PostGIS**

```sql
-- Hitung total baris di satellite_data
SELECT COUNT(*) FROM canopysense.satellite_data;

-- Tampilkan 5 record yang paling baru diperoleh
SELECT block_id, acquisition_date, sensor, ndvi
FROM canopysense.satellite_data
ORDER BY acquisition_date DESC
LIMIT 5;
```

Kalau `acquisition_date` pada baris terbaru sesuai dengan hari ini (atau dalam 7 hari terakhir), run berhasil.

**Metode 3: Periksa tabel run log**

Setiap batch menulis record status ke `canopysense.patcher_run_log`. Query tabel ini untuk melihat hasil run terakhir:

```sql
SELECT afdeling_id, status, rows_inserted, api_version, triggered_at
FROM canopysense.patcher_run_log
WHERE trigger_mode = 'scheduled'
ORDER BY triggered_at DESC
LIMIT 10;
```

**Arti status di run log:**

| Status            | Artinya                                                                                                                |
| ----------------- | ---------------------------------------------------------------------------------------------------------------------- |
| `FULL_SUCCESS`    | Semua block dalam afdeling ini berhasil diproses                                                                       |
| `PARTIAL_SUCCESS` | Beberapa block berhasil; yang lain gagal (misalnya cloud cover terlalu tinggi pada block tertentu) — akan dicoba ulang |
| `FULL_FAILURE`    | Seluruh batch afdeling gagal (network error, timeout, dll.) — akan dicoba ulang pada scheduled run berikutnya          |
| `SKIPPED`         | Batch dilewati — entah daftar block kosong atau sudah berhasil baru-baru ini                                           |
| `IN_PROGRESS`     | Batch sedang berjalan saat ini (seharusnya hilang dalam beberapa menit)                                                |

---

### B.3 Estimasi Waktu dan Kebaruan Data

| Metrik                                   | Nilai yang Diharapkan                                                  |
| ---------------------------------------- | ---------------------------------------------------------------------- |
| Waktu run tipikal                        | 3–8 menit per batch afdeling                                           |
| Total waktu scheduled run                | Jumlah batch × 3–8 menit (berjalan berurutan)                          |
| Penundaan cold start (panggilan pertama) | +5–10 detik per batch                                                  |
| Kebaruan data                            | Scene satelit dari 7 hari terakhir                                     |
| Baris per run                            | Bervariasi tergantung jumlah block (biasanya 50–200 baris total)       |
| Menjalankan ulang pada data yang sama    | Aman — baris duplikat otomatis dilewati                                |
| Retry batch yang gagal                   | Otomatis — terjadi pada scheduled run berikutnya, tidak perlu tindakan |

---

### B.4 Cara Mengatur Scheduled Run

Untuk menjalankan Patcher-Local secara otomatis setiap minggu, tambahkan ke scheduler cron server:

```bash
crontab -e
```

Tambahkan baris ini untuk menjalankan setiap Senin pukul 06:00:

```
0 6 * * 1 cd /path/ke/patcher_local && python3 patcher_local.py >> /var/log/patcher.log 2>&1
```

Untuk melihat log terjadwal:

```bash
tail -50 /var/log/patcher.log
```

---

### B.5 Di Mana Menemukan Log

| Lokasi Log             | Isinya                                                            |
| ---------------------- | ----------------------------------------------------------------- |
| Output terminal        | Eksekusi Patcher-Local (hanya run saat ini)                       |
| `/var/log/patcher.log` | Semua scheduled run yang lalu (jika cron sudah diatur sesuai B.4) |
| Google Cloud Logging   | Audit trail sisi server — semua panggilan termasuk hasil auth     |

**Untuk melihat Cloud Logging (memerlukan akses Google Cloud Console):**

1. Buka [console.cloud.google.com](https://console.cloud.google.com)

2. Pilih project **canopysense**

3. Navigasi ke **Logging → Log Explorer**

4. Gunakan filter ini:
   
   ```
   resource.type="cloud_run_revision"
   resource.labels.service_name="patcher-cloud"
   jsonPayload.audit=true
   ```

5. Cari entri dengan `CONTRACTOR_ID` di dalamnya

---

## Bagian C: Troubleshooting

### C.1 "Cloud Function mengembalikan 403 Forbidden"

**Artinya:** API key ditolak. Entah key-nya salah, atau sudah dicabut.

**Checklist:**

- [ ] Buka `.env` dan periksa `PATCHER_API_KEY` — tidak ada spasi ekstra, tidak ada tanda kutip di sekitar nilai
- [ ] Pastikan `CONTRACTOR_ID` cocok persis dengan yang ditetapkan administrator
- [ ] Tanyakan administrator apakah API key sudah dicabut (Bagian E)
- [ ] Kalau key baru saja diterbitkan, konfirmasi bahwa telah menyalinnya secara lengkap (key-nya berupa string panjang)

**Contoh Tampilan error-nya:**

```
08:30:01 [INFO] — Calling Cloud Function: https://...
08:30:02 [ERROR] — Cloud Function HTTP error: 403 — {"error": "403 Forbidden: Invalid API Key (contact administrator)"}
```

→ Tindakan: Hubungi administrator.

---

### C.2 "Patcher-Local timeout" atau "FULL_FAILURE" pada Sebuah Batch

**Artinya:** Sebuah batch gagal diproses. Cloud Function membutuhkan waktu terlalu lama, jaringan terputus, atau Cloud Function mengembalikan error.

**Yang terjadi secara otomatis:** Batch yang gagal dicatat di `patcher_run_log` dengan status `FULL_FAILURE`. Pada scheduled run berikutnya, hanya batch yang gagal yang dicoba ulang — batch yang sudah berhasil tidak dijalankan lagi.

**Checklist:**

- [ ] Periksa koneksi internet: `ping 8.8.8.8`

- [ ] Coba tingkatkan timeout di `.env`: `FUNCTION_TIMEOUT_SECONDS=300`

- [ ] Periksa `patcher_run_log` untuk mengonfirmasi afdeling mana yang gagal dan apa penyebabnya:
  
  ```sql
  SELECT afdeling_id, status, error_detail, triggered_at
  FROM canopysense.patcher_run_log
  WHERE status = 'FULL_FAILURE'
  ORDER BY triggered_at DESC LIMIT 5;
  ```

- [ ] Kalau terus gagal, periksa Cloud Logging untuk error sisi server (Bagian B.5)

**Contoh Nyata (output retry backoff v0.9):**

```
08:30:01 [WARN]  Attempt 1 failed (timeout). Retrying in 30s...
08:30:31 [WARN]  Attempt 2 failed (timeout). Retrying in 60s...
08:31:31 [WARN]  Attempt 3 failed (timeout). Retrying in 120s...
08:33:31 [ERROR] Batch 2/3 — FULL_FAILURE after 3 attempts. Recorded for next run.
```

→ Run berlanjut ke batch berikutnya. Batch 2 akan otomatis dicoba ulang pada scheduled run berikutnya.

---

### C.3 "PostGIS ingestion failed"

**Artinya:** Data satelit sudah diterima dari cloud, tapi penulisan ke database lokal gagal.

**Checklist:**

- [ ] Verifikasi PostgreSQL berjalan: `pg_isready -h localhost -p 5432`
- [ ] Periksa kredensial database di `.env` (`PGHOST`, `PGUSER`, `PGPASSWORD`, `PGDATABASE`)
- [ ] Verifikasi tabel `satellite_data` ada: `psql -U your_user -d canopysense -c "\dt canopysense.satellite_data"`
- [ ] Periksa ruang disk: `df -h`

**Contoh Nyata:**

```
[ERROR] — 500 Internal Server Error: PostGIS ingestion failed (reason in logs) — 08P01
```

→ Tindakan: Periksa konektivitas database. `08P01` adalah kode error PostgreSQL 

---

### C.4 Cara Memeriksa Cloud Logging untuk Error Sisi Server

1. Buka [console.cloud.google.com](https://console.cloud.google.com)

2. Pilih project **canopysense**

3. Buka **Logging → Log Explorer**

4. Gunakan filter ini:
   
   ```
   resource.type="cloud_run_revision"
   resource.labels.service_name="patcher-cloud"
   jsonPayload.audit=true
   ```

5. Cari entri dengan `"status": "ENGINE_ERROR"` atau `"status": "TIMEOUT"`

**Tampilan entri audit log yang berhasil:**

```json
{
  "audit": true,
  "timestamp": "2026-04-20T08:30:05Z",
  "contractor_id": "CONTRACTOR_ACME",
  "status": "SUCCESS",
  "detail": "rows=84"
}
```

---

### C.5 Cara Memverifikasi Output Core Engine Secara Manual

Kalau ingin mengonfirmasi data apa yang diproses sebelum sampai ke database:

```sql
-- Periksa acquisition date terbaru di database
SELECT MAX(acquisition_date) AS latest_data FROM canopysense.satellite_data;

-- Periksa data untuk tanggal tertentu
SELECT block_id, sensor, ndvi, evi, cloud_cover
FROM canopysense.satellite_data
WHERE acquisition_date = '2026-04-18'
ORDER BY block_id;
```

Kalau `MAX(acquisition_date)` lebih dari 14 hari yang lalu, ekstraksi mungkin tidak berjalan. Periksa Cloud Logging untuk entri `AUTH_OK` terbaru.

---

## Bagian D: Best Practice Keamanan

> **Aturan-aturan ini melindungi data dan akses organisasi. Pelanggaran dapat mengakibatkan akses tidak sah ke pipeline data satelit.**

### D.1 Aturan yang Harus Diikuti

| Aturan                                                      | Kenapa Penting                                                                                   |
| ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| **Jangan pernah commit `.env` ke git**                      | Mengekspos API key ke siapa saja yang punya akses ke repo                                        |
| **Jangan pernah berbagi API key**                           | Setiap key unik untuk organisasi — berbagi berarti membiarkan orang lain menggunakan kuota akses |
| **Jangan pernah hardcode API key di script**                | Kalau script-nya dibagikan, key pun ikut terekspos                                               |
| **Rotate API key setiap kuartal**                           | Membatasi kerusakan kalau key pernah bocor secara tidak sengaja                                  |
| **Pantau Cloud Logging untuk panggilan yang tidak terduga** | Mendeteksi kalau seseorang menggunakan key tanpa izin                                            |

### D.2 Cara Merotasi API Key

Rotasi berarti mendapatkan key baru untuk menggantikan key yang sekarang:

1. Hubungi administrator dan minta API key baru untuk `CONTRACTOR_ID`
2. Administrator akan menerbitkan key baru dan menandai key lama sebagai REVOKED
3. Perbarui `PATCHER_API_KEY` di file `.env` dengan nilai baru
4. Uji dengan `python patcher_local.py` untuk mengonfirmasi key baru berfungsi
5. Hapus dengan aman semua catatan atau email yang mengandung key lama

> **Tips:** Atur pengingat kalender setiap 3 bulan untuk merotasi key.

### D.3 Yang Harus Dilakukan Jika Key Bocor

1. Hubungi administrator
2. Administrator akan mencabut key lama (berlaku dalam <30 detik)
3. Semua panggilan tidak sah akan langsung mulai menerima `403 Forbidden`
4. Administrator akan menerbitkan key baru
5. Perbarui `.env` dengan key baru dan uji

---

## Bagian E: Kontrol Akses & Revocation

### E.1 Cara Kerja Revocation API Key

Ketika administrator mencabut API key:

- Status key diubah menjadi `REVOKED` di Google Cloud Secret Manager
- Berlaku pada **panggilan berikutnya** — tidak perlu restart atau redeploy
- Semua panggilan berikutnya dari server mengembalikan `403 Forbidden: API Key revoked`

**Contoh Nyata — Yang dilihat setelah revocation:**

```
08:30:01 [INFO] — Calling Cloud Function: https://...
08:30:02 [ERROR] — Cloud Function HTTP error: 403 — 
  {"error": "403 Forbidden: API Key revoked (issued 2026-04-20, revoked 2026-04-25)"}
```

### E.2 Cara Meminta API Key Baru

Jika key hilang, kedaluwarsa, atau dicabut:

1. Hubungi Administrator untuk meminta API Key Baru
2. Administrator akan membuat key baru dan mengirimkannya melalui saluran aman 
3. Perbarui file `.env` dengan nilai baru
4. Uji: `python patcher_local.py`

### E.3 Yang Terjadi pada Data Ketika Key Dicabut

- **Data database yang sudah ada tidak terpengaruh.** Revocation hanya memblokir run ekstraksi di masa depan.
- **Scheduled run akan gagal** (akan mencatat error `403 Forbidden`) sampai key baru dikonfigurasi.
- **Tidak ada data historis yang dihapus.** Tabel `satellite_data` tetap utuh.

---

## Bagian F: Pemulihan Bencana

### F.1 Yang Harus Dilakukan Jika Cloud Function Down

**Tanda-tanda Cloud Function down:**

- `ConnectionError` atau `HTTPError 500` di log
- Cloud Logging tidak menunjukkan entri dalam satu jam terakhir

**Langkah-langkah:**

1. Tunggu 10 menit dan coba lagi (Cloud Function auto-recover dari gangguan sementara)
2. Periksa Google Cloud Status: [status.cloud.google.com](https://status.cloud.google.com)
3. Jika pemadaman berlanjut lebih dari 1 jam, hubungi administrator

**Solusi sementara:** Record `satellite_data`yang sudah tersimpan tetap tersedia untuk analisis. Tidak ada data yang hilang selama pemadaman Cloud Function — hanya run ekstraksi baru yang terblokir.

---

### F.2 Timeline Eskalasi Retry

| Waktu Sejak Kegagalan Pertama                              | Tindakan                                                                                    |
| ---------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| 0–3,5 menit                                                | Patcher-Local otomatis retry dengan backoff (30d → 60d → 120d)                              |
| Setelah 3 kali percobaan gagal                             | Batch ditandai `FULL_FAILURE` di `patcher_run_log`; run dilanjutkan dengan batch berikutnya |
| Scheduled run berikutnya                                   | Batch yang gagal otomatis dicoba ulang — tidak perlu tindakan                               |
| Jika batch yang sama gagal 3+ scheduled run berturut-turut | Periksa Cloud Logging untuk error sisi server; eskalasi ke administrator                    |

**Untuk memaksa retry segera atas semua batch yang gagal tanpa menunggu scheduled run berikutnya:**

```bash
python3 patcher_local.py
```

Script akan mendeteksi entri `FULL_FAILURE` di `patcher_run_log` dan mencoba ulang terlebih dahulu.

---

### F.3 Di Mana Menemukan Backup Log

| Jenis                  | Lokasi                                          |
| ---------------------- | ----------------------------------------------- |
| Log run lokal          | `/var/log/patcher.log` (jika cron sudah diatur) |
| Audit trail sisi cloud | Google Cloud Logging → function `patcher_cloud` |
| Hasil run sebelumnya   | Tabel `canopysense.satellite_data` lokal        |

Untuk mengekspor data satelit 30 hari terakhir sebagai backup:

```sql
COPY (
  SELECT * FROM canopysense.satellite_data
  WHERE acquisition_date >= CURRENT_DATE - INTERVAL '30 days'
) TO '/tmp/satellite_data_backup.csv' WITH CSV HEADER;
```

---

### F.4 Cara Memverifikasi Sistem Sehat Secara Manual

Jalankan pengecekan kesehatan end-to-end ini:

**1. Periksa Python dan dependensi:**

```bash
python --version
python -c "import requests, dotenv, psycopg2; print('Dependencies OK')"
```

Output yang diharapkan: `Dependencies OK`

**2. Periksa koneksi PostGIS:**

```bash
python -c "
import os; from dotenv import load_dotenv; load_dotenv()
import psycopg2
conn = psycopg2.connect(
  host=os.environ['PGHOST'], dbname=os.environ['PGDATABASE'],
  user=os.environ['PGUSER'], password=os.environ['PGPASSWORD']
)
print('PostGIS OK — version:', conn.server_version); conn.close()
"
```

Output yang diharapkan: `PostGIS OK — version: 140001` (atau nomor versi serupa)

**3. Periksa keterjangkauan Cloud Function:**

```bash
curl -s -o /dev/null -w "HTTP Status: %{http_code}\n" \
  -X POST https://asia-southeast2-canopysense.cloudfunctions.net/patcher_cloud \
  -H "Content-Type: application/json"
```

Output yang diharapkan: `HTTP Status: 401` (tidak ada key yang disertakan — ini mengonfirmasi URL berfungsi)

**4. Jalankan Patcher-Local:**

```bash
python patcher_local.py
```

Output yang diharapkan: Baris log terakhir menunjukkan `Patcher-Local complete.`

---

## Lampiran: Referensi Cepat

```
┌─────────────────────────────────────────────────────────┐
│           CANOPYSENSE PATCHER-LOCAL QUICK REF v0.10      │
├─────────────────────────────────────────────────────────┤
│ Scheduled run (semua block):                            │
│   python3 patcher_local.py                              │
│                                                         │
│ Upload trigger (satu block):                            │
│   python3 patcher_local.py --block-id 42               │
│                                                         │
│ Cek data DB:     SELECT COUNT(*) FROM                   │
│                  canopysense.satellite_data;             │
│ Cek run log:     SELECT afdeling_id,status,triggered_at │
│                  FROM canopysense.patcher_run_log        │
│                  ORDER BY triggered_at DESC LIMIT 10;   │
│ Cek log:         tail -50 /var/log/patcher.log          │
│                                                         │
│ Error 401 → API key tidak ada di .env                   │
│ Error 403 → API key salah atau dicabut (run berhenti)   │
│ FULL_FAILURE → Otomatis dicoba ulang scheduled run bdk  │
│ PARTIAL_SUCCESS → Block yang hilang dicoba ulang bdk    │
│                                                         │
│ Kontak darurat: administrator                           │
│ Revocation key: berlaku dalam <30 detik                 │
└─────────────────────────────────────────────────────────┘
```

---

*CanopySense Patcher-Local GUIDANCE_ID.md — v0.10 — 2026-04-25*

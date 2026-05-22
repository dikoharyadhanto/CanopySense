# DIRECTOR SETUP PREPARATION
# CanopySense Phase 1 — Panduan Persiapan Infrastruktur Mandiri

**Dokumen ini**: Panduan praktis untuk Director sebelum CDC mulai implementasi.
**Konteks**: Tidak ada server kontraktor. Server utama: IDCloudHost NVME 5 VPS. GCP digunakan untuk patcher-cloud (Cloud Function) dan Cloud Logging saja.
**Target**: Semua item di dokumen ini harus selesai sebelum atau selama Week 1.

---

## Gambaran Arsitektur Phase 1

```
┌─────────────────────────────────────────────────────────────┐
│         IDCloudHost NVME 5 VPS (4 vCPU, 8 GB RAM)          │
│                                                             │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │ PostgreSQL 16    │  │ FastAPI Backend  │                │
│  │ + PostGIS        │  │ (Web App API)    │                │
│  │ (Docker)         │  │ (Docker)         │                │
│  └──────────────────┘  └──────────────────┘                │
│                                                             │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │ Nginx + React    │  │ patcher_local.py │                │
│  │ (Frontend)       │  │ (Cron Job)       │                │
│  │ (Docker)         │  │                  │                │
│  └──────────────────┘  └──────────────────┘                │
└─────────────────────────────────────────────────────────────┘
             │                        │
             ▼                        ▼
┌────────────────────┐   ┌────────────────────────────────────┐
│ GCP Cloud Function │   │ Google Earth Engine                │
│ patcher_cloud.py   │──▶│ (Sentinel-2, Landsat-8/9)          │
│ (sudah ada)        │   │ Sumber citra satelit               │
└────────────────────┘   └────────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────┐
│ GCP Services (semua sudah ada)     │
│ ├── Cloud Logging                  │
│ ├── Secret Manager                 │
│ └── Cloud Function                 │
└────────────────────────────────────┘
```

---

## Estimasi Biaya Phase 1

| Komponen | Biaya/bulan | Keterangan |
| :--- | :--- | :--- |
| IDCloudHost NVME 5 VPS | ~Rp 700.000 | Server utama: semua app container |
| GCP Cloud Function | ~$0 (~Rp 0) | Free tier cukup untuk volume Phase 1 |
| GCP Cloud Logging | ~$0 | Free tier 50GB/bulan |
| GCP Secret Manager | ~$0.10 | Untuk patcher-cloud secrets |
| Domain (.com atau .id) | ~Rp 13.000 | ~Rp150.000/tahun, dicicil bulanan |
| Google Earth Engine | **❓ Perlu dicek** | Lihat Bagian 6 |
| **Total (tanpa GEE komersial)** | **~Rp 715.000/bulan** | Lebih hemat vs GCP VM (~Rp 1.4 juta) |

> **Catatan**: GCP Static IP tidak diperlukan karena server utama sudah di IDCloudHost (punya IP sendiri).
> Backup database: gunakan pg_dump ke Cloud Storage secara manual (lihat Bagian 8).

---

## Bagian 0 — Strategi Infrastruktur Jangka Panjang (Baca Sebelum Segalanya)

> **Ini bukan keputusan Phase 1 saja.** CanopySense akan dikomersilkan ke perusahaan perkebunan besar.
> Keputusan infrastruktur yang salah = biaya operasional yang menggerus margin bisnis selamanya.

### 0.1 — Fakta Kritis: CanopySense Menyimpan Data Sangat Kecil

Banyak yang mengira sistem satelit = menyimpan banyak citra = butuh server besar. **Ini keliru untuk CanopySense.**

**Yang TIDAK disimpan di server:**
Google Earth Engine (milik Google) memproses semua citra satelit di cloud-nya sendiri. Raw Sentinel-2 (100–800 MB per tile) tidak pernah menyentuh server kita.

**Yang BENAR-BENAR disimpan di PostgreSQL:**
Setiap akuisisi satelit, per blok, hanya menghasilkan 1 baris data — 5 angka desimal (indeks vegetasi):

```
block_id | tanggal | sensor | cloud_cover | ndvi | evi | ndre | savi | gndvi
~100 bytes per baris
```

**Kalkulasi volume data nyata:**

| Skala Klien | satellite_data | predictions | Total PostgreSQL |
| :--- | :--- | :--- | :--- |
| 10 perusahaan (100 blok/estate) | ~75 MB | ~30 MB | **< 150 MB** |
| 50 perusahaan | ~375 MB | ~150 MB | **< 1 GB** |
| 100 perusahaan (matang penuh) | ~750 MB | ~300 MB | **< 2 GB** |

Asumsi: 100 blok per estate, 50 akuisisi valid/tahun, 10 tahun historis.

> **Kesimpulan**: Database CanopySense sangat kecil bahkan di skala puluhan klien enterprise.
> Server besar tidak diperlukan untuk volume data ini.

### 0.2 — Analisis Compute Requirements

| Proses | Frekuensi | Beban CPU/RAM |
| :--- | :--- | :--- |
| patcher_local (cron harian) | Harian/mingguan | Rendah — hanya API call ke GEE |
| FastAPI backend | On-demand | Rendah — query data pre-computed |
| Nginx + React frontend | On-demand | Hampir nol |
| Redis (cache/session) | Continuous | 100–500 MB RAM |
| **ML training — Phase 2** | **Batch 1×/minggu** | **Sedang, sementara — selesai 30–120 detik** |
| STL decomposition — Phase 3 | Batch, per alert | Rendah |

Random Forest / XGBoost pada 50.000 baris data (50 klien × 10 tahun) = **selesai dalam 1–2 menit di CPU biasa.** Tidak perlu GPU, tidak perlu server khusus ML.

**Kebutuhan server nyata untuk 50+ klien enterprise:**

| Resource | Kebutuhan | Keterangan |
| :--- | :--- | :--- |
| RAM | 8–16 GB | PostgreSQL + FastAPI + Redis + ML burst |
| CPU | 4 core | Semua proses termasuk ML batch |
| Storage | 100 GB SSD | 50× overkill dari kebutuhan DB; cukup untuk foto lapangan + logs |
| Bandwidth | 10–50 Mbps | patcher GEE calls + user web traffic |

### 0.3 — Perbandingan Model Infrastruktur (Untuk Keputusan Jangka Panjang)

| Model | Biaya Awal | Biaya/Bulan | Total 5 Tahun | Kepemilikan |
| :--- | :--- | :--- | :--- | :--- |
| GCP e2-standard-2 | Rp 0 | ~Rp 900.000 | ~Rp 54.000.000 | Tidak ada |
| VPS Hetzner AX42 (dedicated) | Rp 0 | ~Rp 620.000 | ~Rp 37.000.000 | Tidak ada |
| VPS Biznet Gio Indonesia | Rp 0 | ~Rp 1.500.000 | ~Rp 90.000.000 | Tidak ada |
| **Colocation (owned server)** | **~Rp 10–15 juta** | **~Rp 800.000** | **~Rp 58.000.000** | **Hardware milik sendiri** |

> **Catatan colocation**: Setelah 5 tahun, hardware masih milik Anda. Tambah klien = hampir tidak ada tambahan biaya hingga hardware penuh.
> GCP: setiap klien baru → biaya naik. Margin bisnis tergerus seiring pertumbuhan.

### 0.4 — Satu Dependency yang Tidak Bisa Dihindari: Google Earth Engine

Apapun model server yang dipilih, **GEE tetap di cloud Google.** patcher_cloud memanggil GEE untuk memproses citra satelit — ini tidak bisa dipindahkan ke server sendiri karena GEE adalah layanan eksklusif Google.

```text
[Server owned/colo] ←→ [GEE di GCP] ←→ [Sentinel-2 / Landsat arsip]
PostgreSQL, FastAPI,      Satellite processing
React, Redis, ML          (tidak bisa dipindahkan)
```

Artinya: GEE/Cloud Function tetap butuh akun GCP aktif. Tapi semua komponen lain (database, web app, ML) bisa berjalan di server manapun.

### 0.5 — Rekomendasi Strategis

**Phase 1 (sekarang — 33 hari):** IDCloudHost NVME 5

- Alasan: Lebih hemat (Rp 700.000/bulan vs ~Rp 1.4 juta untuk GCP e2-standard-4), NVMe 6× lebih cepat dari SSD GCP standar, bandwidth unlimited tanpa egress cost. GCP tetap dipakai untuk patcher-cloud (Cloud Function) dan Cloud Logging.

**Phase 2–3 (setelah 3–5 klien nyata):** Evaluasi upgrade ke salah satu:

1. **Upgrade IDCloudHost** ke NVME 7 atau lebih tinggi — cukup 1 klik di panel, IP tidak berubah, downtime minimal.
2. **Colocation di IDC Jakarta** — beli server (Rp 10–15 juta), titip di Biznet DC atau DCI Cibitung. Hardware milik sendiri, biaya flat selamanya.
3. **Dedicated server Hetzner** (jika data sovereignty bukan isu) — spec jauh lebih besar dengan biaya lebih rendah.

**Jangan pertimbangkan:**

- Server di kantor sendiri: tidak profesional untuk produk yang dijual ke perusahaan besar, bergantung PLN dan internet kantor.
- Cloud GPU/high-memory instance: tidak dibutuhkan, ML CanopySense ringan.

---

## Bagian 1 — Daftar & Setup IDCloudHost VPS

**Waktu yang dibutuhkan**: ~20 menit (+ provisioning ~5–10 menit)
**Dilakukan oleh**: Director

### 1.1 — Order IDCloudHost NVME 5

1. Buka [idcloudhost.com](https://idcloudhost.com) dan buat akun atau login
2. Pilih menu **Cloud VPS → Cloud VPS NVMe**
3. Pilih paket **NVME 5**: 4 vCPU, 8 GB RAM, 140 GB NVMe — Rp 700.000/bulan
4. Isi konfigurasi:

   | Field | Nilai |
   | :--- | :--- |
   | OS | Ubuntu 22.04 LTS |
   | Lokasi | Jakarta (Indonesia) |
   | Hostname | `canopysense-phase1` |
   | Password root | Buat password kuat, simpan di tempat aman |

5. Selesaikan pembayaran
6. Cek email untuk IP address dan root credentials (biasanya masuk dalam 5–10 menit)
7. Catat **IP address VPS** — dibutuhkan untuk semua langkah selanjutnya

### 1.2 — Verifikasi Akses SSH

```bash
# Dari terminal lokal Anda:
ssh root@IP_ADDRESS_ANDA
# Jika berhasil masuk ke VPS, langkah ini selesai
```

### 1.3 — Buat Non-Root User (Rekomendasi)

```bash
# Dari dalam VPS (setelah SSH sebagai root):
adduser canopysense
usermod -aG sudo canopysense
su - canopysense
sudo apt update
# Jika berhasil, user canopysense sudah punya sudo access
```

---

## Bagian 2 — Install Docker di VPS

**Waktu yang dibutuhkan**: ~10 menit
**Dilakukan oleh**: Director atau CDC

SSH ke VPS, lalu jalankan perintah berikut:

```bash
# Update package list
sudo apt update && sudo apt upgrade -y

# Install Docker
sudo apt install -y docker.io docker-compose-v2

# Tambahkan user ke group docker (tidak perlu sudo setiap kali)
sudo usermod -aG docker $USER

# Aktifkan Docker berjalan otomatis saat VPS restart
sudo systemctl enable docker
sudo systemctl start docker

# Logout dan login ulang agar group berlaku
exit
```

### Verifikasi

```bash
# SSH ulang ke VPS, lalu:
docker --version
# Output yang diharapkan: Docker version 24.x.x atau lebih baru

docker compose version
# Output yang diharapkan: Docker Compose version v2.x.x
```

---

## Bagian 3 — Setup Networking & Domain

**Waktu yang dibutuhkan**: ~30–60 menit
**Dilakukan oleh**: Director

### 3.1 — Catat IP Address VPS (IDCloudHost)

IDCloudHost VPS sudah memiliki IP address statis secara default — tidak perlu konfigurasi reservasi tambahan.

1. IP address tersedia di email konfirmasi pembelian IDCloudHost
2. Bisa juga dilihat di **Dashboard IDCloudHost → Cloud VPS → detail instance**
3. Catat IP ini — digunakan untuk konfigurasi domain (langkah 3.2) dan untuk patcher-cloud koneksi ke PostgreSQL

### 3.2 — Beli Domain (opsional untuk Phase 1, wajib untuk demo)

Rekomendasi domain murah:
- [Niagahoster](https://www.niagahoster.co.id) — `.com` ~Rp150.000/tahun
- [Hostinger](https://www.hostinger.co.id) — `.com` ~Rp150.000/tahun

Setelah domain dibeli:
1. Masuk ke DNS management panel domain Anda
2. Tambahkan A Record:
   - Name: `@` (atau `canopysense`)
   - Value: IP statis dari langkah 3.1
   - TTL: 300

### 3.3 — Setup Firewall di VPS (UFW)

SSH ke VPS, lalu aktifkan UFW:

```bash
# Izinkan SSH agar tidak terkunci saat UFW aktif
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Port 5432 untuk patcher-cloud (GCP Cloud Function → PostgreSQL IDCloudHost)
# GCP Cloud Function menggunakan IP dinamis, tidak bisa di-whitelist
# Proteksi via strong PostgreSQL password + SSL di Docker Compose
sudo ufw allow 5432/tcp

sudo ufw enable
sudo ufw status
```

> **Catatan Keamanan**: Port 5432 dibuka agar patcher-cloud bisa menulis ke PostgreSQL.
> Pastikan password PostgreSQL menggunakan string acak minimal 32 karakter (lihat Bagian 4).

---

## Bagian 4 — Siapkan Credentials

**Waktu yang dibutuhkan**: ~30 menit
**Dilakukan oleh**: Director

Arsitektur hybrid IDCloudHost + GCP membutuhkan dua set credential:

- **Credential di IDCloudHost VPS** (`.env` file): DB password, JWT secret → digunakan oleh FastAPI + PostgreSQL
- **Credential di GCP Secret Manager**: GEE Service Account, koneksi DB → digunakan oleh patcher-cloud

### 4.1 — Generate Credentials untuk VPS (.env file)

```bash
# Dari terminal lokal — generate random credentials:
DB_PASSWORD=$(openssl rand -base64 32)
JWT_SECRET=$(openssl rand -base64 64)
echo "DB_PASSWORD=$DB_PASSWORD"
echo "JWT_SECRET=$JWT_SECRET"
# Simpan output ini — akan dimasukkan ke .env file di VPS saat setup Docker Compose
```

CDC akan membuat `.env` file di VPS dengan variable ini. Director cukup simpan nilainya di tempat aman.

### 4.2 — Simpan ke GCP Secret Manager (untuk patcher-cloud)

Credential berikut digunakan oleh patcher-cloud (GCP Cloud Function):

| Secret Name | Isi | Status |
| :--- | :--- | :--- |
| `canopysense-gee-service-account` | JSON key GEE Service Account | Sudah ada? |
| `canopysense-gcp-project-id` | GCP Project ID | Sudah ada? |
| `canopysense-db-host` | IP address IDCloudHost VPS | Buat setelah VPS aktif |
| `canopysense-db-password` | Password PostgreSQL (sama dengan .env) | Buat baru |

```bash
# Dari terminal lokal (setelah VPS aktif dan IP tersedia):

# Simpan IP VPS ke Secret Manager
echo "IP_VPS_ANDA" | gcloud secrets create canopysense-db-host \
  --data-file=- \
  --replication-policy="automatic"

# Simpan DB password (sama dengan yang ada di .env VPS)
echo "PASSWORD_ANDA_DISINI" | gcloud secrets create canopysense-db-password \
  --data-file=- \
  --replication-policy="automatic"
```

### 4.3 — Verifikasi

```bash
# Dari terminal lokal:
gcloud secrets versions access latest --secret="canopysense-db-host"
# Jika muncul IP VPS Anda, Secret Manager sudah berisi data yang benar
```

> **Catatan**: IDCloudHost VPS tidak perlu akses ke GCP Secret Manager.
> App secrets (DB password, JWT) disimpan di `.env` file lokal di VPS — lebih sederhana untuk Phase 1.

---

## Bagian 5 — Siapkan Sample Estate Data

**Waktu yang dibutuhkan**: Tergantung data yang tersedia
**Dilakukan oleh**: Director
**Deadline**: Sebelum Week 2 (CDC butuh ini untuk testing peta)

CDC tidak bisa menguji estate map viewer tanpa geometri blok nyata. Ini **blocking** untuk pengembangan frontend.

### Yang Dibutuhkan

| Item | Format | Minimum |
| :--- | :--- | :--- |
| Batas estate (polygon) | GeoJSON atau Shapefile | 1 estate |
| Batas afdeling (polygon) | GeoJSON atau Shapefile | 1–3 afdeling |
| Batas blok (polygon) | GeoJSON atau Shapefile | ≥5 blok |
| Koordinat referensi | Lat/Lon | Lokasi di dalam area perkebunan |

### Catatan

- Jika belum punya data nyata, gunakan **geometri test** — buat 5 poligon persegi di area perkebunan karet mana saja menggunakan [geojson.io](https://geojson.io)
- Format GeoJSON lebih mudah digunakan langsung oleh CDC
- Koordinat harus dalam sistem WGS84 (EPSG:4326)

---

## Bagian 6 — Verifikasi Google Earth Engine Access

**Waktu yang dibutuhkan**: ~30 menit
**Dilakukan oleh**: Director
**Prioritas**: TERTINGGI — lakukan di hari pertama Week 1

GEE adalah sumber semua data satelit. Jika GEE tidak bisa diakses, patcher tidak bisa berjalan.

### 6.1 — Cek Status GEE Account

1. Login ke [earthengine.google.com](https://earthengine.google.com)
2. Pastikan akun Anda masih **approved** dan aktif
3. Cek apakah ada email dari Google tentang quota atau perubahan kebijakan

### 6.2 — Test GEE dari Cloud Function

```python
# Buat Cloud Function test sederhana atau jalankan patcher_cloud_function.py
# dengan satu blok test untuk verifikasi GEE quota masih aman

import ee
ee.Initialize()
image = ee.Image('COPERNICUS/S2_SR/20230101T030551_20230101T031549_T48MYT')
print(image.getInfo())  # Jika berhasil, GEE aktif
```

### 6.3 — Pertanyaan Kritis: GEE Lisensi Komersial

Jika CanopySense adalah produk yang **dijual ke perusahaan perkebunan** (bukan riset/akademik):
- GEE mensyaratkan **Commercial License**
- Harga tidak dipublikasikan, perlu kontak Google langsung
- Link pendaftaran: [earthengine.google.com/commercial](https://earthengine.google.com/commercial)

Untuk Phase 1 testing internal: kemungkinan masih masuk free tier. Tapi konfirmasi ini sebelum demo ke forum bisnis.

---

## Bagian 7 — Checklist Kesiapan (Verifikasi Sebelum CDC Mulai)

Tandai semua item ini **SEBELUM** CDC memulai Week 1:

### Infrastruktur

- [ ] IDCloudHost NVME 5 VPS aktif dan bisa di-SSH
- [ ] Docker dan Docker Compose terinstall di VPS
- [ ] Port 80, 443, dan 5432 terbuka di UFW (VPS)
- [ ] IP address VPS sudah dicatat
- [ ] Domain sudah diarahkan ke IP VPS (opsional untuk Phase 1)

### Credentials & Access

- [ ] DB password dan JWT secret disiapkan (dicatat untuk .env file di VPS)
- [ ] `canopysense-db-host` (IP VPS) tersimpan di GCP Secret Manager
- [ ] `canopysense-db-password` tersimpan di GCP Secret Manager
- [ ] GEE Service Account JSON key tersimpan di GCP Secret Manager
- [ ] CDC developer punya SSH access ke VPS

### Data & GEE

- [ ] GEE account aktif dan bisa diakses
- [ ] Test GEE request berhasil dari Cloud Function
- [ ] Sample estate geometry tersedia (minimal GeoJSON 1 estate, 5 blok)
- [ ] Koordinat sample estate berada di area perkebunan yang valid

### Dokumentasi untuk CDC

- [ ] CDC sudah menerima SSH key atau akses ke VPS
- [ ] CDC sudah menerima nama-nama secret di Secret Manager (untuk patcher-cloud)
- [ ] CDC sudah menerima sample estate GeoJSON file
- [ ] CDC sudah membaca `Panduan_Teknis.md` dan `GUIDANCE.md`

---

## Bagian 8 — Maintenance Rutin Setelah Phase 1 Live

### Harian (~5 menit)

```bash
# Cek Cloud Logging untuk patcher errors
gcloud logging read "resource.type=cloud_function AND severity>=ERROR" \
  --limit=10 \
  --format="table(timestamp, textPayload)"
```

Atau cek via GCP Console → Cloud Logging → query `severity>=ERROR`.

### Mingguan (~15 menit)

```bash
# SSH ke VPS, cek disk usage
df -h
# Jika /dev/sda1 di atas 80%, segera bersihkan atau tambah disk

# Cek Docker containers masih berjalan
docker compose ps
# Semua container harus status "Up"

# Cek log container terakhir
docker compose logs --tail=50 fastapi
docker compose logs --tail=50 postgres
```

### Bulanan (~30 menit)

```bash
# Backup database manual ke Cloud Storage
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
docker exec canopysense-postgres pg_dump -U postgres canopysense_phase1 \
  | gzip > /tmp/backup_$TIMESTAMP.sql.gz

gsutil cp /tmp/backup_$TIMESTAMP.sql.gz gs://BUCKET_ANDA/backups/

# Update OS security patches
sudo apt update && sudo apt upgrade -y
```

---

## Bagian 9 — Limitasi yang Harus Diterima di Phase 1

| Limitasi | Penjelasan | Mitigasi |
| :--- | :--- | :--- |
| **Single point of failure** | Jika VPS mati, semua mati | Restart otomatis dikonfigurasi di Docker Compose; IDCloudHost SLA 99.9% |
| **Backup manual** | Tidak ada backup otomatis dengan self-hosted PostgreSQL | Jalankan backup mingguan ke Cloud Storage; pertimbangkan Cloud SQL di Phase 2 |
| **Data tidak real-time** | Satellite data masuk sesuai jadwal patcher, bukan instan | Normal untuk sistem pre-computed; Sentinel-2 revisit 5 hari |
| **Cloud cover tropis** | Banyak akuisisi satelit di daerah tropis tertutup awan | Gunakan Landsat sebagai backup; tandai akuisisi berawan di database |
| **Single company** | Phase 1 hanya untuk 1 perusahaan demo | Didesain seperti ini; multi-tenant di Phase 2+ |
| **Tidak ada alerting** | Jika patcher diam-diam gagal, tidak ada notifikasi otomatis | Cek Cloud Logging harian secara manual; automated alerting di Phase 2 |
| **Cross-cloud latency** | patcher-cloud (GCP) menulis ke PostgreSQL di IDCloudHost via internet | Payload sangat kecil (5 float per baris); latency ~10–50ms tidak berpengaruh pada data correctness |
| **Skalabilitas terbatas** | NVME 5 cukup untuk demo dan early clients; perlu upgrade untuk 10+ perusahaan serentak | Upgrade ke NVME 7+ di Phase 2 — cukup 1 klik di panel IDCloudHost, IP tidak berubah |

---

## Ringkasan: Urutan Prioritas Persiapan

```
MINGGU INI (sebelum CDC mulai):
  1. Daftar & aktifkan IDCloudHost VPS       → Bagian 1
  2. Install Docker di VPS                   → Bagian 2
  3. Verifikasi GEE access                   → Bagian 6  ← PALING KRITIS
  4. Siapkan credentials (.env + Secret Manager) → Bagian 4
  5. Berikan SSH access ke CDC               → Bagian 7

SEBELUM WEEK 2 (CDC butuh ini untuk frontend):
  6. Siapkan sample estate GeoJSON           → Bagian 5

KAPAN SAJA SEBELUM DEMO:
  7. Setup domain dan SSL                    → Bagian 3
```

---

**Dokumen disiapkan oleh**: Claude Code (ARC)
**Untuk**: Director — Diko Haryadhanto
**Tanggal**: 21 Mei 2026
**Versi**: 1.0 — Phase 1 Infrastructure Guide

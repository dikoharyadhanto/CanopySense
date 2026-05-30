# Manual Testing Guide — TC-021 Director Simulation
## Stage 1.14: Security Hardening + Clean Staging Gate

**Tujuan**: Membuktikan bahwa seluruh alur onboarding dan operasional CanopySense berjalan benar dari baseline staging yang bersih. Ini adalah syarat terakhir sebelum Gate 3 bisa di-lock.

**Estimasi waktu**: 30–45 menit

---

## Prasyarat — Buat File `.env`

Docker Compose membaca variabel dari file `.env` di root project. File ini belum ada, jadi harus dibuat dulu **sebelum** menjalankan `docker compose up`.

Buat file `.env` di root project (sejajar `docker-compose.yml`):

```bash
# Jalankan perintah ini dari root project CanopySense
cat > .env << 'EOF'
PGUSER=postgres
PGPASSWORD=C@n0pyS3ns3_DB#2026!
PGDATABASE=canopysense
REDIS_PASSWORD=R3d1sC@n0py#2026!
SECRET_KEY=8f3a1c9d2e5b7f4a6c0d8e2f3b9a5c7d1e4f6a8b0c2d4e6f8a1b3c5d7e9f0a2b4
ALLOWED_ORIGINS=http://localhost:3000
ENVIRONMENT=development
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
EMAIL_FROM=
DEVICE_TOKEN_EXPIRE_DAYS=90
EOF
```

> Semua nilai di atas diambil dari `secret/credentials.txt`. File `.env` ini **tidak di-commit** ke git (sudah masuk `.gitignore`).

Jalankan stack:

```bash
docker compose up -d
```

Pastikan semua service UP:

```bash
docker compose ps
```

Semua service (`db`, `redis`, `api`, `frontend`) harus berstatus `running`.

Akses aplikasi di:
- **Frontend**: http://localhost:3000
- **API**: http://localhost:8000

---

## Langkah 0 — Jalankan Staging Reset

Langkah ini menghapus semua data operasional (perusahaan, user, data pipeline) dan membuat satu super-admin baru dari nol. Schema database tetap utuh.

Database berjalan di internal Docker network (tidak expose port ke host), jadi **script dijalankan di dalam container `api`** yang sudah punya koneksi ke DB:

```bash
docker compose exec \
  -e RESET_ADMIN_USERNAME=canopy_superadmin \
  -e RESET_ADMIN_PASSWORD='C@n0py$up3r#2026!' \
  api python scripts/staging_reset.py --confirm
```

> Nilai `RESET_ADMIN_USERNAME` dan `RESET_ADMIN_PASSWORD` diambil dari `secret/credentials.txt` bagian `[staging_reset]`. Ganti sesuai keinginan — ini akan menjadi kredensial super-admin pertama.

**Output yang diharapkan:**

```
⚠  Staging reset — ENVIRONMENT=development
   Target: localhost:5432/canopysense (user=<user>)

Truncating operational tables...
  ✓ canopysense.device_otp_sessions
  ✓ canopysense.known_devices
  ✓ canopysense.satellite_data
  ... (semua tabel)
  ✓ public.users

Bootstrapping super-admin: superadmin
  ✓ Super-admin 'superadmin' created

Staging reset complete.
```

**Checkpoint 0**: Database sekarang kosong kecuali satu super-admin.

---

## Langkah 1 — Login sebagai Super-Admin

1. Buka http://localhost:3000/login
2. Masukkan username dan password super-admin yang baru dibuat di Langkah 0
3. Klik **Login**

### Jika muncul Device Verification (OTP)

Karena ini device baru (setelah reset), sistem akan mengirim OTP ke email super-admin. Karena staging belum punya SMTP terkonfigurasi, ada dua opsi:

**Opsi A — Cek OTP langsung dari database (staging only):**

```bash
docker compose exec db psql -U <pguser> -d canopysense -c \
  "SELECT id, user_id, otp_expires_at, used FROM canopysense.device_otp_sessions ORDER BY created_at DESC LIMIT 1;"
```

OTP disimpan sebagai bcrypt hash, jadi tidak bisa dibaca langsung. Gunakan Opsi B.

**Opsi B — Bypass device challenge untuk super-admin pertama kali (staging only):**

```bash
docker compose exec db psql -U <pguser> -d canopysense -c \
  "INSERT INTO canopysense.known_devices (user_id, device_hash, device_label, expires_at)
   SELECT id, 'staging-test-bypass-' || id::text, 'Staging Test Device', NOW() + INTERVAL '90 days'
   FROM public.users WHERE username = 'superadmin';"
```

Setelah itu coba login ulang — device sudah dikenal, tidak akan ada challenge OTP.

**Checkpoint 1**: Berhasil login dan masuk ke halaman `/admin`.

---

## Langkah 2 — Buat Perusahaan Baru

1. Di sidebar admin, klik **Companies** → http://localhost:3000/admin/companies
2. Klik tombol **Create Company** (atau **New Company**)
3. Isi form:
   - **Company Name**: `PT Demo Sawit` (atau nama lain)
   - Field lain sesuai form
4. Submit

**Checkpoint 2**: Perusahaan muncul di daftar companies. Catat `Company ID` dari URL atau daftar (misal: `1`).

---

## Langkah 3 — Invite Manager

1. Klik nama perusahaan yang baru dibuat → masuk ke `/admin/companies/:companyId`
2. Klik tombol **Invite Manager** → masuk ke `/admin/companies/:companyId/invite`
3. Isi email manager (bisa email dummy untuk staging, misal `manager@demo.com`)
4. Submit

**Output yang diharapkan**: Muncul **setup token** yang ditampilkan sekali. Contoh:

```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Salin token ini** — akan dibutuhkan di Langkah 4.

**Checkpoint 3**: Setup token berhasil digenerate dan ditampilkan.

---

## Langkah 4 — First Login Manager (Setup Akun)

1. **Buka tab/window baru** (atau gunakan browser incognito agar sesi tidak tercampur)
2. Buka http://localhost:3000/setup?token=**\<paste_token_di_sini\>**
3. Isi form setup:
   - **Full Name**: `Budi Manager`
   - **Username**: `budimanager`
   - **Password**: Gunakan password kuat (minimal 12 karakter, ada huruf besar, kecil, dan angka/simbol — policy divalidasi server)
   - Contoh: `Manager@Staging1`
4. Submit

**Checkpoint 4**: Akun manager berhasil dibuat. Manager diarahkan ke `/dashboard` atau halaman login.

---

## Langkah 5 — Set Subscription Perusahaan

Kembali ke **sesi super-admin** (tab pertama).

1. Buka http://localhost:3000/admin/companies/:companyId/subscription
2. Pilih tier subscription (misal: `basic`, `premium`, dll.)
3. Simpan

**Checkpoint 5**: Subscription berhasil diset untuk perusahaan.

---

## Langkah 6 — Estate Onboarding

Sebelum pipeline bisa di-trigger, perusahaan harus punya estate dan block data.

1. Buka http://localhost:3000/admin/estate-onboarding
2. Pilih perusahaan yang baru dibuat
3. Buat estate baru:
   - **Estate Name**: `Sembawa Estate`
   - **Estate Code**: `SEMBAWA`
4. Upload file GeoJSON untuk block data (gunakan file test dari `tests/test_blocks.geojson` jika tersedia, atau buat GeoJSON sederhana)
5. Klik **Preview** → verifikasi geometry terdeteksi
6. Klik **Commit**

**Checkpoint 6**: Estate dan block berhasil di-onboard. Data muncul di detail estate.

---

## Langkah 7 — Trigger Pipeline dari Admin UI

1. Buka http://localhost:3000/admin/pipeline/trigger
2. Isi form trigger:
   - **Estate**: Pilih estate yang baru dibuat
   - **Date Range**: Pilih rentang tanggal yang valid (tidak lebih dari 3 tahun, tidak di masa depan)
3. Klik **Trigger**

**Output yang diharapkan**: Job dikirim ke pipeline. Status `SUBMITTED` atau `PROCESSING`.

**Checkpoint 7**: Pipeline trigger berhasil dikirim tanpa error.

---

## Langkah 8 — Konfigurasi Schedule

1. Buka http://localhost:3000/admin/pipeline/schedules
2. Klik **Create Schedule** atau **Add Schedule**
3. Isi:
   - **Estate**: Pilih estate
   - **Cadence**: `weekly` (atau sesuai opsi yang tersedia)
   - **Timezone**: Pilih timezone
4. Simpan

**Checkpoint 8**: Schedule berhasil dibuat dan muncul di daftar jadwal.

---

## Langkah 9 — Verifikasi Isolasi Data Manager

Ini adalah verifikasi kritis untuk multi-tenant isolation (TC-010).

1. **Buat perusahaan kedua** (kembali ke Langkah 2, buat `PT Lain Sawit`)
2. Invite dan setup manager kedua untuk perusahaan ini (`manager2`)

Kemudian **login sebagai `budimanager`** (manager perusahaan pertama):

3. Buka http://localhost:3000/dashboard
4. Verifikasi: hanya data milik `PT Demo Sawit` yang tampil
5. Coba akses langsung URL admin: http://localhost:3000/admin → harus **redirect atau 403**
6. Verifikasi di API secara langsung (opsional):

```bash
# Dapatkan token manager
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -d "username=budimanager&password=Manager@Staging1" \
  -H "Content-Type: application/x-www-form-urlencoded" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Coba akses endpoint admin — harus 403
curl -s -o /dev/null -w "%{http_code}" \
  http://localhost:8000/api/admin/companies \
  -H "Authorization: Bearer $TOKEN"
# Expected: 403
```

**Checkpoint 9**: Manager hanya melihat data perusahaannya sendiri. Akses admin ditolak (403).

---

## Langkah 10 — Cek Audit Log

1. Kembali ke sesi super-admin
2. Buka http://localhost:3000/admin/audit
3. Verifikasi: aksi-aksi yang dilakukan tercatat (invite, trigger, onboarding)

**Checkpoint 10**: Audit log mencatat aksi privileged dengan benar.

---

## Ringkasan Checklist TC-021

| No | Langkah | Status | Catatan |
| :--- | :--- | :--- | :--- |
| 0 | Staging reset berhasil — DB bersih, satu super-admin | ☐ | |
| 1 | Login super-admin berhasil | ☐ | |
| 2 | Perusahaan baru berhasil dibuat | ☐ | |
| 3 | Manager invite — setup token digenerate | ☐ | |
| 4 | Manager first-login + password policy diterima | ☐ | |
| 5 | Subscription berhasil diset | ☐ | |
| 6 | Estate onboarding berhasil (estate + block di-upload) | ☐ | |
| 7 | Pipeline trigger berhasil dikirim | ☐ | |
| 8 | Schedule berhasil dibuat | ☐ | |
| 9 | Manager hanya melihat data perusahaannya; akses admin ditolak | ☐ | |
| 10 | Audit log mencatat aksi privileged | ☐ | |

---

## Setelah Semua Checklist Selesai

Catat di **DEV-EXEC-v1.14.md Section 5 Phase I** (Go/No-Go Synthesis):

- Screenshot atau catatan untuk setiap checkpoint
- Temuan tak terduga (jika ada)
- Tanggal dan kondisi run

Setelah evidence dicatat, informasikan FMN untuk konfirmasi Gate 3 lock:

```
sigma exec advance complete
sigma exec lock    ← membutuhkan persetujuan FMN terlebih dahulu
```

---

## Troubleshooting Umum

**`docker compose up` gagal — environment variable tidak terbaca:**
Pastikan file `.env` sudah dibuat di root project (lihat bagian Prasyarat). Cek dengan:
```bash
cat .env
```
Jika kosong atau tidak ada, buat ulang sesuai instruksi Prasyarat.

**Login gagal setelah reset:**
Pastikan container API sudah restart setelah reset (pool connection mungkin masih stale):
```bash
docker compose restart api
```

**Password ditolak saat setup manager:**
Password harus memenuhi policy: minimal 12 karakter, ada huruf besar, huruf kecil, dan minimal satu angka atau karakter spesial.
Contoh valid: `Manager@Staging1`

**OTP tidak diterima via email:**
Konfigurasi SMTP belum diset di staging. Gunakan Opsi B di Langkah 1 untuk bypass device challenge via psql langsung.

**Frontend tidak bisa diakses:**
```bash
docker compose logs frontend --tail=20
```

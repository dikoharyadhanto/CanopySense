# Audit UI/UX Halaman Admin — CanopySense

## Scope Audit

Dokumen ini hanya membahas **halaman admin** CanopySense, dimulai dari checkpoint audit admin. Audit halaman user/manager sebelumnya tidak diulang di sini.

Baseline audit:

- fokus pada kontrol operasional admin,
- validasi data estate/geospasial,
- approval/rejection workflow,
- pencegahan kesalahan fatal,
- audit trail dan accountability,
- pipeline execution dan cost awareness,
- role/permission clarity,
- konsistensi model data saat ini.

Asumsi produk yang digunakan dalam audit ini:

- Sistem bersifat multi-tenant: satu **company/organization** adalah satu tenant.
- Random user yang register/login sendiri tidak otomatis mendapat data. Ia harus mendapat undangan dari manager agar masuk ke company tertentu.
- Untuk fase development saat ini, company dibuat manual oleh admin/superadmin.
- Saat ini model estate adalah **satu company memiliki satu estate aktif pada satu waktu**.
- Estate lama tidak langsung hilang saat estate baru diterapkan; estate lama menjadi inactive melalui soft delete/retention sekitar 30 hari.
- Block adalah unit polygon terkecil. Setiap polygon dianggap sebagai block.
- `block_code` dibuat otomatis oleh sistem, bukan field wajib dari file upload.
- Pipeline sudah memiliki mekanisme skip-existing/idempotent: data yang sudah tersimpan tidak diekstraksi ulang.

---

# Executive Summary

Fondasi halaman admin sudah cukup lengkap: ada dashboard, companies, audit log, pipeline trigger/history/schedules, estate onboarding, admin users, data viewer, estate change requests, registrations, dan system settings.

Masalah utamanya bukan kelengkapan fitur, tetapi **kejelasan risiko, status operasional, dan permission boundary**. Banyak halaman masih terasa seperti CRUD/admin panel biasa, padahal beberapa aksinya berdampak besar:

- mengganti estate aktif,
- mengubah access/subscription plan,
- menjalankan pipeline yang memakai resource cloud,
- mengundang/mencabut akses user,
- membuat admin internal,
- melihat data sensitif via Data Viewer.

Prioritas tertinggi:

1. Dashboard admin harus menunjukkan pekerjaan yang perlu ditangani, bukan hanya statistik.
2. Audit Log harus human-readable, bukan raw event dump.
3. Companies harus menampilkan setup completeness dan access plan dengan jelas.
4. Pipeline harus membedakan manual run, schedule, backfill, no-new-data, dan skipped-existing.
5. Estate Onboarding harus menjadi workflow bertahap dengan validasi yang jelas.
6. Admin Users harus memiliki role/permission guardrail yang kuat.
7. Registrations sebaiknya di-hide atau direvisi karena belum sesuai flow produk saat ini.

---

# Model Operasional yang Harus Konsisten di UI

## Company / Organization

Company adalah tenant utama. Setiap company memiliki:

- branding,
- user manager/viewer,
- satu estate aktif,
- block,
- satellite records,
- access/subscription configuration,
- pipeline schedule/history.

UI harus konsisten memakai istilah. Pilih salah satu sebagai istilah utama:

- Company,
- Organization,
- Perusahaan,
- Organisasi.

Untuk konteks Indonesia dan contoh “Geografi UI”, istilah **Organisasi** lebih fleksibel daripada Perusahaan. Namun jika backend/UI admin tetap menggunakan Company, pastikan tidak bercampur terlalu banyak.

## Role

Struktur role yang dipahami:

```text
Super Admin
  ↓ mengelola semua tenant dan sistem
Company / Organization
  ↓ punya satu active estate
Manager
  ↓ mengelola company-nya sendiri
Viewer
  ↓ read-only access
```

### Super Admin

Role internal CanopySense dengan akses lintas company. Mengelola company, plan, admin users, pipeline, audit log, data viewer, estate change approval, dan system settings.

### Admin

Role internal selain superadmin. Permission-nya perlu diuji dan dibatasi. Jangan tampilkan halaman/action superadmin kalau admin biasa tidak boleh menggunakannya.

### Manager

User dari company. Dapat mengakses dashboard company, mengundang viewer, mengatur branding, mengajukan perubahan estate, melihat data monitoring.

### Viewer

User read-only. Hanya melihat data monitoring setelah menerima undangan dari manager.

## User tanpa Company

Random user yang register/login sendiri harus diperlakukan sebagai state khusus:

```text
Akun aktif, tetapi belum tergabung ke organisasi mana pun.
```

Jangan arahkan user tanpa company ke dashboard kosong. UI harus menjelaskan bahwa data hanya tersedia setelah mendapat undangan dari manager.

---

# Audit Admin Dashboard

## Diagnosis

Dashboard admin sudah rapi, tetapi masih terlalu pasif. Saat ini hanya menampilkan:

- Companies,
- Active Managers,
- Subscriptions,
- Recent Admin Actions.

Untuk admin, pertanyaan utama bukan “berapa jumlah company”, tetapi:

> Apa yang butuh keputusan atau tindakan saya sekarang?

## Masalah Utama

### 1. Tidak ada pending workload

Belum terlihat:

- registrasi pending,
- estate change request pending,
- pipeline gagal,
- schedule bermasalah,
- company belum complete setup,
- run terakhir gagal/no new data.

### 2. Recent Admin Actions masih raw backend

Contoh action:

- `update_company`,
- `registration_reject`,
- `registration_approve`,
- `invite_viewer`,
- `remove_member`.

Target juga masih teknis:

- `company #1`,
- `user #10`,
- `registration #4`.

Ini sulit dibaca oleh admin operasional.

### 3. Tidak ada severity

Aksi seperti remove member, update subscription, approve estate change, dan data viewer access tidak boleh terlihat setara.

## Rekomendasi

Tambahkan card:

- Registrasi Pending,
- Estate Change Pending,
- Pipeline Gagal,
- Company Needs Setup,
- Active Schedules,
- Last Pipeline Run.

Tambahkan bagian **Perlu Ditinjau**:

```text
Perlu Ditinjau
- 2 registrasi menunggu approval
- 1 perubahan estate menunggu validasi
- 0 pipeline gagal dalam 24 jam terakhir
```

Recent Actions harus human-readable:

| Actor      | Action           | Target      | Detail               | Time        |
| ---------- | ---------------- | ----------- | -------------------- | ----------- |
| dikohary74 | Mengubah company | Geografi UI | Nama/logo diperbarui | 31 Mei 2026 |

## Prioritas

### Critical

- Tambahkan pending workload.
- Humanize action log.
- Ganti target ID teknis dengan nama entitas.

### Important

- Tambahkan severity/kategori.
- Tambahkan quick action.
- Rapikan grouping sidebar berdasarkan domain kerja.

---

# Audit Companies

## Fungsi

Modul Companies adalah pusat kontrol tenant:

- membuat company secara manual,
- melihat company detail,
- mengatur access/subscription plan,
- melihat estate/block/satellite record count,
- invite/deactivate manager.

Untuk fase awal, **New Company by Admin valid** karena company memang dibuat manual oleh admin/superadmin.

## Masalah Utama

### 1. Companies list terlalu teknis

Tabel menampilkan ID, company name, UUID, created, view. UUID panjang tidak perlu jadi informasi utama.

Yang lebih penting:

- setup status,
- active estate,
- jumlah manager,
- jumlah block,
- access plan,
- status active/inactive.

### 2. Subscription terlalu business-final

Karena model bisnis belum final, label “Subscription” bisa terlalu mengunci. Untuk fase ini, lebih aman memakai:

- Access Plan,
- Service Plan,
- Service Configuration.

### 3. Company detail belum menunjukkan setup completeness

Contoh kondisi Geografi UI:

- Estate: 1,
- Blocks: 46,
- Satellite Records: 0,
- Subscription: Yes.

Perlu status:

```text
Setup Status: Estate ready, satellite data not processed
```

### 4. `Subscription: Yes` terlalu miskin informasi

Lebih baik:

```text
Premium · Active · Yearly · Ends 29 May 2028
```

### 5. Edit Subscription/Plan adalah aksi sensitif

Field seperti tier, status, raster serving mode, timelapse, start/end date berdampak ke akses, cost, dan fitur. Form tidak boleh disimpan tanpa summary dan confirmation.

## Rekomendasi

Companies table:

| Company     | Setup Status       | Plan    | Manager | Active Estate  | Blocks | Created |
| ----------- | ------------------ | ------- | -------:| -------------- | ------:| ------- |
| Geografi UI | Ready for pipeline | Premium | 1       | Sumbawa Estate | 46     | 29 Mei  |

Company detail checklist:

```text
Company created
Manager assigned
Active estate configured
Blocks detected
Access plan active
Pipeline schedule configured
```

Edit Plan harus punya change summary:

```text
Changes to be applied:
- Raster mode: gee_mapid → cloud_tile
- Timelapse period: 3 months → 6 months
- Access end: 2028-05-29 → 2027-05-29
```

## Prioritas

### Critical

- Tambahkan setup status/checklist.
- Ganti `Subscription: Yes` dengan plan/status detail.
- Tambahkan change summary + confirmation pada edit plan.
- Jelaskan deactivate manager sebagai company access atau global account.

### Important

- Pertimbangkan label “Access Plan” dibanding “Subscription”.
- Tampilkan active estate, blocks, manager count di list.
- Tambahkan helper text untuk raster serving mode dan timelapse.

---

# Audit Company / Organization Flow

## Flow yang Dipahami

```text
Super Admin/Admin membuat company secara manual
↓
Admin mengatur access plan/service configuration
↓
Admin mengundang/menetapkan manager
↓
Manager mengelola company tersebut
↓
Manager mengundang viewer
↓
Viewer mendapat data setelah menerima undangan
```

## Risiko UX

Jangan biarkan random user yang belum tergabung company melihat dashboard kosong. Itu bukan state “data kosong”; itu state “belum punya akses organisasi”.

## Rekomendasi UI untuk User Tanpa Company

```text
Anda belum tergabung ke organisasi mana pun

Akun Anda sudah aktif, tetapi belum memiliki akses ke data monitoring CanopySense.
Minta manager organisasi Anda untuk mengirim undangan ke email akun ini.

Email akun:
[user@email.com]

Setelah undangan diterima, dashboard, peta, dan time-series akan tersedia sesuai role Anda.
```

CTA:

- Cek Undangan,
- Refresh Status Akses,
- Logout.

---

# Audit Estate Model dan Soft Delete

## Model Saat Ini

Bukan multi-estate aktif. Model yang tepat:

```text
Company
  └── Active Estate: 1
  └── Inactive/archived estate records: retained temporarily
```

Saat estate baru diterapkan:

- estate aktif lama menjadi inactive,
- estate baru menjadi active,
- estate lama disimpan sementara melalui soft delete/retention sekitar 30 hari.

## Implikasi UI

Hindari label:

- Estates,
- Add Estate,
- Estate List,
- multiple active estate selector.

Gunakan:

- Active Estate,
- Replace Active Estate,
- Import New Estate Version,
- Estate Aktif.

## Copy yang Disarankan

```text
Company ini hanya memiliki satu estate aktif. Jika estate baru disetujui, estate aktif saat ini akan dinonaktifkan dan digantikan oleh estate baru. Data estate lama tidak langsung dihapus, tetapi disimpan sementara sesuai kebijakan retensi.
```

---

# Audit Audit Log

## Diagnosis

Audit Log sudah mencatat event, tetapi tampil seperti dump database/developer log. Untuk admin operasional, ini belum cukup sebagai alat investigasi.

## Masalah Utama

### 1. Action masih raw backend

Contoh:

- `update_company`,
- `registration_reject`,
- `invite_viewer`,
- `remove_member`,
- `data_viewer_table_view`.

### 2. Target terlalu teknis

Target seperti `company #1`, `user #10`, `registration #4` tidak informatif.

### 3. Metadata escaped JSON mentah

Kolom Metadata berisi JSON mentah/escaped. Ini sulit dibaca dan membuat tabel berat.

### 4. Tidak ada filter

Audit log akan cepat besar. Butuh filter:

- actor,
- action type,
- target type,
- company,
- date range,
- severity,
- keyword.

### 5. Tidak ada before/after

Untuk perubahan data penting, audit harus bisa menunjukkan:

```text
company_name: "Geografi UI Updated" → "Geografi UI"
```

## Rekomendasi Table

```text
Time | Actor | Category | Action | Target | Summary | Severity
```

Contoh:

```text
31 Mei 2026, 15:51
Actor: dikohary74
Category: Company
Action: Mengubah company
Target: Geografi UI
Summary: Nama company diubah menjadi “Geografi UI”
Severity: Info
```

Detail drawer:

```text
Event key: update_company
Actor: dikohary74
Target: Geografi UI / company #1
Changed fields:
- company_name: "Geografi UI Updated" → "Geografi UI"
Raw metadata: {...}
```

## Prioritas

### Critical

- Humanize action key.
- Resolve target name.
- Jangan tampilkan escaped JSON mentah di table utama.
- Tambahkan filter minimum.

### Important

- Tambahkan severity/kategori.
- Pisahkan read-only events dari change events.
- Tambahkan detail drawer.
- Simpan before/after untuk event penting.

---

# Audit Pipeline — Trigger Run

## Fungsi

Trigger Run adalah manual execution pipeline. Ini berbeda dari schedule dan backfill.

## Masalah Saat Ini

Halaman sempat mencampur:

- manual trigger,
- scheduled update,
- backfill historical processing.

Scheduled seharusnya bukan mode manual run. Scheduled adalah konfigurasi di halaman Schedules.

## Rekomendasi Label

Ubah:

```text
Scheduled (weekly update)
```

menjadi:

```text
Run latest update now
```

atau:

```text
Latest data run
```

Backfill tetap:

```text
Backfill historical data
```

## Scope

Karena satu company hanya punya satu estate aktif, field Estate jangan menjadi dropdown multi-estate aktif.

Gunakan:

```text
Company: Geografi UI
Active Estate: Sumbawa Estate (read-only)
Scope: Whole estate / Afdeling 1 / Afdeling 2
```

## Run Summary

Sebelum trigger, tampilkan:

```text
Run Summary
Company: Geografi UI
Active Estate: Sumbawa Estate
Scope: Whole estate
Blocks affected: 46
Run type: Latest data run
```

Untuk backfill:

- date range,
- expected scenes,
- blocks affected,
- estimated duration/cost jika ada.

## Confirmation

Pipeline run harus memiliki confirmation modal karena dapat memakai resource cloud.

Backfill harus mendapat warning lebih kuat karena memproses histori.

---

# Audit Pipeline — Run History

## Diagnosis

Saat kosong, halaman hanya menampilkan:

```text
0 total runs
No runs yet.
```

Ini terlalu pasif.

## Empty State yang Disarankan

```text
Belum ada riwayat pipeline

Belum ada pipeline run yang pernah dijalankan untuk company mana pun.
Jalankan pipeline manual atau buat schedule untuk mulai memproses data satelit.
```

CTA:

- Create Schedule,
- Trigger Manual Run.

## Status Penting

Karena backend sudah skip-existing, Run History harus membedakan:

| Status                       | Makna                                          |
| ---------------------------- | ---------------------------------------------- |
| Running                      | Sedang berjalan                                |
| Success — New Data Processed | Data baru berhasil diproses                    |
| No New Data                  | Run berhasil, tidak ada data baru              |
| Skipped Existing Data        | Data sudah pernah diproses, ekstraksi dilewati |
| Partial Success              | Sebagian berhasil, sebagian gagal              |
| Failed                       | Run gagal                                      |

## Kolom yang Disarankan

```text
Status | Company | Active Estate | Scope | Run Type | Result | Started | Duration | Actor
```

Result dapat berisi:

- `No new satellite data found`,
- `3 scenes processed, 46 blocks updated`,
- `Failed during raster extraction`.

---

# Audit Pipeline — Schedules

## Fungsi

Schedules adalah konfigurasi eksekusi berkala. Struktur sudah benar karena dipisah dari Trigger Run.

## Masalah Saat Ini

- Empty state terlalu pasif.
- Copy “Schedules fire while the server is running (staging scheduler)” terdengar terlalu developer-facing.
- Modal masih punya field `Mode: scheduled`, padahal halaman ini memang schedules.
- Estate dropdown memberi kesan multi-estate aktif.
- Cadence daily/weekly/monthly kurang akurat untuk kebutuhan interval 7/10/14/30 hari.
- Default timezone UTC kurang cocok untuk konteks Indonesia.
- Belum ada execution time.
- Belum ada penjelasan skip-existing/cost control.

## Copy Empty State

```text
Belum ada schedule pipeline

Schedule digunakan untuk memeriksa dan memproses data satelit baru secara berkala. Sistem akan melewati data yang sudah pernah diproses, sehingga run tanpa data baru tidak melakukan ekstraksi ulang.
```

## Modal New Schedule yang Disarankan

```text
New Pipeline Schedule

Company
[Geografi UI]

Active Estate
Sumbawa Estate (read-only setelah company dipilih)

Scope
[Whole estate / Afdeling 1 / Afdeling 2]

Update interval
[Every 1 day / Every 7 days / Every 10 days / Every 14 days / Every 30 days / Custom]

Execution time
[02:00]

Timezone
[Asia/Jakarta (WIB)]

Cost control
Pipeline hanya memproses data satelit baru yang belum tersimpan. Jika tidak ada data baru, run akan dicatat sebagai “No New Data”.

[Cancel] [Create Schedule]
```

## Guardrail

Cegah schedule ganda untuk company/scope yang sama kecuali admin memang sengaja membuat cadence tambahan.

Pesan:

```text
Schedule aktif untuk Geografi UI / Whole Estate sudah ada.
Buat schedule baru hanya jika Anda ingin menjalankan cadence tambahan.
```

## Prioritas

### Critical

- Ganti cadence menjadi interval eksplisit.
- Default timezone ke Asia/Jakarta atau timezone company.
- Jelaskan skip-existing.
- Tambahkan status No New Data/Skipped di history.

### Important

- Hapus field Mode dari schedule modal.
- Ubah Estate menjadi Active Estate read-only.
- Tambahkan execution time.
- Tambahkan guardrail duplikasi.

---

# Audit Estate Onboarding

## Fungsi

Estate Onboarding adalah flow untuk membuat/mengganti estate aktif dengan mengimpor boundary block dari file geospasial.

Flow yang dipahami:

```text
Pilih company
↓
Lihat active estate / mulai import estate baru
↓
Upload/import boundary file
↓
Sistem membaca polygon
↓
Admin mapping atribut pendukung
↓
Sistem validasi geometri dan atribut
↓
Preview peta
↓
Apply sebagai active estate
```

## Model Data Penting

- Setiap polygon adalah block.
- `block_code` auto-generated oleh sistem.
- Required mapping seharusnya bukan `block_code`.
- Required mapping yang masuk akal:
  - `block_name`,
  - `afdeling_code`,
  - `afdeling_name`.

## Masalah Utama

### 1. UI masih memberi kesan multi-estate aktif

Label:

```text
Estates — Geografi UI
+ New estate
```

berpotensi membuat admin mengira banyak estate aktif didukung.

Gunakan:

- Active Estate,
- Replace Active Estate,
- Import New Estate Version.

### 2. Company selection kurang status

Company card harus menunjukkan:

- active estate,
- block count,
- setup status,
- pending change jika ada.

### 3. Flow butuh stepper

Untuk operasi data master, perlu stepper:

```text
1. Select Company
2. Create / Replace Estate
3. Upload Boundary File
4. Map Columns
5. Validate Geometry & Attributes
6. Review & Apply
```

### 4. Error mapping terlalu repetitif

Saat mapping belum dipilih, sistem menampilkan 46 invalid rows. Ini menakutkan dan salah framing. Sebelum mapping selesai, tampilkan error level form:

```text
Lengkapi pemetaan kolom wajib terlebih dahulu.
Field yang belum dipetakan:
- block_name
- afdeling_code
- afdeling_name
```

### 5. `block_code` tidak boleh diminta sebagai required upload input

Karena `block_code` auto-generate, validasi tidak boleh menandai row invalid karena `block_code` kosong.

Tambahkan microcopy:

```text
Setiap polygon akan dibuat sebagai satu block. Kode block dibuat otomatis oleh sistem.
```

### 6. Auto-suggest mapping dibutuhkan

Dari preview file ada kolom seperti:

- `BlockID`,
- `Blok`,
- `Afdeling`,
- `AfdelName`,
- `AfdelBlock`.

Sistem bisa menyarankan:

```text
block_name → AfdelBlock
afdeling_code → Afdeling
afdeling_name → AfdelName
```

### 7. Processing note sudah bagus, tapi perlu lebih manusiawi

Saat ini pesan seperti:

```text
File direproject dari EPSG:32748 ke WGS84 (EPSG:4326) secara otomatis.
44 fitur MultiPolygon di-explode menjadi 46 Polygon.
```

Ini bagus. Tambahkan makna operasional:

```text
46 polygon akan dibuat sebagai block.
```

## Copy yang Disarankan

```text
Pemetaan Kolom

Pilih kolom dari file yang berisi informasi block dan afdeling.
Setiap polygon akan dibuat sebagai satu block. Kode block akan dibuat otomatis oleh sistem.
```

Processing:

```text
File berhasil dibaca.
- CRS dikonversi: EPSG:32748 → EPSG:4326
- 44 MultiPolygon dipecah menjadi 46 polygon
- 46 polygon akan dibuat sebagai block
```

## Prioritas

### Critical

- Ubah “Estates” menjadi “Active Estate”.
- Ganti “+ New estate” menjadi “Replace Active Estate” atau “Import New Estate Version”.
- Hapus `block_code` dari required mapping/validation upload.
- Jangan tampilkan row-level invalid errors sebelum required mapping lengkap.
- Tambahkan stepper.

### Important

- Auto-suggest mapping.
- Pisahkan mapping validation vs row validation.
- Tambahkan review step sebelum apply.
- Tambahkan peta preview dalam layout yang lebih dekat dengan validasi.

---

# Audit Admin Users

## Fungsi

Halaman Internal Admin Users mengelola akun admin internal CanopySense.

Ini area high-risk karena berkaitan dengan privilege management.

## Masalah Utama

### 1. Perbedaan Super Admin vs Admin belum eksplisit

Harus jelas apakah Admin bisa:

- membuat company,
- mengubah access plan,
- approve estate change,
- trigger pipeline,
- melihat audit log,
- membuat admin lain,
- mengubah system settings.

### 2. Tombol + New Admin perlu guardrail

Membuat admin internal adalah aksi sensitif. Perlu:

- email,
- name,
- role,
- status invited/active,
- confirmation,
- audit log.

### 3. Admin biasa tidak boleh melihat UI superadmin penuh jika tidak berhak

Jangan hanya mengandalkan frontend. Permission harus enforced di backend.

### 4. Tabel terlalu minim

Perlu tambahan:

- last login,
- created by,
- created at,
- MFA status jika ada,
- actions.

### 5. Super Admin terakhir harus dilindungi

Sistem harus mencegah:

- deactivate superadmin terakhir,
- downgrade superadmin terakhir,
- delete superadmin terakhir.

## Prioritas

### Critical

- Definisikan permission Super Admin vs Admin.
- Enforce permission di UI dan backend.
- Cegah admin biasa mengakses fitur superadmin.
- Cegah deactivate/downgrade Super Admin terakhir.
- Audit semua aksi admin management.

### Important

- Tambahkan last login, created by, actions.
- Tambahkan confirmation modal.
- Tambahkan status invited/suspended/disabled.
- Tampilkan ringkasan role permission.

---

# Audit Data Viewer

## Fungsi

Data Viewer adalah read-only database/table inspection untuk superadmin. Berguna untuk debugging dan verifikasi data fase development.

## Yang Sudah Benar

- Ada copy: read-only inspection.
- Disebut super-admin only.
- Menampilkan table list dan data operasional.

## Masalah Utama

### 1. Data sensitif terlihat

Email, role flag, company_id, status user terlihat. Ini oke hanya jika superadmin-only benar-benar enforced.

### 2. Search terlalu sempit

Placeholder `Search username...` tidak cukup. Harus tergantung tabel:

- Users: search username/email/name,
- Companies: search company name,
- Blocks: search block name/code.

### 3. Horizontal scroll berat

Banyak kolom membuat inspeksi sulit. Perlu sticky key columns.

### 4. Boolean terlalu mentah

`true/false` bisa dibantu dengan badge/status.

### 5. Tidak ada row detail drawer

Admin perlu melihat row panjang secara vertikal.

### 6. Foreign key tidak resolved

`company_id = 2` sebaiknya bisa ditampilkan sebagai:

```text
2 — FMN Approval Test Co
```

## Prioritas

### Critical

- Batasi ke Super Admin di UI dan backend.
- Catat semua akses Data Viewer ke Audit Log.
- Tambahkan warning data sensitif.

### Important

- Search dinamis per tabel.
- Row detail drawer.
- Resolve foreign key.
- Sticky key columns.

### Nice-to-have

- Copy row JSON.
- Export CSV jika aman.
- Column visibility toggle.
- Page size selector.

---

# Audit Estate Change Requests

## Fungsi

Halaman ini adalah inbox admin untuk review/approval pengajuan perubahan estate dari manager.

## Masalah Saat Ini

Halaman kosong hanya menampilkan:

```text
Tidak ada permintaan.
```

Ini terlalu pasif. Admin perlu tahu apa yang akan muncul dan apa tugasnya.

## Empty State yang Disarankan

```text
Belum ada permintaan perubahan estate

Permintaan dari manager akan muncul di sini untuk divalidasi. Admin perlu memeriksa file geospasial, area, atribut block, dan kelayakan data sebelum menyetujui perubahan estate aktif.
```

## Jika Ada Request

List harus menampilkan:

| Company     | Active Estate  | Diajukan Oleh | File           | Status   | Tanggal | Aksi   |
| ----------- | -------------- | ------------- | -------------- | -------- | ------- | ------ |
| Geografi UI | Sumbawa Estate | dikohary74    | update.geojson | Menunggu | 1 Jun   | Review |

## Review Page Harus Memuat

- company,
- estate aktif saat ini,
- requester,
- file upload,
- hasil validasi format,
- hasil validasi geometri,
- jumlah polygon/block,
- daftar afdeling,
- map preview,
- catatan manager,
- dampak approval,
- reject reason.

## Approval Impact Copy

```text
Jika disetujui:
- Estate aktif saat ini akan menjadi inactive
- Estate baru akan menjadi active
- Estate lama disimpan sementara sesuai retensi
- Pipeline berikutnya akan memakai boundary baru
```

Reject wajib meminta alasan.

---

# Audit Registrations

## Diagnosis

Halaman Registrations menampilkan **Pendaftaran Perusahaan** dengan approve/reject. Namun flow produk saat ini:

- user registration hanya membuat akun,
- company dibuat manual oleh admin/superadmin,
- random user tidak otomatis masuk company,
- viewer harus diundang oleh manager.

Maka halaman Registrations saat ini tidak selaras dengan model operasional.

## Risiko UX

Halaman ini memberi kesan ada flow:

```text
Perusahaan mendaftar sendiri
↓
Admin approve/reject
↓
Company dibuat
```

Padahal flow aktual belum seperti itu.

## Rekomendasi

### Opsi A — Hide Registrations

Pilihan paling bersih untuk fase sekarang. Sembunyikan sampai ada flow pendaftaran perusahaan resmi.

### Opsi B — Refactor

Jika ingin digunakan untuk akun random user, ubah menjadi:

- User Registrations,
- Account Requests,
- Unassigned Users.

Namun jika user registration otomatis tidak perlu approval, halaman ini tetap tidak diperlukan.

## Keputusan yang Disarankan

Hide **Registrations** untuk fase saat ini.

---

# Audit System Settings

## Fungsi

Halaman ini menampilkan konfigurasi sistem non-sensitif secara read-only.

## Yang Sudah Benar

- Secret/password tidak ditampilkan.
- Ada catatan bahwa hanya nilai non-sensitif yang ditampilkan.
- Cocok untuk superadmin/debugging.

## Masalah

Masih raw config. Contoh:

- `APP_VERSION`,
- `CLOUD_FUNCTION_URL`,
- `FRONTEND_URL`,
- `ARCHIVE_RETENTION_DAYS`,
- `RASTER_CACHE_TTL_SECONDS`,
- `ACCESS_TOKEN_EXPIRE_MINUTES`.

Admin perlu tahu mana yang critical dan mana hanya info.

## Rekomendasi Grouping

```text
Application
- APP_VERSION
- ENVIRONMENT
- FRONTEND_URL

Security
- ACCESS_TOKEN_EXPIRE_MINUTES
- DEVICE_TOKEN_EXPIRE_DAYS
- ALLOWED_ORIGINS

Raster & Pipeline
- CLOUD_FUNCTION_URL
- RASTER_CACHE_TTL_SECONDS
- RASTER_CLOUD_TIMEOUT_SECONDS
- FUNCTION_TIMEOUT_SECONDS
- PATCHER_API_VERSION

Data Retention
- ARCHIVE_RETENTION_DAYS
```

Ganti `—` menjadi `Not configured`.

Jika production dan critical config belum terisi, tampilkan warning.

---

# Sidebar dan Information Architecture Admin

## Masalah

Beberapa menu masih lebih mencerminkan struktur teknis daripada model kerja admin.

Contoh:

- Estate Onboarding berada di Data,
- Estate Change berada di Super Admin,
- Registrations belum relevan,
- Data Viewer sangat sensitif tapi tampil bersama menu lain.

## Struktur yang Disarankan

```text
MANAGEMENT
- Dashboard
- Companies
- Admin Users

DATA ESTATE
- Estate Onboarding
- Estate Change Requests
- Data Viewer

PIPELINE
- Trigger Run
- Run History
- Schedules

GOVERNANCE
- Audit Log
- System Settings
```

Jika menu hanya untuk Super Admin, bisa diberi enforcement permission, bukan dipisahkan hanya karena permission internal.

---

# Severity dan Status System-Wide

## Severity Event

Gunakan severity untuk admin actions:

| Severity | Contoh                                                              |
| -------- | ------------------------------------------------------------------- |
| Critical | Approve estate change, update access plan, deactivate manager/admin |
| Warning  | Reject registration, remove member, trigger backfill                |
| Info     | View table, update branding, invite viewer                          |

## Status Pipeline

Gunakan status:

- Running,
- Success — New Data Processed,
- No New Data,
- Skipped Existing Data,
- Partial Success,
- Failed.

## Status Company Setup

Gunakan status:

- Needs manager,
- Needs active estate,
- Ready for pipeline,
- Active,
- Suspended,
- Pending estate change.

## Status Estate Lifecycle

Gunakan status:

- Active,
- Inactive,
- Pending Change,
- Scheduled for deletion,
- Purged.

---

# Prioritas Global Perbaikan

## P0 — Critical

1. Definisikan dan enforce permission Super Admin vs Admin di frontend dan backend.
2. Hide/refactor Registrations karena tidak sesuai flow saat ini.
3. Tambahkan pending workload di Admin Dashboard.
4. Humanize Audit Log: action, target, metadata.
5. Tambahkan setup completeness pada Companies.
6. Pastikan Estate Onboarding tidak meminta `block_code` sebagai required upload input.
7. Tambahkan workflow/stepper untuk Estate Onboarding.
8. Tambahkan status No New Data / Skipped Existing Data di Run History.
9. Batasi Data Viewer hanya untuk Super Admin dan audit semua aksesnya.
10. Cegah deactivate/downgrade Super Admin terakhir.

## P1 — Important

1. Rename “Estates” menjadi “Active Estate” pada konteks single active estate.
2. Rename “+ New estate” menjadi “Replace Active Estate” atau “Import New Estate Version”.
3. Tambahkan confirmation dan change summary untuk Edit Access Plan/Subscription.
4. Tambahkan confirmation untuk Trigger Pipeline dan Backfill.
5. Ubah schedule cadence menjadi interval eksplisit 1/7/10/14/30 hari/custom.
6. Default timezone schedule ke Asia/Jakarta atau timezone company.
7. Tambahkan row detail drawer di Data Viewer.
8. Tambahkan filter Audit Log.
9. Tambahkan reject reason untuk Estate Change Requests.
10. Tambahkan role permission summary di Admin Users.

## P2 — Nice-to-have

1. Auto-suggest column mapping di Estate Onboarding.
2. Sticky columns di Data Viewer.
3. Resolved foreign keys di Data Viewer.
4. Export audit log CSV.
5. Copy UUID / copy row JSON.
6. Page size selector.
7. System health widget di Admin Dashboard.
8. Audit log before/after diff untuk field penting.
9. Schedule pause/resume.
10. Company onboarding wizard setelah New Company dibuat.

---

# Kesimpulan Akhir

Halaman admin CanopySense sudah memiliki modul-modul yang secara struktur benar, tetapi masih perlu dinaikkan dari level “CRUD admin panel” menjadi **operational control center**.

Admin tidak hanya butuh melihat data. Admin harus bisa:

- tahu apa yang perlu ditangani,
- memahami dampak setiap aksi,
- mencegah kesalahan fatal,
- memvalidasi data geospasial dengan aman,
- melacak siapa melakukan apa,
- membedakan no-data, skipped, failed, dan success,
- membatasi akses sesuai role internal.

Perbaikan paling menentukan bukan kosmetik, melainkan **state clarity, permission clarity, impact clarity, dan auditability**.

Kalau empat hal itu diperkuat, halaman admin akan terasa jauh lebih siap untuk deployment cloud dan operasi data production.

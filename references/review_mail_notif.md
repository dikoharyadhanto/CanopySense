# Review UI/UX Komunikasi Email & Notifikasi CanopySense

## Scope Review

Dokumen ini berisi audit khusus untuk komunikasi ke user melalui email pada aplikasi CanopySense. Fokus review adalah **kejelasan pesan, trust, keamanan, konsistensi identitas produk, dan kesiapan komunikasi transactional**.

Email yang dibahas meliputi:

- Verification code / OTP
- Pendaftaran perusahaan diterima / sedang ditinjau
- Pendaftaran perusahaan disetujui
- Pendaftaran perusahaan ditolak
- Link setup akun manager
- Email delivery failure pada environment development/staging

Catatan penting: audit ini tidak membahas konfigurasi Google Cloud secara penuh. Fokusnya adalah komunikasi yang diterima user.

---

# Executive Summary

Fondasi komunikasi email CanopySense sudah ada dan flow transactional-nya mulai terbentuk. User sudah menerima email untuk verifikasi, status pendaftaran, approval, rejection, dan setup akun manager.

Masalah utama saat ini bukan keberadaan email, tetapi **trust dan identitas komunikasi**. Beberapa email masih terlihat berasal dari akun project lama atau akun personal/development, bukan dari identitas resmi CanopySense. Selain itu, masih ada email test/dummy yang bounce karena dikirim ke domain tidak valid seperti `test.local`.

Prioritas utama perbaikan:

1. Pisahkan **akun cloud/infrastruktur** dari **identitas komunikasi produk**.
2. Gunakan sender khusus CanopySense.
3. Konsistenkan bahasa email.
4. Cegah pengiriman email nyata ke alamat dummy/test.
5. Rapikan subject, CTA, dan security notice pada email transactional.

---

# Diagnosis Utama

## 1. Infrastruktur boleh numpang, identitas komunikasi tidak boleh ikut numpang

Untuk fase development, masih wajar jika Google Cloud / billing / project deployment memakai akun lama yang sudah aktif dan berbayar. Migrasi cloud terlalu dini bisa menambah risiko dan pekerjaan yang tidak perlu.

Namun komunikasi ke user harus menggunakan identitas produk yang jelas.

Model yang disarankan:

```text
Cloud / billing / deployment
→ boleh tetap memakai akun/project lama untuk sementara

Email sender / komunikasi user
→ gunakan identitas khusus CanopySense
```

Jika user menerima OTP, approval, atau link setup dari email yang terlihat random, personal, atau tidak berhubungan dengan CanopySense, trust langsung turun.

---

## 2. Sender identity belum cukup resmi

Di screenshot, sender terlihat sebagai akun/project lama, misalnya tampil seperti:

```text
risprosdb...
```

Ini membuat email terasa seperti berasal dari akun pribadi/development, bukan sistem resmi CanopySense.

### Risiko UX

User bisa berpikir:

```text
Ini benar email dari CanopySense?
Ini phishing?
Kenapa OTP aplikasi datang dari alamat asing?
```

### Rekomendasi

Gunakan display name konsisten:

```text
CanopySense
```

Format ideal:

```text
CanopySense <no-reply@domain-resmi>
```

Untuk development cepat:

```text
CanopySense <canopysense.notification@gmail.com>
```

atau:

```text
CanopySense <canopysense.app@gmail.com>
```

Yang penting: di inbox user, nama pengirim harus terbaca sebagai **CanopySense**.

---

# Rekomendasi Identitas Email

## Opsi 1 — Cepat untuk Development / Demo

Buat Gmail khusus CanopySense.

Contoh:

```text
Display name: CanopySense
Email: canopysense.notification@gmail.com
```

Kelebihan:

- cepat dibuat,
- tidak perlu beli domain,
- cukup untuk testing, demo, dan development,
- lebih kredibel daripada akun project lama.

Kekurangan:

- belum seprofesional domain sendiri,
- deliverability dan branding terbatas,
- kurang ideal untuk production.

---

## Opsi 2 — Proper untuk Pre-production / Production

Gunakan domain yang dikontrol sendiri.

Contoh:

```text
no-reply@canopysense.id
support@canopysense.id
admin@canopysense.id
```

Atau domain lain yang tersedia dan dikontrol sendiri:

```text
canopysense.id
canopysense.app
canopysense.ai
canopysense.io
```

Catatan: email seperti `@canopysense.com` hanya bisa digunakan jika domain tersebut dimiliki atau dikontrol. Tidak bisa sembarang mengirim email dari domain yang tidak dimiliki karena akan ditolak, masuk spam, atau dianggap spoofing.

Untuk production, domain harus diverifikasi menggunakan DNS record seperti:

- SPF
- DKIM
- DMARC

---

## Opsi 3 — Transactional Email Provider

Untuk production, gunakan layanan transactional email:

- Resend
- SendGrid
- Mailgun
- Amazon SES
- Brevo
- Postmark

Format sender ideal:

```text
CanopySense <no-reply@canopysense.id>
```

Reply-to bisa diarahkan ke:

```text
support@canopysense.id
```

---

# Masalah Email Test / Dummy

## Problem

Ada email delivery failure karena sistem mencoba mengirim ke domain dummy seperti:

```text
test.local
```

Contoh error:

```text
Address not found
The domain test.local couldn't be found.
```

Untuk development, ini wajar terjadi. Tetapi jika masuk ke inbox nyata, ini menjadi noise dan bisa mengganggu validasi alur email.

## Risiko

- Inbox testing penuh bounce email.
- Admin sulit membedakan email sistem yang valid dan error development.
- Jika terjadi di production, ini terlihat tidak profesional.

## Rekomendasi

Tambahkan guard pada sistem email:

```text
Jangan kirim email outbound ke domain .local, .test, atau domain invalid pada environment production/staging kecuali mode testing eksplisit.
```

Untuk development gunakan salah satu:

- Mailtrap
- Mailpit
- Ethereal Email
- Resend test mode
- log-only email mode
- local SMTP catcher

Tambahkan environment flag:

```env
MAIL_MODE=smtp | sandbox | log_only
MAIL_FROM_NAME=CanopySense
MAIL_FROM_ADDRESS=canopysense.notification@gmail.com
MAIL_REPLY_TO=support@example.com
BLOCK_DUMMY_EMAILS=true
```

---

# Konsistensi Bahasa

## Problem

Sebagian email memakai Bahasa Inggris:

```text
Hello canopy_superadmin,
Your CanopySense verification code is...
```

Sebagian email lain memakai Bahasa Indonesia:

```text
Halo Test Approve,
Pendaftaran perusahaan ...
```

## Rekomendasi

Untuk target user Indonesia, gunakan Bahasa Indonesia sebagai default untuk semua transactional email user-facing.

Email internal developer boleh Inggris, tetapi email yang diterima manager/viewer/admin operasional sebaiknya konsisten.

Standar bahasa yang disarankan:

```text
Bahasa Indonesia formal-ringan, jelas, dan operasional.
```

Hindari bahasa yang terlalu marketing untuk pesan transactional. Prioritaskan status, aksi, dan keamanan.

---

# Review Per Jenis Email

## 1. Verification Code / OTP

### Yang sudah bagus

- Subject jelas.
- Kode terlihat besar dan mudah dibaca.
- Masa berlaku jelas: 10 menit.
- Ada peringatan agar kode tidak dibagikan.
- Ada instruksi jika user tidak mencoba login.

### Masalah

- Bahasa masih Inggris.
- Sender belum terlihat resmi sebagai CanopySense.
- Sapaan memakai username teknis, misalnya `canopy_superadmin`.

### Rekomendasi Subject

```text
CanopySense — Kode Verifikasi
```

### Template yang disarankan

```text
Halo {display_name},

Kode verifikasi CanopySense Anda adalah:

{verification_code}

Kode ini berlaku selama 10 menit. Jangan bagikan kode ini kepada siapa pun.

Jika Anda tidak mencoba masuk, segera hubungi administrator.
```

### Catatan UX

Jika `display_name` tidak tersedia, gunakan:

```text
Halo,
```

Daripada menampilkan username teknis yang kurang manusiawi.

---

## 2. Pendaftaran Perusahaan Diterima / Sedang Ditinjau

### Fungsi email

Memberi tahu user bahwa pendaftaran perusahaan sudah diterima dan sedang menunggu review admin.

### Yang sudah bagus

- Pesan menjelaskan bahwa pendaftaran sedang diproses.
- User diberi tahu bahwa akan ada email lanjutan setelah disetujui atau ditolak.

### Masalah

- Subject perlu konsisten.
- Sender harus resmi.
- Perlu membedakan dengan approval final.

### Rekomendasi Subject

```text
CanopySense — Pendaftaran Sedang Ditinjau
```

### Template yang disarankan

```text
Halo {contact_name},

Pendaftaran perusahaan {company_name} telah kami terima dan sedang ditinjau oleh administrator.

Anda akan menerima email konfirmasi setelah pendaftaran disetujui atau ditolak.

Jika Anda tidak merasa melakukan pendaftaran ini, abaikan email ini.
```

---

## 3. Pendaftaran Perusahaan Disetujui

### Fungsi email

Memberi tahu bahwa pendaftaran perusahaan disetujui dan user dapat mengatur akun manager.

### Yang sudah bagus

- Pesan menyebut nama perusahaan.
- CTA jelas: mengatur akun manager.
- Link memiliki masa berlaku 1 jam.

### Masalah

Subject seperti:

```text
CanopySense — Selamat Datang, FMN Approval Test Co!
```

terasa agak marketing. Padahal email ini adalah email approval + setup akun.

### Rekomendasi Subject

```text
CanopySense — Pendaftaran Perusahaan Disetujui
```

atau:

```text
CanopySense — Atur Akun Manager Anda
```

### Template yang disarankan

```text
Halo {contact_name},

Pendaftaran perusahaan {company_name} telah disetujui.

Klik tombol di bawah untuk mengatur akun manager Anda.

[Atur Akun Manager]

Tautan ini berlaku selama 1 jam dan hanya dapat digunakan oleh penerima email ini. Jangan teruskan email ini kepada pihak lain.
```

### Catatan keamanan

Tambahkan pesan jika link expired:

```text
Jika tautan sudah kedaluwarsa, hubungi administrator untuk mengirim ulang tautan setup.
```

---

## 4. Pendaftaran Perusahaan Ditolak

### Fungsi email

Memberi tahu bahwa pendaftaran perusahaan tidak disetujui.

### Masalah utama

Email penolakan harus menyertakan alasan. Tanpa alasan, user tidak tahu apa yang harus diperbaiki.

### Rekomendasi Subject

```text
CanopySense — Pendaftaran Tidak Disetujui
```

### Template yang disarankan

```text
Halo {contact_name},

Pendaftaran perusahaan {company_name} tidak dapat disetujui.

Alasan:
{rejection_reason}

Jika informasi ini keliru atau Anda membutuhkan klarifikasi, silakan hubungi administrator CanopySense.
```

### Requirement UX

Admin yang menolak pendaftaran wajib mengisi alasan penolakan.

Validasi UI admin:

```text
Alasan penolakan wajib diisi sebelum pendaftaran ditolak.
```

---

## 5. Invitation / Setup Manager Link

### Fungsi email

Memberikan link setup untuk akun manager setelah company dibuat/disetujui.

### Risiko

Link setup adalah akses sensitif. Jika diteruskan ke orang lain atau dipakai setelah bocor, bisa berbahaya.

### Rekomendasi isi email

```text
Halo {contact_name},

Anda telah ditetapkan sebagai manager untuk {company_name} di CanopySense.

Klik tombol di bawah untuk menyelesaikan pengaturan akun manager.

[Atur Akun Manager]

Tautan ini berlaku selama 1 jam dan hanya dapat digunakan oleh email penerima. Jangan teruskan email ini kepada pihak lain.
```

### Rekomendasi teknis UX

- Link harus single-use.
- Link harus expired.
- Jika expired, user harus bisa meminta resend.
- Jika link sudah digunakan, tampilkan state jelas:

```text
Tautan setup sudah digunakan.
Silakan masuk menggunakan akun Anda.
```

---

## 6. Invitation Viewer

### Fungsi email

Manager mengundang viewer untuk bergabung ke company/organization.

### Template yang disarankan

```text
Halo,

Anda diundang untuk bergabung sebagai Viewer di {company_name} pada CanopySense.

Sebagai Viewer, Anda dapat melihat dashboard, peta, dan data monitoring. Anda tidak dapat mengubah data, mengelola anggota, atau menjalankan pipeline.

[Terima Undangan]

Tautan ini berlaku selama {expiry_duration}.
```

### Catatan UX

Viewer harus tahu bahwa aksesnya read-only. Jangan buat user menebak role-nya.

---

## 7. Pipeline Notification Email

Saat ini fitur notifikasi sistem belum sepenuhnya diterapkan dan mayoritas komunikasi masih melalui email. Jika email pipeline akan digunakan, gunakan istilah yang tidak terlalu teknis.

### Hindari

```text
Pipeline gagal
Pipeline berhasil
```

Jika user non-teknis adalah target utama, gunakan:

```text
Pemrosesan data gagal
Pemrosesan data selesai
Tidak ada data baru
```

### Status email yang disarankan

#### Pemrosesan berhasil dan data baru diproses

```text
CanopySense — Pemrosesan Data Selesai
```

Isi:

```text
Pemrosesan data untuk {company_name} / {estate_name} telah selesai.

Hasil:
- Data baru diproses: {scene_count} scene
- Blok diperbarui: {block_count}
- Waktu proses: {duration}
```

#### Tidak ada data baru

```text
CanopySense — Tidak Ada Data Baru
```

Isi:

```text
Pipeline telah berjalan untuk {company_name} / {estate_name}, tetapi tidak menemukan data satelit baru yang perlu diproses.

Data yang sudah tersimpan tidak diproses ulang.
```

#### Pemrosesan gagal

```text
CanopySense — Pemrosesan Data Gagal
```

Isi:

```text
Pemrosesan data untuk {company_name} / {estate_name} gagal.

Waktu: {timestamp}
Scope: {scope}
Penyebab: {failure_reason}

Silakan periksa Run History di Admin Panel.
```

---

# Standar Subject Email

Gunakan pola konsisten:

```text
CanopySense — {Status / Aksi Utama}
```

Contoh:

```text
CanopySense — Kode Verifikasi
CanopySense — Pendaftaran Sedang Ditinjau
CanopySense — Pendaftaran Perusahaan Disetujui
CanopySense — Pendaftaran Tidak Disetujui
CanopySense — Undangan Viewer
CanopySense — Link Setup Manager
CanopySense — Pemrosesan Data Gagal
CanopySense — Tidak Ada Data Baru
```

Hindari subject yang terlalu panjang atau terlalu marketing untuk email transactional.

---

# Standar Footer Email

Tambahkan footer konsisten di semua email:

```text
Email ini dikirim otomatis oleh CanopySense. Mohon jangan membalas email ini.

Jika Anda membutuhkan bantuan, hubungi administrator CanopySense.
```

Jika memakai support email:

```text
Butuh bantuan? Hubungi support@canopysense.id
```

Untuk development/demo dengan Gmail khusus:

```text
Butuh bantuan? Hubungi administrator CanopySense.
```

---

# Rekomendasi Environment & Konfigurasi

## Environment Variables

Tambahkan konfigurasi email yang eksplisit:

```env
MAIL_FROM_NAME=CanopySense
MAIL_FROM_ADDRESS=canopysense.notification@gmail.com
MAIL_REPLY_TO=canopysense.notification@gmail.com
MAIL_MODE=smtp
MAIL_BLOCK_DUMMY_DOMAINS=true
MAIL_DEFAULT_LOCALE=id-ID
```

Untuk production dengan domain:

```env
MAIL_FROM_NAME=CanopySense
MAIL_FROM_ADDRESS=no-reply@canopysense.id
MAIL_REPLY_TO=support@canopysense.id
MAIL_MODE=transactional_provider
MAIL_BLOCK_DUMMY_DOMAINS=true
MAIL_DEFAULT_LOCALE=id-ID
```

---

# Guardrail Pengiriman Email

Sistem sebaiknya memblokir atau memberi warning saat mencoba mengirim ke:

```text
*.local
*.test
example.com
invalid domain
alamat tanpa MX record
```

Untuk development, boleh diarahkan ke sandbox.

Contoh behavior:

```text
Development:
- email dummy disimpan ke log/sandbox
- tidak dikirim ke internet

Production:
- email dummy diblokir
- event dicatat ke audit/error log
```

---

# Prioritas Perbaikan

## Critical

1. **Gunakan sender identity khusus CanopySense.**
   - Minimal Gmail khusus.
   - Idealnya domain resmi.

2. **Set display name email menjadi CanopySense.**
   - Jangan tampil sebagai akun project lama atau akun personal.

3. **Blokir pengiriman ke domain dummy/test.**
   - Hindari bounce seperti `test.local`.

4. **Konsistenkan bahasa email ke Bahasa Indonesia.**
   - Terutama untuk user-facing transactional email.

5. **Email penolakan wajib menyertakan alasan.**
   - Admin harus mengisi reason saat reject.

---

## Important

6. **Rapikan subject email menjadi operasional dan konsisten.**
7. **Tambahkan security note untuk OTP dan setup link.**
8. **Gunakan link setup yang single-use dan expired.**
9. **Tambahkan resend flow untuk link expired.**
10. **Gunakan sandbox email untuk development/staging.**

---

## Nice-to-have

11. Tambahkan logo CanopySense pada email template.
12. Tambahkan preheader text.
13. Buat template HTML yang dark-mode friendly.
14. Tambahkan footer standar.
15. Tambahkan email event log di admin panel.
16. Tambahkan preview email template di admin/dev tools.

---

# Recommended Implementation Roadmap

## Fase 1 — Cepat / Development

- Buat Gmail khusus CanopySense.
- Set display name menjadi **CanopySense**.
- Ubah semua template email ke Bahasa Indonesia.
- Blokir domain dummy/test.
- Tambahkan reason di email reject.
- Tambahkan env config untuk sender.

## Fase 2 — Pre-production

- Gunakan transactional email provider.
- Tambahkan email sandbox untuk staging.
- Tambahkan template HTML standar.
- Tambahkan resend setup link.
- Tambahkan email event log.

## Fase 3 — Production

- Gunakan domain resmi.
- Konfigurasi SPF, DKIM, DMARC.
- Gunakan sender `no-reply@domain` dan reply-to support.
- Monitor bounce, complaint, dan delivery rate.
- Tambahkan alert jika email provider gagal mengirim pesan penting.

---

# Final Recommendation

Untuk kondisi CanopySense saat ini, keputusan paling rasional:

```text
Tetap gunakan akun Google Cloud lama untuk development/deployment sementara.
Namun, segera pisahkan identitas email dengan membuat akun email khusus CanopySense.
```

Jangan tunggu migrasi cloud untuk memperbaiki komunikasi email. User tidak melihat akun billing Google Cloud, tetapi mereka melihat siapa pengirim OTP dan link setup.

Perubahan paling kecil tetapi berdampak besar:

```text
Display name: CanopySense
Sender: email khusus CanopySense
Bahasa: Indonesia konsisten
Dummy email: diblokir/sandbox
```

Ini akan langsung menaikkan trust dan membuat komunikasi produk terasa lebih resmi.

# Review UI/UX CanopySense

**Konteks audit:** aplikasi masih berjalan di local dan data satelit/indeks/time-series belum di-run. Audit ini menilai pengalaman pengguna ketika aplikasi berada dalam kondisi **data kosong**, bukan menilai kualitas output data production.

**Baseline penilaian:** user harus tetap memahami bahwa sistem valid, estate/blok sudah dikenali, dan data analitik belum tersedia karena belum diproses. UI tidak boleh terasa seperti error, rusak, atau setengah jalan.

---

## 1. Prinsip Utama Empty-State UX

Aplikasi CanopySense harus mampu menangani kondisi belum ada data satelit, indeks vegetasi, maupun time-series dengan jelas dan profesional.

User harus paham bahwa:

1. Estate dan blok sudah dikenali.
2. Data analitik belum tersedia.
3. Sistem tidak rusak.
4. User tahu status saat ini atau langkah berikutnya.

### Kosakata status yang disarankan

| Kondisi                       | Label yang disarankan          |
| ----------------------------- | ------------------------------ |
| Data belum pernah diproses    | **Belum diproses**             |
| Tidak ada raster untuk indeks | **Raster belum tersedia**      |
| Belum ada data historis       | **Time-series belum dibangun** |
| Belum ada tanggal akuisisi    | **Belum ada akuisisi**         |
| Boundary/blok sudah ada       | **Siap dianalisis**            |
| Data gagal diproses           | **Gagal diproses**             |
| Data sedang berjalan          | **Sedang diproses**            |

### Hindari penggunaan generik

Hindari terlalu banyak menggunakan:

- `N/A`
- `—`
- `Tidak ada data`
- `0%`

Kecuali disertai penjelasan yang spesifik. Istilah tersebut mudah ditafsirkan sebagai error sistem.

---

## 2. Dashboard Utama

### Diagnosis

Dashboard sudah rapi secara visual dan cukup terasa seperti aplikasi enterprise. Struktur sidebar, topbar, card metrics, dan peta sudah membentuk dashboard yang familiar.

Namun dalam kondisi data kosong, dashboard belum cukup menjelaskan bahwa sistem sedang berada dalam state **belum diproses**, bukan error.

### Masalah utama

#### 2.1 Card metrics terlihat seperti error

Card saat ini menampilkan informasi seperti:

- Avg NDVI Estate: `N/A`
- Index Coverage: `0%`
- Akuisisi Terakhir: `—`
- Total Blok: `46`

Masalahnya, `N/A`, `0%`, dan `—` membuat user berpikir sistem gagal atau data hilang.

#### Rekomendasi

Ubah menjadi state yang lebih eksplisit:

- **Status Analisis:** Belum dijalankan
- **Cakupan Data:** 0 dari 46 blok
- **Akuisisi Terakhir:** Belum ada
- **Total Blok:** 46

Tambahkan banner empty state:

> **Data NDVI belum diproses**  
> Sistem sudah mengenali 46 blok estate, tetapi hasil analisis NDVI belum tersedia. Jalankan akuisisi atau pemrosesan data untuk mulai melihat kesehatan kanopi.

Jika tombol pipeline belum tersedia, jangan tampilkan CTA palsu. Gunakan CTA yang memang bisa dilakukan, misalnya:

- **Lihat Batas Blok**
- **Buka Explore Map**
- **Refresh Status Data**

#### 2.2 Dashboard belum cukup decision-oriented

Untuk aplikasi monitoring kesehatan kanopi, dashboard seharusnya menjawab:

1. Berapa area bermasalah?
2. Di mana lokasinya?
3. Seberapa parah?
4. Kapan terakhir terdeteksi?
5. Apa tindakan berikutnya?

Dalam kondisi data kosong, dashboard tetap bisa memberi insight:

- 46 blok sudah terdeteksi.
- 0 blok sudah memiliki data NDVI.
- Analisis belum dapat dilakukan.
- Sistem menunggu hasil akuisisi/pemrosesan data.

#### 2.3 Peta abu-abu perlu konteks

Polygon abu-abu masih valid sebagai indikasi belum ada data. Namun label legend **Tidak ada data** sebaiknya diganti menjadi:

- **Belum dianalisis**
- **Belum diproses**
- **Data indeks belum tersedia**

### Prioritas perbaikan Dashboard

| Prioritas    | Perbaikan                                                         |
| ------------ | ----------------------------------------------------------------- |
| Critical     | Ganti `N/A`, `—`, dan `0%` dengan status manusiawi                |
| Critical     | Tambahkan empty-state banner yang menjelaskan data belum diproses |
| Important    | Tambahkan ringkasan “46 blok siap dianalisis”                     |
| Important    | Ganti legend “Tidak ada data” menjadi “Belum dianalisis”          |
| Nice-to-have | Tambahkan detail saat polygon diklik                              |

---

## 3. Explore Map

### Diagnosis

Explore Map memiliki masalah UX paling jelas: peta default tidak langsung mengarah ke area estate/blok yang sedang dikelola.

User membuka Explore Map dengan ekspektasi:

> “Tunjukkan estate/blok yang sedang saya kelola.”

Bukan melihat Indonesia atau world map secara umum.

### Masalah utama

#### 3.1 Default map view salah konteks

Jika aplikasi sudah mengetahui estate dan 46 blok, map harus otomatis mengarah ke area estate.

#### Rekomendasi behavior

```text
Jika estate aktif punya boundary/blok:
  zoom otomatis ke area estate menggunakan fitBounds
Jika belum ada boundary:
  tampilkan empty state + pilihan estate
Jika user tidak punya estate:
  tampilkan onboarding/setup estate
```

Secara teknis:

- Ambil seluruh polygon blok aktif.
- Hitung bounding box.
- Jalankan `fitBounds`.
- Tambahkan padding agar area tidak terlalu mepet.
- Fallback ke Indonesia hanya jika boundary benar-benar belum ada.

#### 3.2 Empty state terlalu pasif

Copy saat ini sudah mengarah ke kondisi kosong, tetapi masih kurang actionable.

Rekomendasi copy:

> **Belum ada data satelit untuk estate ini**  
> Sistem sudah mengenali batas estate/blok, tetapi raster indeks vegetasi belum tersedia. Data akan tampil setelah proses akuisisi atau pemrosesan berhasil dilakukan.

CTA yang relevan:

- **Refresh Status Data**
- **Tampilkan Batas Blok**
- **Kembali ke Dashboard**

#### 3.3 Kontrol raster muncul padahal raster kosong

Jika raster belum tersedia, slider opacity raster sebaiknya tidak aktif.

Rekomendasi:

- Disable slider opasitas.
- Tambahkan teks: **Raster belum tersedia**.
- Jangan tampilkan kontrol raster aktif jika belum ada layer raster.

#### 3.4 Toggle indeks bisa menimbulkan friction

Tab NDVI, EVI, SAVI, GNDVI, NDRE terlihat bisa digunakan. Jika semua data kosong, user bisa klik satu per satu tanpa hasil.

Rekomendasi:

- Tambahkan tooltip: **Belum ada data untuk indeks ini**.
- Atau tampilkan pesan spesifik saat tab diklik: **Data EVI belum tersedia untuk estate ini**.

### Prioritas perbaikan Explore Map

| Prioritas    | Perbaikan                                                                         |
| ------------ | --------------------------------------------------------------------------------- |
| Critical     | Auto-focus map ke estate/blok menggunakan `fitBounds`                             |
| Critical     | Empty state harus menjelaskan raster belum tersedia, bukan sekadar tidak ada data |
| Important    | Disable/hide opacity raster saat raster kosong                                    |
| Important    | Ganti “Refresh” menjadi “Refresh Raster” atau “Refresh Status Data”               |
| Nice-to-have | Tambahkan tooltip/status pada tab indeks                                          |

---

## 4. Time-Series Analyzer

### Diagnosis

Layout kiri-kanan sudah masuk akal: selector dan metadata blok di kiri, chart utama di kanan. Namun dalam kondisi data kosong, panel chart terlalu kosong dan mudah terlihat seperti fitur gagal.

### Masalah utama

#### 4.1 Empty chart terasa seperti error

Pesan saat ini:

> Tidak ada data untuk blok ini  
> Pilih blok lain atau periksa status akuisisi data.

Masalahnya, jika semua blok memang belum punya data, menyuruh user memilih blok lain kurang membantu.

#### Rekomendasi copy

> **Time-series belum tersedia**  
> Blok **C — BLK-0001** sudah terdaftar di **Sumbawa Estate**, tetapi data historis NDVI belum diproses. Grafik akan tampil setelah akuisisi dan pemrosesan data pertama berhasil dilakukan.

Tambahkan status checklist:

- Batas blok: tersedia
- Data satelit: belum tersedia
- Time-series: belum dibangun
- Akuisisi terakhir: belum ada

#### 4.2 Warning tutupan awan muncul terlalu dini

Peringatan cloud cover muncul walaupun belum ada chart dan titik data.

Masalahnya, user bisa bertanya:

> “Mana garis merahnya? Mana titik datanya?”

#### Rekomendasi

Sembunyikan warning cloud cover sampai chart tersedia.

Atau ubah menjadi catatan pasif:

> Saat data tersedia, titik dengan tutupan awan tinggi akan diberi penanda khusus.

#### 4.3 Disabled index tidak punya alasan

NDVI tampil selalu aktif, indeks lain disabled. Ini bisa dipersepsikan sebagai fitur belum jadi.

Rekomendasi:

- NDVI — Aktif, belum ada data
- EVI — Belum diproses
- NDRE — Belum diproses
- SAVI — Belum diproses
- GNDVI — Belum diproses

#### 4.4 Metadata blok perlu label manusiawi

Ganti:

- **NDVI: N/A** → **NDVI: Belum diproses**
- **Tanggal: -** → **Tanggal: Belum ada akuisisi**

Tambahkan:

- **Status blok:** Siap dianalisis

### Prioritas perbaikan Time-Series

| Prioritas    | Perbaikan                                            |
| ------------ | ---------------------------------------------------- |
| Critical     | Ganti empty chart menjadi pre-processing empty state |
| Critical     | Ganti `N/A` dan `-` dengan status spesifik           |
| Important    | Sembunyikan warning cloud cover sampai ada data      |
| Important    | Jelaskan kenapa indeks lain disabled                 |
| Nice-to-have | Tambahkan checklist status data pada panel kosong    |

---

## 5. Profile Page

### Diagnosis

Halaman Profile sudah fungsional, tetapi terasa seperti form admin standar yang belum cukup dipoles. Masalah utamanya ada pada layout, read-only state, dan UX keamanan password.

### Masalah utama

#### 5.1 Layout terlalu sempit di desktop

Konten profile memakai kolom kecil di tengah dengan banyak ruang kosong. Ini terasa seperti layout mobile yang ditempel ke web desktop.

#### Rekomendasi

Gunakan layout 2 kolom:

```text
[Informasi Akun]        [Keamanan Akun]
Nama Lengkap            Password Saat Ini
Username                Password Baru
Email                   Konfirmasi Password
Peran                   Checklist kekuatan password
Organisasi              Ubah Password
Status akses
```

Atau lebarkan card menjadi sekitar 520–640px.

#### 5.2 Field editable dan read-only belum cukup jelas

User bisa bingung kenapa username/email tidak bisa diedit.

Tambahkan microcopy:

- Username: **Tidak dapat diubah**
- Email: **Dikelola oleh akun organisasi**
- Role: **Ditetapkan oleh admin**

#### 5.3 Role tampil seperti value database

Ganti:

- `manager` → **Manager**
- `viewer` → **Viewer**

Tambahkan deskripsi role jika perlu:

> Manager dapat mengelola anggota dan melihat seluruh monitoring estate.

#### 5.4 UX password masih kurang

Tambahkan:

- Show/hide password.
- Validasi kekuatan password real-time.
- Indikator konfirmasi password cocok/tidak cocok.
- Loading state saat submit.
- Success/error state yang jelas.

### Prioritas perbaikan Profile

| Prioritas    | Perbaikan                                   |
| ------------ | ------------------------------------------- |
| Critical     | Perjelas field read-only                    |
| Critical     | Tambahkan feedback validasi password        |
| Important    | Lebarkan layout atau gunakan 2 kolom        |
| Important    | Ubah role lowercase menjadi label manusiawi |
| Nice-to-have | Tambahkan aktivitas login terakhir          |

---

## 6. Kelola Anggota / User Management

### Diagnosis

Fungsi halaman ini cukup jelas: manager dapat mengundang user dengan role viewer agar dapat melihat monitoring tanpa hak manajerial.

Namun ini adalah fitur **access management**, bukan sekadar daftar user. UI harus eksplisit soal role, status, dan konsekuensi pencabutan akses.

### Masalah utama

#### 6.1 “Undang Viewer” terlalu sempit

Jika memang hanya viewer yang bisa diundang, itu valid. Namun user perlu tahu kenapa tidak bisa memilih role lain.

Rekomendasi copy:

> **Undang Anggota Baru**  
> Anggota baru akan diberi akses sebagai **Viewer**. Viewer dapat melihat dashboard, peta, dan time-series, tetapi tidak dapat mengelola anggota atau mengubah konfigurasi.

#### 6.2 Tabel status belum berguna

Kolom Status berisi `—`. Untuk access management, status adalah informasi penting.

Gunakan badge:

- **Aktif**
- **Menunggu diterima**
- **Undangan terkirim**
- **Kedaluwarsa**
- **Nonaktif**

#### 6.3 Aksi “Hapus” terlalu ambigu

“Hapus” bisa dianggap menghapus akun permanen. Padahal kemungkinan yang dimaksud adalah mencabut akses dari organisasi/estate.

Ganti menjadi:

- **Cabut Akses**

Tambahkan confirmation modal:

> **Cabut akses pengguna?**  
> Pengguna ini tidak akan dapat mengakses monitoring CanopySense untuk organisasi ini. Akun pribadinya tidak akan dihapus.

Button:

- **Batal**
- **Cabut Akses**

### Prioritas perbaikan Kelola Anggota

| Prioritas    | Perbaikan                                                    |
| ------------ | ------------------------------------------------------------ |
| Critical     | Ganti “Hapus” menjadi “Cabut Akses” + confirmation modal     |
| Critical     | Isi kolom Status dengan badge nyata atau hilangkan sementara |
| Important    | Jelaskan permission Viewer sebelum invite                    |
| Important    | Tampilkan role sebagai “Manager” / “Viewer”                  |
| Nice-to-have | Tambahkan resend invitation dan cancel invitation            |

---

## 7. Pengaturan Branding & Header

### Diagnosis

Fungsi halaman ini sederhana: mengubah nama organisasi/perusahaan dan upload logo untuk tampil di header. Secara dasar sudah jelas, tetapi belum memiliki preview dan pola penyimpanan yang konsisten.

### Masalah utama

#### 7.1 Tidak ada preview hasil branding

Untuk fitur branding, preview adalah inti UX.

Tambahkan preview header:

```text
[Logo] Geografi UI                         CanopySense
                                           Monitoring Kerapatan Kanopi Perkebunan Karet
```

Preview harus berubah saat user:

- mengganti nama,
- upload logo,
- menonaktifkan logo,
- menonaktifkan nama.

#### 7.2 File input masih default browser

Tombol “Choose File / No file chosen” terlihat mentah dan tidak konsisten dengan UI aplikasi.

Rekomendasi:

- Gunakan upload area custom.
- Tampilkan thumbnail logo.
- Tampilkan nama file dan ukuran file.
- Tambahkan tombol **Ganti Logo** dan **Hapus Logo**.

#### 7.3 Pola simpan tidak konsisten

Tombol Simpan hanya terlihat di bagian Nama Perusahaan. User bisa bingung apakah logo dan checkbox tersimpan otomatis.

Pilih salah satu:

1. Auto-save dengan indikator **Tersimpan otomatis**.
2. Manual save dengan satu tombol **Simpan Perubahan Branding**.

Untuk saat ini, opsi manual save lebih aman.

#### 7.4 Istilah “perusahaan” mungkin terlalu sempit

Karena contoh menggunakan Geografi UI, istilah **organisasi** lebih fleksibel daripada **perusahaan**.

Rekomendasi label:

- **Nama Organisasi**
- **Logo Organisasi**
- **Tampilan Header**

### Prioritas perbaikan Branding

| Prioritas    | Perbaikan                                        |
| ------------ | ------------------------------------------------ |
| Critical     | Tambahkan preview header                         |
| Critical     | Buat satu pola penyimpanan yang jelas            |
| Important    | Ganti file input default dengan upload component |
| Important    | Tampilkan thumbnail logo setelah upload          |
| Nice-to-have | Tambahkan reset ke default branding              |

---

## 8. Pengajuan Perubahan Estate

### Diagnosis

Fungsi halaman ini adalah workflow pengajuan perubahan data geospasial estate/blok. Manager mengajukan file, admin memvalidasi file, lalu admin menyetujui atau menolak sebelum data diterapkan.

Ini bukan upload biasa. Ini adalah perubahan data master yang berisiko tinggi karena dapat memengaruhi:

- peta,
- jumlah blok,
- batas estate/blok,
- hasil analisis,
- histori data,
- konsistensi monitoring.

### Alur ideal

```text
Manager mengajukan file
↓
Sistem menerima pengajuan
↓
Admin validasi file:
- format valid atau korup
- area benar atau salah
- geometri valid
- atribut blok lengkap
- overlap/gap/duplikasi
↓
Admin menyetujui atau menolak
↓
Jika disetujui, data estate/blok diganti
```

### Masalah utama

#### 8.1 Label halaman terlalu umum

“Perubahan Estate” bisa diganti menjadi:

- **Pengajuan Perubahan Data Estate**
- **Pengajuan Perubahan Batas Estate/Blok**
- **Pengajuan Data Spasial Estate**

#### 8.2 Status `—` tidak informatif

Ganti dengan status workflow:

| Status                      | Makna                                    |
| --------------------------- | ---------------------------------------- |
| **Belum ada pengajuan**     | Tidak ada perubahan yang sedang diproses |
| **Menunggu validasi admin** | File sudah diajukan                      |
| **Sedang diperiksa**        | Admin sedang mengecek file               |
| **Ditolak**                 | File salah/korup/tidak sesuai            |
| **Disetujui**               | Perubahan diterima                       |
| **Diterapkan**              | Boundary baru sudah aktif                |
| **Gagal diterapkan**        | Approval ada, tetapi proses update gagal |

Untuk versi minimal:

- Belum ada pengajuan
- Menunggu validasi admin
- Ditolak
- Disetujui
- Diterapkan

#### 8.3 Modal warning sudah benar, tetapi copy perlu lebih spesifik

Copy sekarang terlalu luas karena menyebut “semua data estate”. Itu bisa membuat user mengira data historis atau seluruh data aplikasi akan hilang.

Rekomendasi modal:

```text
Konfirmasi Pengajuan Perubahan Estate

File yang Anda ajukan akan ditinjau oleh admin sebelum diterapkan. Admin akan memeriksa apakah file valid, tidak korup, dan sesuai dengan area estate yang benar.

Jika disetujui, data batas estate/blok saat ini akan digantikan dan dapat memengaruhi peta serta hasil analisis terkait.

[Batal] [Lanjut ke Upload File]
```

#### 8.4 Form pengajuan perlu metadata tambahan

Selain file, form sebaiknya meminta:

- Jenis perubahan:
  - Batas estate
  - Batas blok
  - Batas estate + blok
- File geospasial
- Catatan perubahan
- Tanggal efektif, opsional
- Kontak penanggung jawab, opsional

#### 8.5 Harus ada alasan penolakan dari admin

Jika ditolak, manager harus tahu alasan spesifik.

Contoh:

> **Status: Ditolak**  
> File tidak dapat diproses karena geometri polygon tidak valid dan terdapat area di luar boundary estate Sumbawa.

### Prioritas perbaikan Perubahan Estate

| Prioritas    | Perbaikan                                                    |
| ------------ | ------------------------------------------------------------ |
| Critical     | Ganti status `—` dengan status workflow                      |
| Critical     | Revisi modal warning agar spesifik ke data batas estate/blok |
| Important    | Jelaskan bahwa admin akan validasi sebelum diterapkan        |
| Important    | Tambahkan field jenis perubahan dan catatan perubahan        |
| Nice-to-have | Tambahkan riwayat pengajuan dan alasan penolakan             |

---

## 9. Notifikasi / Preferensi Email

### Diagnosis

Jika notifikasi sistem belum diterapkan dan komunikasi mayoritas melalui email, tab **Notifikasi** sebaiknya diganti menjadi **Preferensi Email** atau disembunyikan sementara.

Dalam bentuk sekarang, tab Notifikasi menciptakan ekspektasi fitur yang belum ada.

### Masalah utama

#### 9.1 Nama “Notifikasi” terlalu menjanjikan

User akan mengira aplikasi punya sistem notifikasi internal seperti inbox, bell icon, alert center, atau riwayat notifikasi.

Jika implementasi saat ini berbasis email, gunakan:

- **Preferensi Email**
- **Email & Zona Waktu**

#### 9.2 Istilah “pipeline” terlalu teknis

Ganti:

- **Notifikasi ketika pipeline gagal** → **Email saat pemrosesan data gagal**
- **Notifikasi ketika pipeline berhasil** → **Email saat pemrosesan data berhasil**

Atau:

- **Kirim email jika akuisisi/analisis data gagal**
- **Kirim email jika akuisisi/analisis data selesai**

#### 9.3 Tidak jelas email dikirim ke mana

Tambahkan:

> Notifikasi akan dikirim ke: **email akun pengguna**

Contoh:

> Notifikasi akan dikirim ke: **dikoharyadhanto74@gmail.com**

#### 9.4 Zona waktu perlu konteks

Tambahkan microcopy:

> Zona waktu digunakan untuk menampilkan waktu akuisisi, jadwal pemrosesan, dan email notifikasi.

### Rekomendasi struktur

```text
Preferensi Email & Zona Waktu

Zona Waktu
[Asia/Jakarta (WIB)]

Email notifikasi
Notifikasi akan dikirim ke: user@example.com

[x] Kirim email jika pemrosesan data gagal
    Disarankan aktif agar Anda tahu ketika data tidak berhasil diperbarui.

[ ] Kirim email jika pemrosesan data berhasil
    Opsional. Aktifkan jika Anda ingin menerima konfirmasi setiap proses selesai.

[Simpan Preferensi]
```

### Prioritas perbaikan Notifikasi

| Prioritas    | Perbaikan                                                 |
| ------------ | --------------------------------------------------------- |
| Critical     | Rename tab menjadi “Preferensi Email” atau hide sementara |
| Important    | Ganti “pipeline” menjadi “pemrosesan data”                |
| Important    | Tampilkan alamat email penerima                           |
| Nice-to-have | Jelaskan fungsi zona waktu                                |

---

## 10. Sidebar dan Fitur Fase 2

### Diagnosis

Menu Fase 2 di sidebar menciptakan ekspektasi fitur yang belum tersedia.

Menu yang terlihat:

- Long-Term Trends
- Model Studio
- Alerts & Tasking
- Reports & Export

Untuk aplikasi yang masih fokus ke fungsi inti, menampilkan terlalu banyak fitur terkunci dapat membuat produk terlihat belum matang.

### Rekomendasi

Sembunyikan fitur Fase 2 sampai siap.

Sidebar sementara cukup berisi:

- Dashboard
- Explore Map
- Time-Series Analyzer
- Profil Saya
- Pengaturan
- Logout

Jika tetap ingin ditampilkan, gunakan visual yang sangat low-emphasis:

- ikon lock kecil,
- tooltip “Akan tersedia di fase berikutnya”,
- tanpa badge yang terlalu menarik perhatian.

### Prioritas

| Prioritas    | Perbaikan                                                     |
| ------------ | ------------------------------------------------------------- |
| Important    | Hide fitur Fase 2 untuk mengurangi kesan produk belum selesai |
| Nice-to-have | Gunakan tooltip roadmap jika fitur tetap ditampilkan          |

---

## 11. Prioritas Perbaikan Global

### Critical

1. **Buat empty state eksplisit di Dashboard, Explore Map, dan Time-Series.**
2. **Auto-focus Explore Map ke estate/blok aktif.**
3. **Ganti `N/A`, `—`, dan status kosong generik dengan label yang spesifik.**
4. **Ganti aksi “Hapus” user menjadi “Cabut Akses” dengan confirmation modal.**
5. **Revisi workflow Perubahan Estate sebagai pengajuan yang divalidasi admin.**

### Important

1. **Hide fitur Fase 2 dari sidebar.**
2. **Tambahkan preview pada pengaturan Branding & Header.**
3. **Rename Notifikasi menjadi Preferensi Email jika sistem notifikasi belum ada.**
4. **Perjelas read-only field di Profile.**
5. **Sembunyikan kontrol yang belum relevan saat data kosong.**

### Nice-to-have

1. Tambahkan detail popup saat klik polygon blok.
2. Tambahkan riwayat pengajuan perubahan estate.
3. Tambahkan show/hide password dan strength validation.
4. Tambahkan status invitation pada Kelola Anggota.
5. Tambahkan reset branding ke default.

---

## 12. Kesimpulan Umum

Fondasi visual CanopySense sudah cukup baik: rapi, konsisten, dan punya struktur dashboard enterprise. Masalah utamanya bukan estetika dasar, melainkan **komunikasi state kosong, clarity workflow, dan trust pada fitur sensitif**.

Dalam kondisi data belum diproses, aplikasi harus mengatakan:

> “Sistem sudah mengenali estate dan blok. Data analitik belum tersedia. Ini statusnya, dan ini langkah berikutnya.”

Bukan membiarkan user melihat:

> `N/A`, `—`, `0%`, atau “Tidak ada data” tanpa konteks.

Perubahan yang paling cepat menaikkan kualitas UX:

1. Gunakan bahasa **belum diproses / belum tersedia / siap dianalisis** secara konsisten.
2. Auto-focus peta ke estate/blok aktif.
3. Hide fitur yang belum siap.
4. Tambahkan preview branding.
5. Perlakukan user management dan perubahan estate sebagai fitur sensitif dengan konfirmasi, status, dan penjelasan konsekuensi yang jelas.

Jika ini diperbaiki, aplikasi akan tetap terasa profesional meskipun data masih kosong.

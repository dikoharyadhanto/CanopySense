# Review i18n Aplikasi CanopySense

## Tujuan Dokumen

Dokumen ini merangkum arahan pengembangan **i18n / internationalization** untuk aplikasi CanopySense. Fokusnya bukan langsung membuat aplikasi full bilingual, tetapi menyiapkan struktur agar aplikasi **Indonesia-first** namun tetap **English-ready**.

Keputusan utama:

> CanopySense sebaiknya menggunakan Bahasa Indonesia sebagai bahasa utama untuk fase awal, tetapi seluruh copy penting perlu disiapkan dalam struktur i18n agar mudah ditambahkan Bahasa Inggris nanti.

---

## 1. Apa itu i18n?

**i18n** adalah singkatan dari **internationalization**.

Istilah ini berarti proses membuat aplikasi siap mendukung lebih dari satu bahasa/lokal tanpa perlu membongkar ulang komponen UI, email, status, format tanggal, dan pesan error.

Contoh:

Tanpa i18n:

```tsx
<h1>Data NDVI belum tersedia</h1>
```

Dengan i18n:

```tsx
<h1>{t("dashboard.empty.noNdvi.title")}</h1>
```

Lalu teksnya disimpan di file bahasa:

```json
{
  "dashboard": {
    "empty": {
      "noNdvi": {
        "title": "Data NDVI belum tersedia"
      }
    }
  }
}
```

Jika nanti butuh Bahasa Inggris, cukup tambahkan file `en.json`:

```json
{
  "dashboard": {
    "empty": {
      "noNdvi": {
        "title": "NDVI data is not available yet"
      }
    }
  }
}
```

---

## 2. Strategi Bahasa Produk

### Rekomendasi

Gunakan pendekatan:

> **Indonesia-first, English-ready.**

Artinya:

- UI default menggunakan Bahasa Indonesia.
- Struktur copy sudah siap diterjemahkan.
- Istilah teknis tertentu tetap boleh menggunakan English.
- English UI bisa ditambahkan nanti tanpa refactor besar.

### Alasan

CanopySense saat ini kuat di konteks Indonesia:

- perkebunan karet,
- estate,
- afdeling,
- blok,
- WIB,
- user operasional lokal,
- komunikasi email berbahasa Indonesia.

Namun peluang penggunaan luar negeri tetap mungkin karena domain remote sensing, vegetation monitoring, dan plantation analytics bisa bersifat global. Karena itu, aplikasi tidak boleh terlalu hardcoded ke Bahasa Indonesia.

---

## 3. Prinsip Bahasa UI

### 3.1 User-facing UI menggunakan Bahasa Indonesia

Area berikut sebaiknya memakai Bahasa Indonesia:

- dashboard manager/viewer,
- empty state,
- warning,
- confirmation modal,
- pengaturan akun,
- kelola anggota,
- pengajuan perubahan estate,
- email user,
- pesan error,
- status pipeline.

Contoh:

```text
Data NDVI belum tersedia

Estate dan blok sudah terdaftar, tetapi data satelit belum diproses.
```

Bukan:

```text
No NDVI data available.
```

Untuk user awal Indonesia, clarity lebih penting daripada kesan global.

---

### 3.2 Istilah teknis boleh hybrid

Beberapa istilah tidak perlu dipaksakan diterjemahkan penuh.

| Konsep | Label Indonesia yang Disarankan | Label English Nanti |
|---|---|---|
| Company | Organisasi | Organization |
| Estate | Estate | Estate |
| Afdeling | Afdeling | Division / Management Unit |
| Block | Blok | Block |
| Pipeline | Pipeline / Pemrosesan Data | Pipeline / Data Processing |
| Raster | Raster | Raster |
| Backfill | Backfill Historis | Historical Backfill |
| Manager | Manager | Manager |
| Viewer | Viewer | Viewer |
| Super Admin | Super Admin | Super Admin |
| Audit Log | Audit Log / Log Audit | Audit Log |
| Schedule | Jadwal Pipeline | Pipeline Schedule |
| No New Data | Tidak Ada Data Baru | No New Data |

Catatan penting:

- Jangan menggunakan `company`, `perusahaan`, dan `organisasi` secara acak.
- Untuk user-facing, lebih aman gunakan **Organisasi**.
- Untuk backend/internal, `company` tetap boleh.

---

## 4. Yang Harus Dipersiapkan dari Sekarang

### 4.1 Pisahkan teks UI dari komponen

Jangan hardcode teks panjang langsung di komponen.

Buruk:

```tsx
<h1>Data NDVI belum tersedia</h1>
<p>Estate dan blok sudah terdaftar, tetapi data satelit belum diproses.</p>
```

Lebih baik:

```tsx
<h1>{t("dashboard.empty.noNdvi.title")}</h1>
<p>{t("dashboard.empty.noNdvi.description")}</p>
```

Dengan file `id.json`:

```json
{
  "dashboard": {
    "empty": {
      "noNdvi": {
        "title": "Data NDVI belum tersedia",
        "description": "Estate dan blok sudah terdaftar, tetapi data satelit belum diproses."
      }
    }
  }
}
```

---

### 4.2 Buat folder i18n

Struktur minimal:

```text
src/
  i18n/
    locales/
      id.json
      en.json
    index.ts
    glossary.ts
```

Untuk tahap awal:

- `id.json` wajib dibuat.
- `en.json` boleh kosong atau belum lengkap.
- Struktur tetap disiapkan agar English bisa ditambahkan nanti.

---

### 4.3 Tentukan default locale

Untuk fase sekarang:

```ts
const defaultLocale = "id";
const supportedLocales = ["id", "en"];
```

Aplikasi tetap default Bahasa Indonesia.

---

### 4.4 Buat fungsi `t()`

Jika belum ingin memakai library, bisa mulai dari fungsi sederhana.

```ts
import id from "./locales/id.json";
import en from "./locales/en.json";

type Locale = "id" | "en";

const dictionaries = {
  id,
  en,
};

let currentLocale: Locale = "id";

export function setLocale(locale: Locale) {
  currentLocale = locale;
}

export function t(key: string): string {
  const dictionary = dictionaries[currentLocale] || dictionaries.id;

  const value = key.split(".").reduce<any>((obj, part) => {
    return obj?.[part];
  }, dictionary);

  if (typeof value === "string") {
    return value;
  }

  const fallback = key.split(".").reduce<any>((obj, part) => {
    return obj?.[part];
  }, dictionaries.id);

  return typeof fallback === "string" ? fallback : key;
}
```

Contoh pemakaian:

```tsx
import { t } from "@/i18n";

export function DashboardEmptyState() {
  return (
    <div>
      <h2>{t("dashboard.empty.noNdvi.title")}</h2>
      <p>{t("dashboard.empty.noNdvi.description")}</p>
    </div>
  );
}
```

---

## 5. Prioritas Migrasi dari Hardcoded Text

Jangan langsung migrasi seluruh aplikasi. Mulai dari bagian dengan dampak UX paling tinggi.

### Prioritas 1 — Wajib

Pindahkan teks berikut ke translation key terlebih dahulu:

- empty state,
- warning,
- confirmation modal,
- error message,
- status label,
- CTA button,
- pesan sukses/gagal,
- email transactional.

Contoh teks prioritas:

```text
Data NDVI belum tersedia
Belum siap diterapkan
Cabut Akses
Pengajuan menunggu validasi admin
Pipeline hanya memproses data baru
Tidak ada data baru
Estate aktif akan diganti
```

---

### Prioritas 2 — Penting

Pindahkan:

- sidebar menu,
- page title,
- table header,
- form label,
- tooltip,
- helper text.

---

### Prioritas 3 — Nanti

Pindahkan:

- admin/debug page,
- data viewer label,
- audit log raw technical metadata,
- developer-facing internal notes.

---

## 6. Standarkan Status

Jangan tampilkan status mentah dari backend ke user.

Backend mungkin menyimpan:

```ts
"not_processed"
"processing"
"available"
"no_new_data"
"failed"
"partial_success"
```

Frontend harus mapping ke label manusiawi.

Contoh:

```ts
export const statusLabelKeys = {
  not_processed: "status.notProcessed",
  processing: "status.processing",
  available: "status.available",
  no_new_data: "status.noNewData",
  failed: "status.failed",
  partial_success: "status.partialSuccess",
} as const;
```

Di `id.json`:

```json
{
  "status": {
    "notProcessed": "Belum diproses",
    "processing": "Sedang diproses",
    "available": "Tersedia",
    "noNewData": "Tidak ada data baru",
    "failed": "Gagal",
    "partialSuccess": "Berhasil sebagian"
  }
}
```

Di UI:

```tsx
<span>{t(statusLabelKeys[status])}</span>
```

### Status yang perlu distandarkan di CanopySense

| Backend Key | Label Indonesia | Label English |
|---|---|---|
| `not_processed` | Belum diproses | Not processed |
| `processing` | Sedang diproses | Processing |
| `available` | Tersedia | Available |
| `no_new_data` | Tidak ada data baru | No new data |
| `skipped_existing` | Data tersimpan dilewati | Existing data skipped |
| `failed` | Gagal | Failed |
| `partial_success` | Berhasil sebagian | Partial success |
| `pending_review` | Menunggu validasi | Pending review |
| `approved` | Disetujui | Approved |
| `rejected` | Ditolak | Rejected |
| `active` | Aktif | Active |
| `inactive` | Tidak aktif | Inactive |

---

## 7. Empty State Harus Distandarkan

Empty state adalah area paling penting karena user sering bingung saat data kosong.

### Contoh key untuk dashboard

```json
{
  "dashboard": {
    "empty": {
      "noMembership": {
        "title": "Anda belum tergabung ke organisasi mana pun",
        "description": "Akun Anda sudah aktif, tetapi belum memiliki akses ke data monitoring CanopySense. Minta manager organisasi Anda untuk mengirim undangan ke email akun ini."
      },
      "noNdvi": {
        "title": "Data NDVI belum tersedia",
        "description": "Estate dan blok sudah terdaftar, tetapi data satelit belum diproses."
      },
      "noSatelliteData": {
        "title": "Belum ada data satelit",
        "description": "Data akan muncul setelah pipeline pertama berhasil memproses data satelit untuk estate ini."
      }
    }
  }
}
```

### Empty state penting di CanopySense

- user belum tergabung organisasi,
- estate belum dikonfigurasi,
- data satelit belum tersedia,
- NDVI belum diproses,
- time-series belum dibangun,
- pipeline history kosong,
- schedule belum dibuat,
- audit log kosong,
- estate change request kosong.

---

## 8. Email Harus Bilingual-Ready

Email tidak boleh ditulis langsung sebagai string panjang di logic backend.

Struktur yang disarankan:

```text
emails/
  templates/
    id/
      verification-code.html
      manager-invitation.html
      estate-change-request.html
      estate-change-approved.html
      estate-change-rejected.html
      pipeline-failed.html
    en/
      verification-code.html
      manager-invitation.html
      estate-change-request.html
      estate-change-approved.html
      estate-change-rejected.html
      pipeline-failed.html
```

Untuk fase awal, cukup buat folder `id/`. Folder `en/` bisa ditambahkan nanti.

### Variabel template

Gunakan variabel, bukan hardcoded.

```text
{{user_name}}
{{company_name}}
{{organization_name}}
{{verification_code}}
{{expires_in_minutes}}
{{setup_link}}
{{reject_reason}}
{{pipeline_run_id}}
{{estate_name}}
```

Contoh buruk:

```text
Tautan ini berlaku selama 1 jam.
```

Lebih baik:

```text
Tautan ini berlaku selama {{expires_in_minutes}} menit.
```

---

## 9. Format Tanggal, Angka, dan Timezone

Jangan hardcode format tanggal manual.

Gunakan formatter berbasis locale.

```ts
export function formatDateTime(
  date: string | Date,
  locale: "id" | "en" = "id",
  timeZone = "Asia/Jakarta"
) {
  return new Intl.DateTimeFormat(locale === "id" ? "id-ID" : "en-US", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone,
  }).format(new Date(date));
}
```

Untuk angka:

```ts
export function formatNumber(value: number, locale: "id" | "en" = "id") {
  return new Intl.NumberFormat(locale === "id" ? "id-ID" : "en-US").format(value);
}
```

Contoh:

| Locale | Tanggal |
|---|---|
| `id-ID` | 31 Mei 2026, 15.51 |
| `en-US` | May 31, 2026, 3:51 PM |

Ini penting untuk:

- waktu akuisisi,
- jadwal pipeline,
- run history,
- audit log,
- email,
- archive retention,
- subscription/access plan,
- NDVI value,
- coverage percentage.

---

## 10. Simpan Preferensi Bahasa

Belum perlu membuat language switcher sekarang. Tapi field dapat disiapkan.

Rekomendasi:

```text
users.preferred_locale = "id"
companies.default_locale = "id"
```

Aturan fallback:

1. Jika user punya `preferred_locale`, gunakan itu.
2. Jika tidak, gunakan `company.default_locale`.
3. Jika tidak, fallback ke `id`.

Contoh:

```text
preferred_locale = "en"
```

Maka UI dan email dapat menggunakan English untuk user tersebut.

---

## 11. Glossary Produk

Buat dokumen atau file khusus glossary agar istilah konsisten.

Contoh `glossary.ts`:

```ts
export const glossary = {
  company: {
    id: "Organisasi",
    en: "Organization"
  },
  estate: {
    id: "Estate",
    en: "Estate"
  },
  afdeling: {
    id: "Afdeling",
    en: "Division"
  },
  block: {
    id: "Blok",
    en: "Block"
  },
  pipeline: {
    id: "Pipeline",
    en: "Pipeline"
  }
};
```

### Catatan istilah “Afdeling”

`Afdeling` cocok untuk konteks Indonesia/perkebunan tertentu, tetapi belum tentu dipahami user luar negeri. Secara data model, lebih aman jika konsep ini disiapkan sebagai:

```text
management_unit
```

Label Indonesia tetap bisa “Afdeling”. Label English bisa “Division” atau “Management Unit”.

---

## 12. Rekomendasi Struktur Key

Gunakan key yang deskriptif dan stabil.

Contoh:

```json
{
  "common": {
    "save": "Simpan",
    "cancel": "Batal",
    "delete": "Hapus",
    "edit": "Ubah",
    "loading": "Memuat..."
  },
  "navigation": {
    "dashboard": "Dashboard",
    "exploreMap": "Peta Eksplorasi",
    "timeSeries": "Analisis Time-Series",
    "profile": "Profil",
    "settings": "Pengaturan"
  },
  "pipeline": {
    "trigger": {
      "title": "Jalankan Pipeline Manual",
      "description": "Jalankan pipeline secara manual untuk mengambil data terbaru atau membangun data historis."
    },
    "schedule": {
      "title": "Jadwal Pipeline",
      "skipExistingNote": "Pipeline hanya memproses data satelit baru yang belum tersimpan. Jika tidak ada data baru, run akan dicatat sebagai tidak ada pembaruan."
    },
    "history": {
      "emptyTitle": "Belum ada riwayat pipeline",
      "emptyDescription": "Belum ada pipeline run yang pernah dijalankan."
    }
  },
  "estate": {
    "active": "Estate Aktif",
    "replaceActive": "Ganti Estate Aktif",
    "blockCodeAuto": "Kode blok dibuat otomatis. Setiap polygon dianggap sebagai satu blok."
  }
}
```

---

## 13. Library yang Bisa Dipakai Nanti

Jika stack aplikasi menggunakan React/Next.js, pendekatan manual `t()` bisa dikembangkan ke library:

- `next-intl`,
- `react-i18next`,
- `next-i18next`.

Untuk fase awal, fungsi `t()` sederhana sudah cukup. Yang penting adalah kebiasaan tidak hardcode teks.

---

## 14. Checklist Implementasi

### Tahap 1 — Minimal

- [ ] Buat folder `src/i18n/locales/`
- [ ] Buat `id.json`
- [ ] Buat `en.json` placeholder
- [ ] Buat fungsi `t()`
- [ ] Pindahkan empty state ke translation key
- [ ] Pindahkan warning/modal ke translation key
- [ ] Pindahkan status label ke translation key
- [ ] Buat glossary istilah produk
- [ ] Pindahkan email template ke folder terpisah

### Tahap 2 — Setelah Stabil

- [ ] Tambahkan `preferred_locale` di user
- [ ] Tambahkan `default_locale` di company/organization
- [ ] Tambahkan formatter tanggal dan angka berbasis locale
- [ ] Migrasi sidebar/menu/table header ke translation key
- [ ] Migrasi semua email transactional ke template berbasis locale

### Tahap 3 — Jika Mulai Dipakai User Luar

- [ ] Lengkapi `en.json`
- [ ] Tambahkan pilihan bahasa di Profile/Settings
- [ ] Translate email template English
- [ ] Uji semua empty state dalam English
- [ ] Uji format tanggal, angka, dan timezone
- [ ] Review istilah Afdeling/Block/Estate untuk konteks global

---

## 15. Brutal Audit: Risiko Jika Tidak Disiapkan

Jika i18n tidak disiapkan dari sekarang, risiko yang akan muncul:

1. Copy tersebar hardcoded di banyak komponen.
2. Bahasa campur Indonesia-English tanpa pola.
3. Empty state sulit diseragamkan.
4. Status backend seperti `not_processed` atau `no_new_data` bisa bocor ke UI.
5. Email sulit diterjemahkan karena tertanam di logic backend.
6. Admin UI makin sulit dirapikan karena banyak label teknis.
7. Saat butuh English, harus refactor besar.
8. Produk terlihat belum matang karena istilah berubah-ubah antar halaman.

---

## Kesimpulan

CanopySense tidak perlu langsung full bilingual. Namun, aplikasi harus mulai dikembangkan dengan struktur i18n sejak sekarang.

Keputusan terbaik:

> **Default Bahasa Indonesia, tetapi semua copy penting dikelola melalui translation key agar English bisa ditambahkan nanti.**

Prioritas praktis:

1. Stop hardcode teks untuk empty state, warning, modal, status, dan email.
2. Buat `id.json`.
3. Buat fungsi `t()`.
4. Standarkan istilah produk.
5. Pisahkan email template dari logic backend.
6. Siapkan `preferred_locale` dan `default_locale` untuk fase berikutnya.

Ini akan menjaga CanopySense tetap jelas untuk user awal Indonesia, tetapi tidak terkunci jika nanti perlu dipakai oleh user luar negeri.

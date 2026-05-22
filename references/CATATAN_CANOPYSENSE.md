# CATATAN RINGKASAN: CANOPY SENSE - MONITORING KERAPATAN KANOPI PERKEBUNAN KARET

**Tanggal Catatan:** 21 Mei 2026  
**Sumber:** CanopySense_Dokumen_Teknis.md (v3.0) + Rekomendasi_Dokumentasi_Skema_Database_PostGIS  
**Status:** Pemahaman Fase Permulaan (Pre-Intent)

---

## 1. GAMBARAN UMUM PROYEK

### Visi & Tujuan Inti

**CanopySense** adalah aplikasi **monitoring perkebunan karet berbasis cloud** yang mengubah citra satelit optik menjadi indikator **Green Canopy Cover (GCC)** yang konsisten menggunakan Machine Learning.

**Tujuan Utama (3 pilar):**

1. Mengubah citra satelit → indikator GCC% yang konsisten (berbasis ML + data lapangan)
2. Menyediakan peringatan dini ketika kanopi menurun abnormal (vs. gugur daun musiman)
3. Memberikan ringkasan spasial & tren jangka panjang (5-10 tahun per blok/estate)

### Target Pengguna

- **Manajer Estate / Agronom / QC Kebun:** Monitoring operasional harian/mingguan
- **Tim Riset Perusahaan / Universitas:** Analisis fenologi dan produktivitas
- **Tim Penyakit Tanaman / Sustainability:** Health monitoring dan deforestasi

---

## 2. ARSITEKTUR DATA & TEKNOLOGI

### Stack Teknologi Utama

**Backend:**

- Framework: FastAPI (Python 3.10+)
- Database: PostgreSQL 16+ + PostGIS (spatial queries)
- Cache: Redis
- Task Queue: Celery (untuk batch processing)
- ML: scikit-learn, XGBoost, statsmodels (untuk STL decomposition)
- Satellite API: Google Earth Engine (GEE)

**Frontend:**

- Framework: React 18 + TypeScript
- Mapping: Leaflet / MapLibre GL JS
- Charts: Plotly.js / Recharts
- State: Redux Toolkit

**Infrastructure:**

- Cloud: Google Cloud Platform (GCP)
- Containerization: Docker + Docker Compose
- Orchestration: Kubernetes (GKE)
- CI/CD: GitHub Actions / GitLab CI
- Monitoring: Prometheus + Grafana

---

## 3. PIPELINE DATA & MACHINE LEARNING

### Alur Pemrosesan Data (7 Tahap)

```
Citra Satelit (Sentinel-2, Landsat-8/9)
        ↓
Cloud Masking & Atmospheric Correction
        ↓
Perhitungan 5 Indeks Vegetasi (NDVI, EVI, NDRE, SAVI, GNDVI)
        ↓
Integrasi Data Ground-Truth Lapangan (GCC%)
        ↓
Training Model ML (Random Forest / XGBoost)
        ↓
Output: Prediksi GCC (%)
        ↓
Deteksi Anomali (STL Decomposition) + Alert Generation
```

### Sumber Data Satelit

1. **Sentinel-2 MSI (Utama)**
   
   - Resolusi: 10-20m
   - Temporal: 5 hari (A+B)
   - Gratis (Copernicus)
   - Keunggulan: Red-edge bands untuk deteksi stres

2. **Landsat-8/9 (Backup & Historis)**
   
   - Resolusi: 30m
   - Temporal: 8-16 hari
   - Gratis (USGS)
   - Keunggulan: Arsip sejak 1984

3. **Planet PlanetScope (Opsional)**
   
   - Resolusi: 3-5m
   - Temporal: Harian
   - Berbayar (komersial)

### Model Machine Learning

**Random Forest Regressor (Baseline):**

- Target R² > 0.80
- Robust terhadap overfitting
- Interpretable (feature importance mudah dipahami)

**XGBoost Regressor (Advanced):**

- Potensi R² 0.85-0.90
- Sequential learning untuk perbaikan error
- Built-in regularization (L1/L2)

### Deteksi Anomali (STL Decomposition)

Sistem membedakan **gugur daun musiman (normal)** vs **anomali penurunan kanopi (abnormal)** menggunakan:

```
GCC_observed = Trend + Seasonal + Residual
```

- **Trend:** Tren jangka panjang (naik/turun per tahun)
- **Seasonal:** Pola musiman berulang (fenologi normal)
- **Residual:** Deviasi dari pola normal (anomali = penyakit, stres, defoliasi)

Threshold: Anomali terdeteksi jika residual > ±2 SD dari baseline

---

## 4. SKEMA DATABASE POSTGIS

### Hierarki Spasial (3 Level)

1. **estates** (MultiPolygon)
   
   - Level makro: unit kebun utama
   - Kolom kunci: id, name, code, geometry, area_ha (generated)
   - Index: GiST pada geometry + envelope

2. **afdelings** (MultiPolygon)
   
   - Level menengah: pembagian lahan di bawah estate
   - Foreign Key: estate_id
   - Index: GiST pada geometry

3. **blocks** (Polygon)
   
   - Level mikro: unit operasional utama
   - Kolom kunci: id, name, code, plant_year, clone_type, geometry, area_ha (generated)
   - Foreign Key: afdeling_id
   - Index: GiST pada geometry

### Tabel Data Analitik (Time-Series & Operasional)

| Tabel                 | Fungsi                                                                                | Karakteristik                                                     |
| --------------------- | ------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| **satellite_data**    | Menyimpan hasil preprocessing satelit (NDVI, EVI, NDRE, SAVI, GNDVI, cloud_cover)     | Immutable; unique constraint (block_id, acquisition_date, sensor) |
| **ground_truth**      | Data pengukuran lapangan GCC% dari UAV, hemispherical photo, atau visual assessment   | Training data untuk ML model                                      |
| **predictions**       | Output prediksi GCC% per satellite_data; track model_version untuk A/B testing        | Append-only (history tracking)                                    |
| **anomalies**         | Deteksi anomali dari residual STL; status tracking (OPEN → VERIFIED → RESOLVED)       | Linked ke predictions_id untuk traceability                       |
| **alerts**            | Notifikasi peringatan kepada user berdasarkan anomalies                               | Linked ke anomalies_id + user_id                                  |
| **field_inspections** | Hasil inspeksi lapangan (findings, photos, actual_gcc); trigger update pada anomalies | JSONB untuk array foto                                            |
| **users**             | Manajemen autentikasi & profil pengguna                                               | Linked ke user_estate_roles untuk RBAC                            |
| **user_estate_roles** | Relasi Many-to-Many (users ↔ estates/afdelings/blocks); mendefinisikan role & scope   | Supports scoped access control                                    |

### Optimasi Performa Database

**Spatial Indexing:**

- GiST (Generalized Search Tree) R-Tree pada semua kolom geometry
- CLUSTER blocks USING idx_blocks_geometry untuk query performa optimal

**Time-Series Indexing:**

- Composite index: (block_id, acquisition_date DESC)
- Composite index: (block_id, prediction_date DESC)
- Composite index: (block_id, detection_date DESC)

---

## 5. MODUL APLIKASI (7 Komponen)

### A. Dashboard Utama (Executive View)

- KPI: GCC harian/mingguan (%)
- Peta status blok: Normal/Waspada/Kritis
- Ringkasan perubahan: ΔMingguan, ΔBulanan, ΔYear-over-Year
- Top 10 blok perlu inspeksi

### B. Explore Map (Peta Interaktif)

- Visualisasi GCC% per blok (color ramp: Merah→Kuning→Hijau)
- Toggle layer indeks vegetasi (NDVI, EVI, NDRE, SAVI, GNDVI)
- Quality layer (awan mask + confidence level)
- Drill-down: Estate → Afdeling → Blok → Pixel sample

### C. Time-Series Analyzer

- Line chart GCC mingguan/bulanan + confidence interval
- Overlay indeks vegetasi (NDVI, EVI, NDRE)
- STL decomposition: Trend + Seasonal + Residual
- Event tagging (penyakit, leaf fall, pruning, drought, dll)

### D. Long-Term Trend Analysis (5-10 Tahun)

- Slope tren (naik/turun per tahun)
- Stabilitas (variansi musiman)
- Deteksi regime shift (perubahan permanen)
- Year-over-Year comparison heatmap

### E. Model & Prediction Studio (Tim Teknis)

- Model management (baseline vs. versi terbaru)
- Metrik performa: R², RMSE, MAE
- Feature importance (kontribusi indeks vegetasi)
- Explainability: SHAP values per blok

### F. Alerts & Tasking (Operasional)

- Alert rules: Penurunan GCC cepat (>15% dalam 2-3 minggu), anomali residual tinggi, confidence rendah
- Workflow inspeksi: Create task → Upload foto/observasi → Data menjadi validasi untuk retraining

### G. Reports & Export

- Monthly Canopy Health Report (PDF)
- Anomaly & Inspection List (CSV)
- 10-Year Trend Summary (PDF)
- GeoPackage / GeoJSON (untuk GIS integration)
- Cloud Optimized GeoTIFF (COG) untuk distribusi hasil raster

---

## 6. ROADMAP IMPLEMENTASI (4 FASE MVP)

### Fase 1: Core Foundation (Bulan 1-3)

- Autentikasi & manajemen user (OAuth 2.0, RBAC)
- Upload & CRUD hierarki kebun (shapefile/GeoJSON)
- Integrasi GEE, akuisisi Sentinel-2/Landsat
- Perhitungan 5 indeks vegetasi
- Peta viewer dasar + time-series viewer NDVI/EVI

**Success Criteria:** User dapat login, melihat peta estate, time-series vegetasi indices

### Fase 2: ML Model & Predictions (Bulan 4-6)

- Input data ground-truth GCC% (form + batch CSV)
- Training pipeline Random Forest
- Batch prediction GCC% untuk semua blok
- Dashboard utama (KPI, peta status, top 10 blok)
- Enhanced time-series (GCC predicted + confidence interval)

**Success Criteria:** Model R² > 0.75, prediksi ter-update otomatis setiap minggu

### Fase 3: Anomaly Detection & Alerts (Bulan 7-9)

- STL decomposition (Trend + Seasonal + Residual)
- Anomaly detection engine (±2 SD threshold)
- Alert system (email/SMS notifications)
- Field inspection workflow (mobile-friendly, foto + notes)
- Reports & export (PDF, CSV, GeoPackage, COG)

**Success Criteria:** Sistem membedakan gugur daun vs. anomali, alert dalam <24 jam

### Fase 4: Advanced Features (Bulan 10-12, Optional)

- Long-term trend analysis + regime shift detection
- Model studio (versioning, A/B testing, SHAP explainability)
- Mobile app (Flutter)
- Multi-tenant support
- Public API (REST + rate limiting)

---

## 7. METODE PENGUKURAN GREEN CANOPY COVER LAPANGAN (Ground-Truth)

### 3 Metode yang Didukung:

1. **Hemispherical Photography (Standar)**
   
   - Alat: Kamera fisheye lens + tripod
   - Output: GCC% dengan akurasi tinggi
   - Kelebihan: Standar ilmiah
   - Kekurangan: Labor-intensive

2. **UAV/Drone RGB Imagery**
   
   - Alat: Drone DJI Phantom/Mavic
   - Output: GCC% per blok dari orthomosaic
   - Kelebihan: Coverage luas, cepat
   - Kekurangan: Butuh izin, cuaca dependent

3. **Visual Assessment (Praktis)**
   
   - Alat: Checklist + smartphone GPS
   - Output: GCC% estimasi (kategori: 0-20%, 20-40%, dst)
   - Kelebihan: Cepat, murah, scalable
   - Kekurangan: Subjektif

### Sampling Strategy:

- Training: 200-300 blok per estate
- Validation: 50-100 blok per estate
- Stratifikasi: Umur tanaman, klon, kondisi kesehatan, musim
- Temporal matching: ±7 hari dari akuisisi satelit

---

## 8. ROLE-BASED ACCESS CONTROL (RBAC)

| Role              | Scope               | Hak Akses                                                           |
| ----------------- | ------------------- | ------------------------------------------------------------------- |
| **Administrator** | Global (Sistem)     | System write & full control                                         |
| **Manager**       | Estate (Wilayah)    | Estate write, kurasi blok, CRUD pengguna, akses data analitik       |
| **Inspector**     | Operasional         | Eksekusi inspeksi lapangan, upload foto/notes, akses Viewer         |
| **Viewer**        | Wilayah (Read-Only) | Visualisasi peta, time-series, predictions, notifications (no edit) |

---

## 9. POIN-POIN PENTING UNTUK DIPERTIMBANGKAN

### Tantangan Teknis yang Telah Diidentifikasi:

1. **Fenologi Karet Kompleks:** Sistem harus membedakan gugur daun musiman (2-4 minggu per tahun) vs. anomali penurunan abnormal → Solusi: STL decomposition + statistical thresholding

2. **Integritas Data Historis:** Tabel satellite_data dan predictions adalah immutable (append-only) untuk menjaga konsistensi riwayat

3. **Skalabilitas Raster:** Dua metodologi tersedia:
   
   - **Vector Point-Cloud:** Fleksibel tapi risiko performa tinggi (jutaan baris)
   - **Raster/COG:** Optimal untuk peta web, tapi terpisah dari DB (S3/GCS)

4. **Traceability Anomali:** Setiap anomali harus linked ke predictions_id → field_inspections (tracking penuh dari deteksi hingga resolusi)

5. **Temporal Matching:** Ground-truth measurement harus dilakukan ±7 hari dari akuisisi satelit, idealnya same-day

---

## 10. STATUS IMPLEMENTASI AKTUAL (Berdasarkan Code Review)

### ✅ Sudah Implementasi (Phase 1 - Core Engine):

**Infrastructure & Pipeline:**

- ✅ `patcher_local.py` - Client yang berjalan di server kontraktor (Dasmap)
- ✅ `patcher_cloud.py` - Cloud Function di GCP (asia-southeast2)
- ✅ Google Earth Engine integration (akuisisi Sentinel-2, Landsat-8/9)
- ✅ Perhitungan 5 indeks vegetasi (NDVI, EVI, NDRE, SAVI, GNDVI)
- ✅ PostgreSQL+PostGIS database schema lengkap (11 tabel + relasi)
- ✅ API Key authentication system (via Secret Manager)
- ✅ Retry logic & error handling (exponential backoff)
- ✅ Cloud Logging untuk audit trail
- ✅ Tested pada local Docker PostgreSQL server

**Dokumentasi Operasional:**

- ✅ `Panduan_Teknis.md` (v0.9) - 950 lines, operasional lengkap
- ✅ `GUIDANCE.md` (v0.10) - Bilingual operations guide untuk contractors
- ✅ Onboarding workflow terdokumentasi
- ✅ Troubleshooting guides & best practices

### ⏳ Dalam Progress (Phase 2 - Test Infrastructure):

**Test Framework Implementation:**

- 🔄 `docker-compose.yml` untuk two-container topology (postgis + patcher)
- 🔄 `Dockerfile.patcher` untuk containerized patcher
- 🔄 `init.sql` dengan seed data (blocks, satellite_data, patcher_run_log)
- 🔄 `mock_cloud.py` untuk local Cloud Function simulation
- 🔄 `.env.test.example` & `.gitignore` update
- **Status:** CDC-WALK-003-v0.10b ready awaiting ANT approval on FLAG-1 (build context)

### ❌ Belum Implementasi:

**Phase 3 & 4:**

- ML Model Training (Random Forest/XGBoost)
- STL Decomposition & Anomaly Detection
- Alert System
- Field Inspection Workflow
- Dashboard & Analytics UI (React)
- Reporting & Export Features
- Long-term Trend Analysis

---

## 11. OPEN ISSUES & DECISIONS PENDING

| FLAG   | Issue                                                         | Status                | Impact                        |
| ------ | ------------------------------------------------------------- | --------------------- | ----------------------------- |
| FLAG-1 | Build context path (`context: ../03_Build` vs. `context: ..`) | Awaiting ANT approval | Dockerfile.patcher COPY paths |
| FLAG-2 | PostgreSQL sequence sharing in testschema (non-blocking)      | Noted for awareness   | Phase C testing only          |
| —      | ML model selection (RF vs XGBoost), hyperparameters           | Pending intent        | Phase 3 implementation        |
| —      | Raster (COG) vs Vector point-cloud architecture               | Pending intent        | Data storage strategy         |

---

## 12. TEAM & ROLES

**Dari Dokumentasi:**

- **Dasmap**: Kontraktor pengembang server aplikasi CanopySense
- **UI/Administrator**: Pihak yang memelihara sistem cloud & API gateway
- **Staf Operasional**: Kontraktor yang men-deploy & menjalankan patcher_local

---

## 13. STATUS PEMAHAMAN FINAL

### ✅ Sudah Dipahami:

- Visi & tujuan proyek
- Arsitektur data lengkap (11 tabel, relasi, schema)
- Tech stack & tech decisions
- Core engine implementation (patcher-local + patcher-cloud)
- Operasional procedures & onboarding workflow
- Tantangan teknis & solusinya
- Dokumentasi & knowledge base yang ada

### 🔴 Menunggu Intent User:

**Pertanyaan Kunci untuk User:**

1. **Phase & Prioritas:**
   
   - Mau lanjutkan Phase 2 (test infrastructure) dulu, atau
   - Jump ke Phase 3 (ML model training), atau
   - Setup UI/dashboard terlebih dahulu?

2. **Scope & Timeline:**
   
   - Target delivery date?
   - Team size & expertise?
   - Resource constraints?

3. **Keputusan Teknis:**
   
   - ML model preference (RF baseline vs XGBoost advanced)?
   - Storage strategy (Raster COG vs Vector point-cloud)?
   - Deployment target (GCP vs on-premise vs hybrid)?

4. **Business Priorities:**
   
   - KPI utama (accuracy, speed, cost, scalability)?
   - Which modules paling critical untuk MVP?
   - Regulatory atau compliance requirements?

---

**SIAP untuk Interview Intent dengan User.**

---

## 14. CATATAN INTENT USER (21 Mei 2026)

### Deklarasi Strategic Direction:

> **"Akibat kurangnya performa contractor (Dasmap), saya memutuskan membangun server sendiri dan web apps sendiri."**

### Scope Inti:

- **Primary Focus:** Backend server architecture + Frontend web apps (self-hosted)
- **Script Reuse:** Leverage patcher-local & patcher-cloud yang sudah exist (Phase 1 core engine)
- **Tidak fokus:** Detail script core engine, tapi dapat terintegrasi

### Request Formal:

**→ Konsultasi Backend + Frontend Tech Stack Recommendations**

---

## 15. PHASE INTERVIEW - TECH STACK CONSULTATION

Sebelum merekomendasikan tech stack, beberapa klarifikasi teknis diperlukan:

### **Kategori 1: Deployment & Infrastructure**

1. **Hosting Target:**
   
   - Self-hosted on-premises (Dasmap server)?
   - Hybrid (cloud + on-prem)?
   - Pure cloud (GCP, AWS, Azure)?

2. **Scaling Requirements:**
   
   - Expected concurrent users?
   - Number of estates/blocks to manage?
   - Expected data volume per month (satellite requests)?

### **Kategori 2: Team & Expertise**

3. **Development Team:**
   
   - Team size? (1 person, 2-3, 5+)
   - Current tech stack familiarity?
   - Backend expertise level (junior/mid/senior)?
   - Frontend expertise level?

4. **Time to Market:**
   
   - Target MVP delivery date?
   - Phase 2 (test infra) first, or skip to Phase 3 (UI)?

### **Kategori 3: Technical Constraints**

5. **Database Continuity:**
   
   - Keep PostgreSQL+PostGIS? (recommended, given current schema)
   - Any vendor lock-in constraints?

6. **API Pattern Preference:**
   
   - REST only?
   - GraphQL?
   - Real-time WebSocket for alerts?

7. **Frontend Deployment:**
   
   - Web only (React)?
   - Mobile needed (Flutter/React Native)?
   - Desktop app?

### **Kategori 4: Business/Operational**

8. **Critical Modules for MVP:**
   
   - Dashboard + Alerts first?
   - ML model + predictions first?
   - Inspector workflow first?

9. **Regulatory/Compliance:**
   
   - Data residency requirements?
   - Audit trail (logging) mandatory?
   - RBAC complexity level?

---

**Mohon berikan jawaban atas pertanyaan di atas sehingga rekomendasi tech stack dapat disesuaikan dengan context & constraints spesifik project.****

---

## 16. DEKLARASI INTENT USER - PHASE DESAIN ARSITEKTUR (21 Mei 2026, Session 2)

### Konteks Keputusan

> **Pengguna menyatakan:** "Saya buta dan butuh arahan anda. Namun saya ingin memberi intent yang jelas."

Pengguna memberikan **4 Intent Inti** yang harus menjadi fondasi desain arsitektur backend & frontend.

---

### **Intent #1: Balance Optimization - Satellite Processing vs GIS Modeling**

**Statement:**

> "Aplikasi harus balance antara optimiziation dalam pengolahan Citra Satelit dan pemodelan GIS (ini via earth engine yang mana menggunakan server google dalam pengolahan)"

**Interpretasi Teknis:**

- Pengolahan satelit (Sentinel-2, Landsat via GEE) dilakukan di Google Cloud Infrastructure
- Pemodelan GIS dan spatial queries dilakukan di PostGIS lokal (on-premise)
- Aplikasi harus orchestrate antara kedua sistem tanpa bottleneck

**Implikasi Desain:**

- Backend perlu async task queue (Celery/Bull) untuk manage long-running satellite jobs
- Perlu caching layer untuk hasil intermediate (Redis)
- API response harus mencerminkan job status (pending/processing/complete)
- WebSocket atau polling untuk real-time progress updates ke frontend

---

### **Intent #2: Account & Permission Model Revamp - One-to-Many Hierarchy**

**Statement:**

> "Saya mau manager perusahaan tidak melakukan uploading ke web, jadi perlu revisi relasi many to many jadi one to many. Yang mana satu manager mewakili satu perusahaan, akun dibuatkan dengan id company, dan company name."

**Struktur Account Baru:**

```
Company
  ├── Manager (1:1 link ke company - account utama)
  │    └── Permission: Invite users, Manage settings, View all blocks
  │
  └── Users (Many:1 link ke company via Manager's invitation)
       ├── Inspector (View + field inspection tasks)
       ├── Viewer (View only, read-only access)
       └── (Roles TBD)
```

**Rules:**

1. **Setiap user bisa membuat akun tapi TIDAK bisa menampilkan apapun** (blank canvas sampai diundang)
2. **Role Viewer memerlukan undangan langsung dari Manager** - Viewer hanya read-only
3. **Manager adalah satu-satunya yang bisa mengundang akun lain** (karyawan, delegasi internal perusahaan)
4. Account dibuatkan dengan: `id_company`, `company_name`, password sementara

**Implikasi Database:**

- Tabel `companies` (baru): id_company, company_name, metadata
- Tabel `users` refactor: Hapus direct relationship dengan estates/afdelings/blocks; tambah `company_id`
- Tabel `user_roles` refactor: Ubah dari scope (blocks/afdelings) menjadi company-level role definition
- Tabel `company_invitations` (baru): Manage undangan dari Manager ke calon users (token-based)
- Relasi: `companies.id` ← `users.company_id` ← `user_roles.user_id`

---

### **Intent #3: Hapus Upload Data Feature - Pre-Computed Backend Processing**

**Statement:**

> "Fitur upload data dihapus total. Mekanisme nya perusahaan akan mendaftar, memberikan area mereka, dan dibuatkan akun id company khusus dari pihak kami dan password smeentara (yang nanti bisa diganti passwordnya setelah login oleh manager). Karena area sudah dimasukkan sebelumnya, proses computasi backend core engine berlangsung jauh2 hari pastinya sebelum diberikannya akun company ke perusahaan melalui role manager."

**Workflow Baru:**

```
1. Company registers (offline/support form) + submits area (GeoJSON/shapefile)
   ↓
2. CanopySense team validates & processes area:
   - Insert estates/afdelings/blocks ke database
   - Trigger patcher-cloud untuk backfill satellite data (Sentinel-2/Landsat historis)
   - Run ML model training untuk blok-blok baru
   - Generate initial predictions & anomaly detection
   (DURATION: Days/Weeks, depending on historical data availability)
   ↓
3. CanopySense team creates Manager account:
   - id_company, company_name, username, temp password
   - Email ke Manager dengan credentials + onboarding guide
   ↓
4. Manager logs in, changes password, dapat full access:
   - View dashboard dengan data yang sudah pre-computed
   - Invite team members (Inspector, Viewer roles)
```

**Konsekuensi:**

- **Tidak ada real-time upload dalam aplikasi**
- **Backend data pipeline completely separate dari user-facing application**
- **Application layer = Read-Only + Invite Management + Customization ONLY**
- Perlu **admin/ops interface terpisah** untuk manage company registrations & data ingestion (tidak dalam main app)

**Implikasi Database:**

- Tabel `satellites_data`, `predictions`, `anomalies` di-populate SEBELUM Manager account diberikan
- Tabel `ground_truth` bisa tetap ada untuk future validation (Manager bisa request upload setelah live)
- Tabel `patcher_run_log` tetap exist tapi tidak user-facing
- Perlu tabel `company_onboarding_status` (baru): Track kapan company data siap (for audit trail)

---

### **Intent #4: Fitur Customisasi Tampilan Minimal (Company Branding)**

**Statement:**

> "Ada fitur customisasi tampilan minimal. Perusahaan bisa mengganti judul web aplikasi, menambahkan logo perusahaan, mengganti theme (theme disediakan beberapa pilihan, lebih ke ganti warna, harus ada salah satunya mode dark dan mode light), dll yang memungkinkan aplikasi dikustomisasi. Hanya manager yang bisa mengatur kustomisasi tampilan web."

**Customization Options:**

1. **Web Title**: Custom app name (e.g., "Estate Monitor - PT Sukses Jaya" bukan generic "CanopySense")
2. **Logo/Branding**: Company logo upload (SVG/PNG, max size TBD)
3. **Theme**: Predefined color palettes
   - Light mode (required)
   - Dark mode (required)
   - Additional branded themes (optional)
4. **Permission**: Only Manager role can edit customization

**Implikasi Database:**

- Tabel `company_settings` (baru): id_company, app_title, logo_url, theme_id, custom_css (optional)
- Tabel `themes` (baru): id, name, color_palette (JSON), light_mode, dark_mode

**Implikasi Frontend:**

- Dynamic header/navbar based on company settings
- Dynamic theme switching (CSS variables / Tailwind classes)
- Settings panel under "Admin" section (Manager only)

---

### **Ringkasan Implikasi Database Schema Revamp**

**Tabel Baru (3):**

1. `companies`: id_company, company_name, created_at
2. `company_invitations`: token, company_id, email, role, created_at, expires_at, accepted_at
3. `company_settings`: company_id, app_title, logo_url, theme_id, created_at, updated_at
4. `themes`: id, name, color_palette (JSON), light_mode_colors, dark_mode_colors

**Tabel Dimodifikasi (3):**

1. `users`: Tambah `company_id`, Hapus direct block/afdeling/estate FK, Tambah `created_by` (Manager who invited)
2. `user_roles`: Ubah scope dari block-level menjadi company-level; simplify dari (user, block, role) menjadi (user, company, role)
3. Hapus/Archive: `ground_truth_uploads`, `field_inspections` (upload feature removed) - atau keep tapi change to Manager-initiated requests

**Tabel Tetap (Unchanged):**

- `estates`, `afdelings`, `blocks` (structure sama, tapi perlu FK ke company)
- `satellite_data`, `predictions`, `anomalies` (immutable, pre-computed)

**New Relationships:**

```
companies (1) ── (Many) users
companies (1) ── (Many) company_settings
companies (1) ── (Many) blocks (+ afdelings + estates)
users (Many) ── (Many) company_invitations
themes (1) ── (Many) company_settings
```

---

### **14. STATUS PEMAHAMAN & NEXT STEPS**

**✅ Intent #1-4 sudah dicatat.**

**Pertanyaan Clarification untuk User (sebelum mulai detailed technical design):**

1. **Ground-Truth Measurement**: Apakah Manager bisa request pengukuran GCC lapangan (hemispherical photo / UAV / visual) SETELAH aplikasi live? Atau data ground-truth hanya untuk internal CanopySense team?

2. **Field Inspections**: Anomaly sudah terdeteksi pre-computation. Apakah Inspector tetap perlu upload foto/findings saat di lapangan untuk retraining? Atau inspeksi hanya untuk acknowledgment/notes?

3. **Multi-Estate / Multi-Afdeling**: Satu Company bisa punya multiple estates (e.g., PT Sukses punya 3 kebun di lokasi berbeda)? Jika ya, apakah setiap estate butuh Manager terpisah atau satu Manager manage semua?

4. **Theme Customization - Scope**: Apakah "additional branded themes" (selain light/dark) perlu predefined oleh CanopySense, atau Manager bisa full custom CSS?

5. **Company Registration Flow**: Apakah ada approval workflow (CanopySense team approve/reject registrations) atau auto-accept setelah validasi area?

---

**SIAP untuk diskusi & refinement.**

---

## 17. ANALISIS TEKNIS & REKOMENDASI ARSITEKTUR (Session 2)

### **A. ANALISIS DAMPAK: 4 Intent Inti**

#### **Intent #1: Balance Satellite Processing vs GIS Modeling**

**Mengapa Penting:**

- Google Earth Engine (GEE) scalable tapi latency 30-300 detik per request
- PostGIS spatial queries harus fast (<1 detik) untuk dashboard responsiveness
- Tidak bisa menunggu GEE setiap kali user klik peta

**Implikasi Arsitektur:**

- Backend harus **async**: satellite jobs di-queue & di-process background (non-blocking)
- Frontend harus show "loading state" jelas saat waiting for satellite data
- **Caching critical**: hasil GEE cache minimal 3-5 hari (satellite revisit cycle)
- Webhook/polling untuk notify frontend when satellite job complete

**Rekomendasi Tech Stack:**

- Backend: **FastAPI** (built-in async/await) + **Celery** (task queue) atau **Redis Queue** (simpler)
- Cache: **Redis** untuk hasil intermediate + job status tracking
- Message Queue: **RabbitMQ** (robust) atau **Redis Streams** (cost-effective)

---

#### **Intent #2: Account Model Revamp (One-to-Many Company→Manager→Users)**

**Mengapa Penting:**

- Current: User bisa multi-estate access (many-to-many) → Menyalahi "satu manager per company"
- New: Company boundary = hard limit. Manager = gateway semua akses
- **Security**: Data Company A completely isolated dari Company B

**Implikasi Arsitektur:**

- **Multi-tenancy architecture** diterapkan (row-level security di PostgreSQL)
- **Auth flow berubah**:
  - Old: user login → show all accessible blocks
  - New: user login → company_id extracted dari JWT → show ONLY company's blocks
- **Authorization check di setiap endpoint**: Must verify (user.company_id == request.company_id)
- **Invitation workflow baru**: Manager generate invite token → newbie click link → account created

**Rekomendasi Tech Stack:**

- Auth: **JWT dengan company_id claim** (atau OAuth 2.0 + custom claims)
- Database: **Row-Level Security (RLS) di PostgreSQL** untuk enforce company isolation
- Backend: **Middleware untuk company context injection** di setiap request

---

#### **Intent #3: Hapus Upload Feature → Pre-Computed Data Pipeline**

**Mengapa Penting:**

- Paradigm shift dari "data pipeline embedded in app" → "data pipeline is admin tool, app is read-only"
- Ini fundamental untuk operational model & scaling

**Implikasi Arsitektur:**

- **Separation of concerns**:
  1. Admin Tool: Setup company, manage registrations, trigger data ingestion (separate codebase)
  2. Main App: Dashboard, alerts, customization (customer-facing, read-only)
- **No real-time computation** dalam main app (faster, simpler, stable)
- **Company onboarding becomes async** (days/weeks sebelum live)
- **Data freshness predictable** (e.g., satellite data every 5 days Sentinel-2)

**Rekomendasi Architecture:**

- Split into **2 applications**:
  - **Admin Dashboard** (FastAPI/Flask, internal) - Company registration, data ingestion, monitoring
  - **User Dashboard** (FastAPI + React, customer-facing) - Read-only analytics, customization, invitations

**Workflow Backend:**

```
Company Registration (Admin) 
  → Area validation & insert to DB
  → Trigger patcher-cloud batch (async Celery job)
  → Monitor progress in admin dashboard
  → Mark "ready" when all computations complete
  → Auto-send Manager credentials email
  → Manager logs in ke pre-populated data
```

---

#### **Intent #4: Company Branding & Customization**

**Mengapa Penting:**

- Memudahkan multi-tenant model: setiap customer feels "owns" aplikasi
- Marketing: Custom branding membuat customer loyal
- Simple but powerful

**Implikasi Arsitektur:**

- Frontend harus **dynamic theme switching** (CSS-in-JS atau Tailwind variables)
- Database store **company_settings** (simple JSON)
- Backend: Simple CRUD endpoint untuk company_settings (one endpoint per field)

**Rekomendasi Tech Stack:**

- Frontend: **Tailwind CSS** dengan CSS variables untuk dynamic theming
- Backend: Simple CRUD endpoint per field

---

### **B. DATABASE SCHEMA RESTRUCTURING - DETAIL**

**Tabel Baru (4):**

```sql
CREATE TABLE companies (
  id BIGSERIAL PRIMARY KEY,
  company_id UUID UNIQUE NOT NULL,
  company_name VARCHAR(255) NOT NULL,
  created_at TIMESTAMP DEFAULT NOW(),
  metadata JSONB DEFAULT '{}'
);

CREATE TABLE company_settings (
  id BIGSERIAL PRIMARY KEY,
  company_id BIGINT REFERENCES companies(id),
  app_title VARCHAR(255) DEFAULT 'CanopySense',
  logo_url VARCHAR(500),
  theme_id INTEGER DEFAULT 1,
  custom_css TEXT,
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE themes (
  id BIGSERIAL PRIMARY KEY,
  theme_name VARCHAR(100),
  light_colors JSONB,
  dark_colors JSONB,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE company_invitations (
  id BIGSERIAL PRIMARY KEY,
  company_id BIGINT REFERENCES companies(id),
  token VARCHAR(255) UNIQUE NOT NULL,
  email VARCHAR(255) NOT NULL,
  role VARCHAR(50) DEFAULT 'viewer',
  created_at TIMESTAMP DEFAULT NOW(),
  expires_at TIMESTAMP DEFAULT NOW() + INTERVAL '7 days',
  accepted_at TIMESTAMP,
  accepted_by_user_id BIGINT
);
```

**Tabel Dimodifikasi:**

```sql
-- users table refactor
ALTER TABLE users ADD COLUMN company_id BIGINT REFERENCES companies(id);
ALTER TABLE users ADD COLUMN created_by BIGINT REFERENCES users(id);
-- Hapus direct FK ke blocks/afdelings/estates

-- user_roles simplify
CREATE TABLE user_company_roles (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT REFERENCES users(id),
  company_id BIGINT REFERENCES companies(id),
  role VARCHAR(50) NOT NULL,
  created_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(user_id, company_id)
);
```

**Tabel Tetap (dengan FK adjustment):**

```sql
ALTER TABLE estates ADD COLUMN company_id BIGINT REFERENCES companies(id);
ALTER TABLE afdelings ADD COLUMN company_id BIGINT;
ALTER TABLE blocks ADD COLUMN company_id BIGINT;

CREATE INDEX idx_estates_company_id ON estates(company_id);
CREATE INDEX idx_blocks_company_id ON blocks(company_id);
```

---

### **C. BACKEND ARCHITECTURE - STRUCTURE**

**Layer 1: Authentication & Multi-Tenancy**

```python
# middleware/tenant.py
async def inject_company_context(request: Request, call_next):
    """Extract company_id dari JWT token"""
    token = request.headers.get("authorization")
    user = decode_jwt(token)
    request.state.company_id = user.company_id
    response = await call_next(request)
    return response
```

**Layer 2: Read-Only Data APIs**

```python
@router.get("/blocks/gcc-summary")
async def get_gcc_summary(company_id: int = Depends(get_company_id)):
    """Return pre-computed GCC data"""
    blocks = await db.query("""
        SELECT block_id, gcc_percentage, confidence, detection_date
        FROM predictions
        WHERE company_id = $1
        ORDER BY detection_date DESC
    """, [company_id])
    return blocks
```

**Layer 3: Company Settings & Invitations (Manager-only)**

```python
@router.post("/settings/update")
async def update_company_settings(user = Depends(get_current_user)):
    """Update company branding (Manager only)"""
    if user.role != "manager":
        raise HTTPException(status_code=403)
    ...

@router.post("/invite")
async def invite_user(email: str, role: str, user = Depends(get_current_user)):
    """Manager creates invite token"""
    if user.role != "manager":
        raise HTTPException(status_code=403)
    ...
```

**Layer 4: Admin-Only APIs**

```python
@router.post("/admin/register-company")
async def register_company(admin_token: str = Header(...)):
    """Admin: Register company + trigger data pipeline"""
    if not verify_admin_token(admin_token):
        raise HTTPException(status_code=401)

    company = await db.create_company(...)
    celery_app.send_task("tasks.ingest_company_data", args=[company.id, ...])
    return {"status": "ingestion_started"}
```

---

### **D. FRONTEND ARCHITECTURE - STRUCTURE**

**Component Hierarchy:**

```
src/
├── components/
│   ├── Layout/
│   │   ├── Header.tsx (dynamic company title + logo)
│   │   ├── ThemeProvider.tsx
│   ├── Dashboard/
│   │   ├── GCCSummary.tsx (read-only)
│   │   ├── BlockStatusMap.tsx
│   └── Manager/
│       ├── CompanySettings.tsx (Manager only)
│       ├── InviteUsers.tsx
│       └── ThemeCustomizer.tsx
├── hooks/
│   ├── useCompanyContext.ts
│   └── useCompanySettings.ts
├── pages/
│   ├── Auth/
│   │   ├── Signup.tsx
│   │   └── AcceptInvite.tsx
│   └── Dashboard.tsx
```

**Dynamic Theme (Tailwind + CSS Variables):**

```typescript
// themes.ts
export const THEMES = {
  light: {
    primary: "#2563eb",
    secondary: "#64748b",
    background: "#ffffff",
    text: "#1e293b"
  },
  dark: {
    primary: "#3b82f6",
    secondary: "#94a3b8",
    background: "#0f172a",
    text: "#f1f5f9"
  }
};

// ThemeProvider.tsx
const ThemeProvider = ({ children, companySettings }) => {
  const theme = THEMES[companySettings.theme] || THEMES.light;
  return (
    <div style={{
      "--primary-color": theme.primary,
      "--background-color": theme.background
    }}>
      {children}
    </div>
  );
};
```

---

### **E. TECH STACK RECOMMENDATION FINAL**

**Backend:**

- Framework: **FastAPI** (async-first, perfect untuk satellite orchestration)
- Database: **PostgreSQL 16 + PostGIS** (keep current, add RLS)
- Cache: **Redis** (satellite job caching + session management)
- Task Queue: **Celery + RabbitMQ** (robust) OR **Redis Queue** (simpler, cost-effective)
- Auth: **JWT dengan company_id claim**
- Admin Tool: **FastAPI** (separate routes, admin-only middleware)

**Frontend:**

- Framework: **React 18 + TypeScript** (continue current)
- Styling: **Tailwind CSS** (built-in dark mode, CSS variables)
- State: **Redux Toolkit** (current)
- Maps: **Leaflet/MapLibre** (current)
- Charts: **Recharts** (current)

**Infrastructure:**

- Deployment: **Docker Compose** (dev) → **Kubernetes** (production)
- Satellite: **Google Cloud Function** (patcher-cloud, unchanged)
- Admin Dashboard: **Internal-only**, same server atau separate VM
- Database: **PostgreSQL + PostGIS** on-premise (current)

---

### **F. CLARIFICATION QUESTIONS (sebelum detail design)**

1. **Multi-Estate Complexity**: Satu Company bisa punya multiple estates? Jika ya, satu Manager handle semua atau Manager per estate?

2. **Ground-Truth Data After Launch**: Setelah live, Manager/Inspector bisa request/upload GCC measurement (hemispherical photo) untuk retraining? Atau hanya internal CanopySense team?

3. **Field Inspection Workflow**: Inspector perlu upload foto + findings dari lapangan, atau hanya acknowledgment ("yes confirmed" / "false alarm")?

4. **Company Registration & Approval**: Ada approval workflow atau auto-accept setelah validasi area?

5. **Timeline & Resources**: Target MVP delivery date? Team size? Backend/frontend expertise level?

---

**SIAP untuk diskusi & refinement berdasarkan jawaban 5 pertanyaan clarification di atas.**

---

## 18. JAWABAN CLARIFICATION QUESTIONS (Session 2)

### **#1: Multi-Estate Complexity ✅ RESOLVED**

**Jawaban User:**
> "Tidak, satu company harus punya satu estate dan by request oleh manager perusahaan. Sistem bisnis adalah subscription/payment model, satu company = satu estate."

**Implikasi:**
- Database relationship: **Company ↔ Estate = 1:1 (bukan 1:Many)**
- Hierarki menjadi **SANGAT SIMPLE**:
  ```
  Company (1:1)
    ├── Estate (spatial unit)
    │    ├── Afdelings (divisions)
    │    └── Blocks (operational units)
    └── Users (scoped to this company's estate)
  ```
- **Simplification impact**: Reduce schema complexity, permission checks lebih simple, query optimization easier
- Tabel relasi: `company_id` di `users` and `estates` tables; `estates` di cascade drop ke `afdelings` dan `blocks`

---

### **#2: Ground-Truth Data After Launch ✅ RESOLVED**

**Jawaban User:**
> "Kemungkinan jawabannya B. Ada fitur uploading di tahap 4 yang berkaitan erat dengan sistem verifikasi internal perusahaan terhadap checking perbandingan hasil model dengan data lapangan. Ini sebagai resources evaluasi model kedepannya."

**Interpretasi:**
- **Timeline**: Ground-truth uploading feature = **Phase 4 (Advanced Features)**
- **Purpose**: Inspector upload field measurements (photos + findings) → Manager verify → Data untuk model retraining resources
- **NOT for real-time alerts**: Data ini digunakan untuk post-incident validation & model improvement, bukan untuk operational alerts

**Workflow Ground-Truth Verification (Phase 4):**
```
Inspector di lapangan (setelah anomali terdeteksi atau scheduled inspection)
  ↓
Inspector take photos + notes (actual GCC%, kondisi tanah, findings)
  ↓
Inspector upload ke sistem (dengan block_id + verification data)
  ↓
Manager reviews + approves upload
  ↓
Data stored untuk Phase 4: Model retraining & evaluation
  ↓
Data Science team: Compare model predictions vs actual field measurements
  ↓
Hasil: Improve ML model accuracy & hyperparameter tuning
```

**Implikasi Database (Phase 4):**
```sql
CREATE TABLE field_verifications (
  id BIGSERIAL PRIMARY KEY,
  inspector_id BIGINT REFERENCES users(id),
  block_id BIGINT REFERENCES blocks(id),
  company_id BIGINT REFERENCES companies(id),
  photos JSONB,  -- array of photo URLs
  findings TEXT,
  gcc_actual NUMERIC(5,2),  -- actual GCC% from field measurement
  created_at TIMESTAMP DEFAULT NOW(),
  approved_by BIGINT REFERENCES users(id),  -- manager approval
  approval_status VARCHAR(50) DEFAULT 'PENDING',
  approved_at TIMESTAMP,
  rejection_reason TEXT
);

CREATE INDEX idx_field_verifications_block_company 
  ON field_verifications(block_id, company_id);
CREATE INDEX idx_field_verifications_status 
  ON field_verifications(approval_status);
```

---

### **#3: Role Hierarchy & Field Inspection ✅ RESOLVED**

**Jawaban User:**
> "Hierarki nya lebih masuk ke option A. Intinya akun company diserahterima ke akun manager, akun lain (viewer) hanya bisa link ke akun company id yang sama dengan manager (dengan hak akses terbatas view saja) hanya melalui undangan atau request to manager only. Viewer yang sudah teregistrasi ke dalam akun company (melalui undangan manager) bisa ditunjuk lebih lanjut dengan role spesifik inspector, dengan role ini, viewer tersebut dapat satu hak akses uploading fitur verifikasi lapangan atas approval atau permission manager. Terkait apakah ada second manager atau dll itu by request atau by evaluation nantinya, tapi pengembangan awal kita ketatkan sistem ini bahwa hanya manager yg bisa mendaftarkan dan memberi role viewer menjadi inspector."

**Interpretasi - Struktur Role Hierarchy (Option A: Flat):**

```
Company (created by CanopySense team + assigned Manager account)
  │
  ├── Manager (1 per company, role utama)
  │    ├── Permission: Read all company data (dashboard, analytics)
  │    ├── Permission: Invite viewer users (via email/token)
  │    ├── Permission: Promote viewer → inspector
  │    ├── Permission: Approve inspector uploads (field_verifications)
  │    ├── Permission: Manage company settings (branding, theme, logo)
  │    └── CONSTRAINT: Only 1 Manager per company in MVP
  │         (Multiple managers = future phase by request/evaluation)
  │
  ├── Viewer (many, invited by Manager)
  │    ├── Permission: Read-only access to company data
  │    ├── Permission: Can be promoted to Inspector by Manager
  │    └── CONSTRAINT: Must be invited by Manager (no self-registration within company)
  │
  └── Inspector (many, promoted from Viewer by Manager)
       ├── Permission: All Viewer permissions (read-only access)
       ├── Permission: Upload field verification data (photos + findings)
       └── CONSTRAINT: Uploads require Manager APPROVAL before visible/processable
```

**Workflow - User Invitation & Role Promotion:**

```
Step 1: Manager Invites Viewer
  Manager: "Invite person@email.com to this company"
  ↓
  System: Generate invite token + send email with accept link
  ↓
  User clicks link: "Accept invitation to Company X"
  ↓
  User account created with:
    - user.company_id = Company X
    - user_company_roles: role = 'viewer'
    - Status: ACTIVE, can view company data

Step 2: Manager Promotes Viewer → Inspector
  Manager: "Promote viewer@email.com to Inspector role"
  ↓
  System: Update user_company_roles: role = 'inspector'
  ↓
  Inspector can now: Upload field verification data
  ↓
  Backend: Check permission before allowing upload (role == 'inspector')

Step 3: Inspector Uploads Field Verification
  Inspector (in field): Upload photos + findings for Block X
  ↓
  System: Create field_verifications record (status = 'PENDING')
  ↓
  Manager notification: "New inspection upload from Inspector, needs approval"
  ↓
  Manager reviews + clicks "Approve"
  ↓
  field_verifications.approval_status = 'APPROVED'
  ↓
  Data available for Phase 4: Model evaluation & retraining
```

**Implikasi Database (Role Management):**

```sql
-- Simplified user_company_roles table
CREATE TABLE user_company_roles (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT REFERENCES users(id),
  company_id BIGINT REFERENCES companies(id),
  role VARCHAR(50) NOT NULL,  -- 'manager', 'inspector', 'viewer'
  created_at TIMESTAMP DEFAULT NOW(),
  promoted_by BIGINT REFERENCES users(id),  -- which manager promoted (if role=inspector)
  UNIQUE(user_id, company_id)  -- one role per user per company
);

-- Company invitation management
-- (already defined in Section 16)
CREATE TABLE company_invitations (
  id BIGSERIAL PRIMARY KEY,
  company_id BIGINT REFERENCES companies(id),
  token VARCHAR(255) UNIQUE NOT NULL,
  email VARCHAR(255) NOT NULL,
  role VARCHAR(50) DEFAULT 'viewer',
  created_at TIMESTAMP DEFAULT NOW(),
  expires_at TIMESTAMP DEFAULT NOW() + INTERVAL '7 days',
  accepted_at TIMESTAMP,
  accepted_by_user_id BIGINT REFERENCES users(id)
);
```

**Implikasi Backend - Authorization Middleware:**

```python
# roles.py
PERMISSIONS = {
    'manager': [
        'view_data',
        'manage_users',
        'promote_user_to_inspector',
        'approve_inspector_uploads',
        'manage_company_settings'
    ],
    'inspector': [
        'view_data',
        'upload_field_verification'
    ],
    'viewer': [
        'view_data'
    ]
}

# routes/field_verification.py
@router.post("/upload-verification")
async def upload_field_verification(
    block_id: int,
    photos: List[bytes],
    findings: str,
    user = Depends(get_current_user)
):
    """Inspector uploads field verification data"""
    # Check permission
    if user.role != 'inspector':
        raise HTTPException(status_code=403, detail="Only Inspector can upload")
    
    # Check company_id matches
    block = await db.get_block(block_id)
    if block.company_id != user.company_id:
        raise HTTPException(status_code=403, detail="Block not in your company")
    
    # Create pending verification
    verification = await db.create_field_verification(
        inspector_id=user.id,
        block_id=block_id,
        photos=photos,
        findings=findings,
        approval_status='PENDING'
    )
    
    # Notify manager
    await notify_manager(user.company_id, f"New inspection upload from {user.name}")
    
    return {"status": "uploaded", "verification_id": verification.id}

@router.post("/approve-verification/{verification_id}")
async def approve_field_verification(
    verification_id: int,
    user = Depends(get_current_user)
):
    """Manager approves Inspector uploads"""
    if user.role != 'manager':
        raise HTTPException(status_code=403, detail="Only Manager can approve")
    
    verification = await db.get_field_verification(verification_id)
    if verification.company_id != user.company_id:
        raise HTTPException(status_code=403, detail="Not your company's data")
    
    await db.update_field_verification(
        verification_id,
        approval_status='APPROVED',
        approved_by=user.id,
        approved_at=now()
    )
    
    return {"status": "approved"}
```

**MVP Constraints (Tahap Awal):**
- ✅ One Manager per company only (future: support multiple managers by request/evaluation)
- ✅ Manager adalah gatekeeper semua permissions (invite, promote, approve)
- ✅ Viewer hanya bisa accessed via invitation (no self-signup)
- ✅ Inspector hanya bisa created dari promotion (no direct signup sebagai inspector)

---

### **#4: Company Registration Workflow ❓ PENDING**

**Pertanyaan Original:** Apakah ada approval workflow atau auto-accept setelah validasi area?

**Opsi:**
- **SCENARIO A: Manual Approval** - CanopySense team manually review & approve registrations
- **SCENARIO B: Auto-Accept** - System auto-validate & auto-trigger data processing

**Awaiting user answer**: Which scenario prefer? Atau ada workflow lain?

---

### **#5: Timeline & Team ❓ PENDING**

**Target Delivery: 23 Juni 2026** (33 hari dari hari ini, 21 Mei)

**Missing Info yang diperlukan:**

1. **Team Size**: 
   - Solo development?
   - Team 2-3 orang?
   - Larger team?

2. **Expertise Level**:
   - Backend dev: junior/mid/senior?
   - Frontend dev: junior/mid/senior?
   - DevOps/infra: ada atau tidak?

3. **MVP Scope for 23 Juni**:
   - **OPTION A**: Full MVP (Phase 1-3: dashboard + alerts + anomaly) = unlikely 33 days
   - **OPTION B**: MVP Core (Phase 1-2: dashboard only, skip alerts) = possible
   - **OPTION C**: Prototype (Phase 1 integration + basic dashboard) = likely 33 days

4. **Patcher Status**:
   - Patcher-local & patcher-cloud sudah production-ready?
   - Or need refactoring/hardening first?

**Awaiting user answers**: Silakan berikan info di atas untuk realistic roadmap planning.

---

## 19. TEAM & RESOURCE CONSTRAINTS (Session 2 - Critical Reality Check)

### **#5: Timeline & Team ✅ ANSWERED**

**User Answers:**
1. **Team Size**: Solo (hanya user sendiri)
2. **Expertise Level**: Apprentice/Beginner (self-taught, "vibe coding" + manual audit)
3. **MVP Scope for 23 Juni**: **Phase 1 Core Engine Only** (Phase 2, 3, 4 belum dimulai)
4. **Current Status**: Phase 1 ~90% done, tapi testing data satellite ingestion belum fully validated
5. **Patcher Status**: Seharusnya robust per design, tapi perlu recheck + mungkin modifikasi sedikit

### **Critical Reality Assessment**

**Mismatch Alert:** Ada **gap signifikan** antara 4 intents yang user deklarasikan vs resource constraint:

| Aspek | Intent User | Reality |
|-------|-----------|---------|
| **Scope** | Phase 1-4 fully implemented | Phase 1 only (incomplete testing) |
| **Timeline** | 33 hari (23 Juni) | Unrealistic untuk 4 phases + solo apprentice |
| **Team** | Implied: team 2-3 orang | Solo developer |
| **Expertise** | Implied: mid-level | Apprentice/beginner level |
| **Current Status** | Ready for Phase 2+ | Phase 1 testing incomplete |

### **Honest Assessment: What's Realistic dalam 33 Hari (Solo Apprentice)**

**BEST CASE SCENARIO (Phase 1 completion + basic Phase 2):**
```
Weeks 1-2 (May 21 - Jun 3):
  - Finish Phase 1 testing validation
  - Verify satellite data ingestion (Sentinel-2/Landsat)
  - Validate database schema + queries
  - Document operational procedures
  - Recheck & minor refactor patcher-local/cloud

Weeks 3-4 (Jun 4 - Jun 17):
  - Setup Phase 2 test infrastructure (docker-compose)
  - Basic dashboard skeleton (no complex features)
  - Login system (simple, no multi-tenant complexity)
  - Basic data visualization (read-only)

Week 5 (Jun 18 - Jun 23):
  - Integration testing
  - Hardening + security check
  - Documentation
  - Deployment/setup guide

OUTCOME: Phase 1 robust + Phase 2 skeleton (basic UI only)
SKIP: Alerts, anomaly detection, multi-tenant, company branding, inspector workflow
```

**REALISTIC SCOPE FOR 23 JUNI:**
1. ✅ Phase 1 Core Engine: COMPLETE & TESTED
2. ✅ Phase 2 Basic Dashboard: SKELETON ONLY (read-only, no interactivity)
3. ✅ Basic Authentication: Simple login (no complex RBAC yet)
4. ❌ Phase 3: Anomaly Detection - NOT INCLUDED
5. ❌ Phase 4: Ground-truth Verification - NOT INCLUDED
6. ❌ 4 Intents (multi-tenant, branding, etc): NOT INCLUDED

### **#4: Company Registration Workflow ❓ STILL PENDING**

**But this becomes less critical if:**
- 23 Juni scope = Phase 1 completion only
- Company registration = future phase (not 23 Juni deliverable)
- Company branding/settings = Phase 4 (not 23 Juni deliverable)

**So my question for user**: 
- Apakah 4 intents itu adalah **long-term vision** (not for 23 Juni)?
- Atau ada aspek dari 4 intents yang **MUST** be in 23 Juni deliverable?

---

**STATUS SECTION 19:**
- ✅ #5: ANSWERED - Solo apprentice, Phase 1 only, 33 days
- ✅ Resource constraint documented
- ✅ Reality assessment provided
- ❓ User clarification needed: Which of the 4 intents are "23 Juni must-have" vs "long-term vision"?

---

### **CRITICAL DECISION POINT**

**User perlu clarify prioritas:**

**Option A: Strict 23 Juni Deadline (Phase 1 completion only)**
- 4 intents = long-term roadmap
- 23 Juni deliverable = Phase 1 robust + Phase 2 skeleton
- Realistic & achievable untuk solo apprentice

**Option B: Partial Intents for 23 Juni (extended scope)**
- Some of 4 intents included (e.g., basic multi-tenant + simple auth)
- But realistic? Unlikely untuk solo apprentice tanpa extending timeline
- Risk: incomplete work, unstable code, no proper testing

**Option C: Extend Timeline (realistic for full intent)**
- Keep all 4 intents
- Realistic timeline: 3-6 bulan (bukan 33 hari)
- Solo apprentice perlu support/mentoring

**RECOMMENDATION**: Option A (23 Juni = Phase 1 completion, 4 intents = roadmap)

---

## 20. FINAL SCOPE DECISION - DIR-INTENT BOUNDARY (Session 2)

### **User Decision: ✅ LOCKED**

> **"Catatan untuk dokument intent batasi hanya sampai fase 1, saya tidak menuntut fase 2, 3, dan 4 selesai di tanggal 23 juni"**

**Translation**: Document intent scope = **PHASE 1 ONLY for 23 Juni**. NO demands for Phase 2, 3, 4 completion by 23 June.

### **DIR-INTENT Scope Boundary (LOCKED)**

**In Scope (23 Juni):**
- ✅ Phase 1: Core Engine Completion
  - Patcher-local robustness check + minor refactoring
  - Patcher-cloud validation
  - Satellite data ingestion pipeline (Sentinel-2, Landsat)
  - 5 vegetation indices calculation (NDVI, EVI, NDRE, SAVI, GNDVI)
  - PostgreSQL+PostGIS database validation
  - ML model infrastructure (Random Forest baseline ready)
  - Cloud Logging & error handling

**Out of Scope (Phase 2-4, for future roadmap):**
- ❌ Phase 2: ML Training Pipeline
- ❌ Phase 3: Anomaly Detection & Alerts
- ❌ Phase 4: Ground-truth Verification + Advanced Features
- ❌ 4 Intents (multi-tenant, company branding, role hierarchy, etc) = Roadmap for Phase 2+

### **4 Intents: Repositioned as Long-Term Roadmap (Post-Phase 1)**

The 4 intents user declared are **STRATEGIC VISION** for future phases:

1. **Intent #1**: Balance satellite processing vs GIS modeling → Phase 2-3 implementation
2. **Intent #2**: One-to-many account hierarchy (company→manager→users) → Phase 2 implementation  
3. **Intent #3**: Pre-computed backend processing (no upload in app) → Phase 2+ operational model
4. **Intent #4**: Company branding & customization → Phase 4 implementation

These intents will inform **Phase 2+ architecture design**, but NOT expected for 23 Juni delivery.

---

**STATUS: READY TO DRAFT DIR-INTENT DOCUMENT**

Next action: Draft formal DIR-INTENT with Phase 1 scope only → Request user approval to lock

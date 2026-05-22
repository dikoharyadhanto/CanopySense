# Rencana Teknis: Canopy Sense - Monitoring Kerapatan Kanopi Perkebunan Karet

**Versi Dokumen:** 3.0 (Pipeline ML dengan Green Canopy Cover)  
**Tanggal:** 4 Maret 2026  
**Audiens Target:** Tim Implementasi Teknis (Developer, Data Scientist, Agronom)

## Ringkasan Eksekutif

Canopy Sense adalah aplikasi monitoring perkebunan karet berbasis cloud yang dirancang untuk mengubah citra satelit optik menjadi indikator **Green Canopy Cover (GCC)** yang konsisten menggunakan algoritma Machine Learning. Sistem ini memanfaatkan data satelit multi-spektral (Sentinel-2, Landsat-8/9) untuk menghitung indeks vegetasi, kemudian mengintegrasikan data ground-truth lapangan untuk melatih model prediksi Green Canopy Cover dalam satuan persentase (%).

**Alur Utama Sistem:**

Citra Satelit Optik (Sentinel-2/Landsat)  
↓  
Perhitungan Indeks Vegetasi (NDVI, EVI, NDRE, SAVI, GNDVI)  
↓  
Integrasi dengan Data Ground-Truth Lapangan  
↓  
Training Model Machine Learning (Random Forest/XGBoost)  
↓  
Output: Green Canopy Cover (%)

**Keunggulan Pendekatan:** - **Berbasis Data Lapangan:** Model dilatih menggunakan pengukuran aktual dari kebun - **Konsistensi Temporal:** Prediksi GCC yang dapat dibandingkan antar waktu - **Deteksi Anomali:** Identifikasi penurunan kanopi abnormal vs. gugur daun musiman - **Skalabilitas:** Monitoring dari level blok hingga estate secara otomatis

## Daftar Isi

- [Konsep Produk](#X99f654dc7d7089d53542cf44acf376993f412b3)
- [Modul Aplikasi](#Xff298a4a3547c21df5e043722ab292bfad0fa40)
- [Fitur Data & Indikator](#Xe3c35857bab01c26df1affa4725447b33ecfa94)
- [Desain Machine Learning & Pipeline Data](#X47fd4318305faad73bbc1c6d7ea011400032d07)
- [Arsitektur Sistem](#X7327d3dd505d0123fc34a6a7334ec15049b605b)
- [Rekomendasi MVP](#Xdd3713ec60f23b3b0ba25a94ad692a4f7ff6a70)
- [Referensi](#referensi)

## 1\. Konsep Produk

### 1.1 Tujuan Utama

**Canopy Sense** bertujuan untuk:

- **Mengubah citra satelit menjadi indikator Green Canopy Cover (GCC) yang konsisten**
  - Menggunakan algoritma Machine Learning yang dilatih dengan data lapangan
  - Output berupa persentase penutupan kanopi hijau (0-100%)
  - Konsisten dari waktu ke waktu untuk analisis tren
- **Menyediakan peringatan dini saat kanopi menurun tidak normal**
  - Deteksi stres tanaman, penyakit (Pestalotiopsis), defoliasi abnormal
  - Membedakan penurunan musiman normal vs. anomali
  - Alert prioritas untuk inspeksi lapangan
- **Memberi ringkasan spasial dan tren jangka panjang**
  - Agregasi dari blok → afdeling → estate
  - Analisis tren 5-10 tahun untuk evaluasi manajemen
  - Perbandingan year-over-year (YoY)

### 1.2 Target Pengguna

- **Manajer Estate / Agronomi / QC Kebun:** Monitoring operasional harian/mingguan
- **Tim Riset Perusahaan / Universitas:** Analisis fenologi dan produktivitas
- **Tim Penyakit Tanaman / Sustainability:** Health monitoring dan deforestasi

## 2\. Modul Aplikasi

### A. Dashboard Utama (Executive View)

**Komponen Utama:**

- **Green Canopy Cover (GCC) Hari Ini / Minggu Ini**
  - Skor kondisi kanopi estate dalam persentase (%)
  - Visualisasi gauge chart dengan kategori warna:
    - Hijau: GCC > 80% (Sehat)
    - Kuning: GCC 60-80% (Waspada)
    - Merah: GCC < 60% (Kritis)
- **Peta Status Blok**
  - Klasifikasi blok berdasarkan anomali GCC:
    - **Normal:** Dalam range historis
    - **Waspada:** Penurunan 10-20% dari baseline
    - **Kritis:** Penurunan > 20% atau anomali ekstrem
  - Heatmap dengan color coding
- **Ringkasan Perubahan**
  - ΔMingguan: Perubahan GCC 7 hari terakhir
  - ΔBulanan: Perubahan GCC 30 hari terakhir
  - ΔYear-over-Year: Perbandingan dengan periode sama tahun lalu
- **Top 10 Blok Perlu Inspeksi**
  - Ranking berdasarkan:
    - Penurunan GCC cepat (> 15% dalam 2 minggu)
    - Anomali residual tinggi
    - Confidence model rendah

### B. Explore Map (Peta Interaktif)

**Layer Utama:**

- **Prediksi Green Canopy Cover (%)**
  - Visualisasi grid/pixel atau agregasi blok
  - Color ramp: Merah (0%) → Kuning (50%) → Hijau tua (100%)
  - Tooltip menampilkan nilai GCC, confidence interval, tanggal akuisisi
- **Layer Indeks Vegetasi**
  - NDVI, EVI, NDRE, SAVI, GNDVI
  - Toggle on/off untuk perbandingan visual
- **Quality Layer**
  - Mask awan dan area low-quality
  - Transparansi untuk menunjukkan confidence level

**Tools Interaktif:**

- **Pilih Blok → Profil Time-Series:** Grafik GCC historis
- **Compare Tool:** Bandingkan 2 blok atau 2 periode waktu
- **Drill-Down:** Estate → Afdeling → Blok → Pixel sample

### C. Time-Series Analyzer (Mingguan/Bulanan)

**Grafik Utama:**

- **Time-Series GCC (%)**
  - Line chart mingguan/bulanan
  - Confidence interval (±1 SD)
  - Baseline historis (mean ± 2 SD)
- **Indeks Vegetasi**
  - NDVI, EVI, NDRE (multi-line chart)
  - Untuk validasi visual terhadap prediksi GCC
- **Dekomposisi Time-Series**
  - **Trend:** Tren jangka panjang (naik/turun)
  - **Seasonal:** Pola musiman (fenologi normal)
  - **Residual:** Anomali (deviasi dari pola normal)

**Event Tagging:**

- User dapat menandai event lapangan:
  - Wabah penyakit (Pestalotiopsis outbreak)
  - Musim gugur daun alami (leaf fall season)
  - Pemangkasan (pruning)
  - Replanting
  - Kekeringan (drought)
- Event muncul sebagai garis vertikal/label di grafik

### D. Long-Term Trend (5-10 Tahun)

**Analisis Jangka Panjang:**

- **Tren per Blok/Estate**
  - Slope tren (naik/turun per tahun)
  - Stabilitas (variansi musiman, amplitudo fenologi)
  - Deteksi "regime shift" (perubahan permanen setelah tahun tertentu)
- **Year-over-Year Comparison**
  - Bandingkan GCC untuk bulan yang sama antar tahun
  - Mengurangi bias musiman
  - Visualisasi heatmap multi-tahun
- **Ringkasan Perubahan Area**
  - Berapa hektar masuk kategori "declining trend"
  - Berapa blok menunjukkan "improving trend"
  - Distribusi GCC per kategori umur tanaman

### E. Model & Prediction Studio (Tim Teknis)

**Manajemen Model:**

- **Pilih Model Aktif**
  - Baseline model vs. versi terbaru (v2, v3)
  - Metrik performa:
    - R² (coefficient of determination)
    - RMSE (Root Mean Square Error)
    - MAE (Mean Absolute Error)
- **Explainability**
  - **Feature Importance Global:** Kontribusi masing-masing indeks vegetasi
  - **Penjelasan Lokal per Blok:** Apa yang "mendorong" prediksi turun (SHAP values)
- **Data Quality Report**
  - Coverage awan per periode
  - Gap time-series
  - Sensor availability (Sentinel-2 vs. Landsat)

### F. Alerts & Tasking (Operasional)

**Alert Rules:**

- **Penurunan GCC Cepat**
  - Trigger: Penurunan > 15% dalam 2-3 minggu
  - Prioritas: Tinggi
- **Anomali Residual Tinggi**
  - Trigger: Residual > 2 SD dari baseline
  - Prioritas: Sedang (perlu verifikasi)
- **Confidence Rendah**
  - Trigger: Model confidence < 70%
  - Prioritas: Rendah (minta verifikasi lapangan)

**Workflow Inspeksi Lapangan:**

- Buat daftar tugas: Blok, prioritas, lokasi GPS, catatan
- Upload foto/observasi lapangan
- Data menjadi validasi untuk re-training model

### G. Reports & Export

**Laporan Otomatis:**

- **Monthly Canopy Health Report**
  - Ringkasan GCC estate-level
  - Top 10 blok bermasalah
  - Tren bulan ini vs. bulan lalu
- **Anomaly & Inspection List**
  - Daftar blok dengan anomali terdeteksi
  - Rekomendasi tindakan
- **10-Year Trend Summary**
  - Analisis tren jangka panjang per afdeling
  - Perbandingan performa antar estate

**Format Export:**

- **PDF:** Laporan eksekutif dengan grafik dan peta
- **CSV:** Data tabular untuk analisis lanjutan
- **GeoPackage/GeoJSON:** Data spasial untuk GIS
- **Cloud Optimized GeoTIFF (COG):** Raster GCC untuk integrasi sistem lain

## 3\. Fitur Data & Indikator

### 3.1 Sumber Data Satelit Optik

**A. Sentinel-2 MSI (Sumber Utama)**

| Karakteristik         | Spesifikasi                                                 |
| --------------------- | ----------------------------------------------------------- |
| **Resolusi Spasial**  | 10m (B2, B3, B4, B8), 20m (B5, B6, B7, B8A, B11, B12)       |
| **Resolusi Temporal** | 5 hari (kombinasi Sentinel-2A dan 2B)                       |
| **Resolusi Spektral** | 13 band (VIS, NIR, SWIR, Red-Edge)                          |
| **Ketersediaan**      | Gratis (Copernicus Open Access Hub, Google Earth Engine)    |
| **Keunggulan**        | Red-edge bands untuk deteksi stres tanaman, resolusi tinggi |

**B. Landsat-8/9 (Backup & Historis)**

| Karakteristik         | Spesifikasi                                                        |
| --------------------- | ------------------------------------------------------------------ |
| **Resolusi Spasial**  | 30m (band multispektral)                                           |
| **Resolusi Temporal** | 16 hari (8 hari jika kombinasi Landsat-8 dan 9)                    |
| **Resolusi Spektral** | 11 band (VIS, NIR, SWIR, Thermal)                                  |
| **Ketersediaan**      | Gratis (USGS Earth Explorer, Google Earth Engine)                  |
| **Keunggulan**        | Arsip historis sejak 1984 (Landsat 5+) untuk analisis tren panjang |

**C. Planet PlanetScope (Opsional - High Resolution)**

| Karakteristik         | Spesifikasi                                         |
| --------------------- | --------------------------------------------------- |
| **Resolusi Spasial**  | 3-5m                                                |
| **Resolusi Temporal** | Harian                                              |
| **Resolusi Spektral** | 4-band (RGB + NIR) atau 8-band (termasuk Red-Edge)  |
| **Ketersediaan**      | Komersial (lisensi berbayar)                        |
| **Keunggulan**        | Resolusi temporal tinggi untuk monitoring real-time |

### 3.2 Indeks Vegetasi (Fitur Input untuk ML)

Aplikasi ini menggunakan **5 indeks vegetasi utama** sebagai fitur input untuk model Machine Learning:

#### A. NDVI (Normalized Difference Vegetation Index)

**Formula:**

NDVI = (NIR - Red) / (NIR + Red)

**Band Sentinel-2:**

NDVI = (B8 - B4) / (B8 + B4)

**Interpretasi:** - **Range:** -1 hingga +1 - **Vegetasi Sehat:** 0.6 - 0.9 - **Vegetasi Sparse:** 0.2 - 0.5 - **Tanah/Air:** < 0.2

**Kegunaan:** - Indikator umum kehijauan (greenness) - Sensitif terhadap klorofil dan biomassa - Baseline untuk monitoring kesehatan tanaman

#### B. EVI (Enhanced Vegetation Index)

**Formula:**

EVI = G × \[(NIR - Red) / (NIR + C1×Red - C2×Blue + L)\]

**Parameter:** - G = 2.5 (gain factor) - C1 = 6, C2 = 7.5 (koefisien koreksi atmosfer) - L = 1 (koreksi background kanopi)

**Band Sentinel-2:**

EVI = 2.5 × \[(B8 - B4) / (B8 + 6×B4 - 7.5×B2 + 1)\]

**Keunggulan:** - Lebih stabil pada kanopi rapat (mengurangi saturasi) - Koreksi atmosfer lebih baik - Cocok untuk perkebunan karet dengan kanopi tinggi

#### C. NDRE (Normalized Difference Red Edge Index)

**Formula:**

NDRE = (NIR - RedEdge) / (NIR + RedEdge)

**Band Sentinel-2:**

NDRE = (B8A - B5) / (B8A + B5)

**Keunggulan:** - Sensitif terhadap kandungan klorofil dan nitrogen - Deteksi dini stres tanaman (sebelum terlihat di NDVI) - Cocok untuk monitoring penyakit (Pestalotiopsis)

#### D. SAVI (Soil Adjusted Vegetation Index)

**Formula:**

SAVI = \[(NIR - Red) / (NIR + Red + L)\] × (1 + L)

**Parameter:** - L = 0.5 (faktor koreksi tanah, 0 untuk kanopi rapat, 1 untuk sparse)

**Band Sentinel-2:**

SAVI = \[(B8 - B4) / (B8 + B4 + 0.5)\] × 1.5

**Keunggulan:** - Mengurangi pengaruh reflektansi tanah - Cocok untuk area dengan kanopi tidak penuh (replanting, young plantation)

#### E. GNDVI (Green Normalized Difference Vegetation Index)

**Formula:**

GNDVI = (NIR - Green) / (NIR + Green)

**Band Sentinel-2:**

GNDVI = (B8 - B3) / (B8 + B3)

**Keunggulan:** - Sensitif terhadap kandungan klorofil - Lebih responsif terhadap perubahan warna daun (chlorosis) - Komplementer dengan NDVI untuk deteksi stres

### 3.3 Fitur Tambahan (Opsional)

**A. Fitur Temporal:** - **Lag Features:** Nilai indeks 1-4 minggu sebelumnya - **Rolling Statistics:** Mean, std, min, max dalam window 4-12 minggu - **Rate of Change:** Perubahan indeks per minggu

**B. Fitur Konteks Kebun (Non-Citra):** - Clone type (klon karet) - Umur tanaman (tahun tanam) - Jarak tanam (spacing) - Elevasi, slope, aspect - Curah hujan kumulatif - Catatan penyakit historis - Data yield (latex) jika tersedia

## 4\. Desain Machine Learning & Pipeline Data

### 4.1 Arsitektur Pipeline

┌─────────────────────────────────────────────────────────────────┐  
│ 1. DATA INPUT │  
│ Citra Satelit Multispektral (Sentinel-2, Landsat-8/9) │  
└─────────────────────┬───────────────────────────────────────────┘  
│  
▼  
┌─────────────────────────────────────────────────────────────────┐  
│ 2. PREPROCESSING │  
│ • Cloud Masking (SCL, QA60) │  
│ • Atmospheric Correction (Surface Reflectance) │  
│ • Multi-Temporal Compositing (Median 16-hari) │  
│ • Temporal Interpolation (Whittaker, Harmonik) │  
└─────────────────────┬───────────────────────────────────────────┘  
│  
▼  
┌─────────────────────────────────────────────────────────────────┐  
│ 3. FEATURE ENGINEERING │  
│ Perhitungan 5 Indeks Vegetasi: │  
│ • NDVI = (NIR - Red) / (NIR + Red) │  
│ • EVI = 2.5 × \[(NIR - Red) / (NIR + 6×Red - 7.5×Blue + 1)\] │  
│ • NDRE = (NIR - RedEdge) / (NIR + RedEdge) │  
│ • SAVI = \[(NIR - Red) / (NIR + Red + 0.5)\] × 1.5 │  
│ • GNDVI = (NIR - Green) / (NIR + Green) │  
│ │  
│ Fitur Tambahan (Opsional): │  
│ • Lag features (1-4 minggu) │  
│ • Rolling statistics (mean, std, min, max) │  
│ • Rate of change │  
└─────────────────────┬───────────────────────────────────────────┘  
│  
▼  
┌─────────────────────────────────────────────────────────────────┐  
│ 4. GROUND TRUTH INTEGRATION │  
│ Penggabungan Data Lapangan: │  
│ • Pengukuran Green Canopy Cover (%) dari survei lapangan │  
│ • Metode: Hemispherical photography, UAV, visual assessment │  
│ • Matching spasial: Koordinat GPS blok ↔ pixel satelit │  
│ • Matching temporal: Tanggal pengukuran ± 7 hari akuisisi │  
│ │  
│ Format Data Training: │  
│ ┌──────┬──────┬──────┬──────┬───────┬───────┬─────────────┐ │  
│ │ NDVI │ EVI │ NDRE │ SAVI │ GNDVI │ ... │ GCC_actual │ │  
│ ├──────┼──────┼──────┼──────┼───────┼───────┼─────────────┤ │  
│ │ 0.75 │ 0.68 │ 0.42 │ 0.71 │ 0.73 │ ... │ 82.5% │ │  
│ │ 0.62 │ 0.55 │ 0.35 │ 0.59 │ 0.60 │ ... │ 65.3% │ │  
│ │ ... │ ... │ ... │ ... │ ... │ ... │ ... │ │  
│ └──────┴──────┴──────┴──────┴───────┴───────┴─────────────┘ │  
└─────────────────────┬───────────────────────────────────────────┘  
│  
▼  
┌─────────────────────────────────────────────────────────────────┐  
│ 5. MODEL TRAINING │  
│ Algoritma Machine Learning: │  
│ • Random Forest Regressor (Baseline) │  
│ • XGBoost Regressor (Advanced) │  
│ │  
│ Training Strategy: │  
│ • Split: 70% training, 15% validation, 15% test │  
│ • Cross-Validation: 5-fold spatial CV (per estate) │  
│ • Hyperparameter Tuning: Grid Search / Bayesian Optimization │  
│ │  
│ Target Metrik: │  
│ • R² > 0.80 (koefisien determinasi) │  
│ • RMSE < 10% (Root Mean Square Error) │  
│ • MAE < 7% (Mean Absolute Error) │  
└─────────────────────┬───────────────────────────────────────────┘  
│  
▼  
┌─────────────────────────────────────────────────────────────────┐  
│ 6. MODEL OUTPUT │  
│ Prediksi: Green Canopy Cover (GCC) dalam % │  
│ • Range: 0% - 100% │  
│ • Confidence Interval: ±1 SD │  
│ • Feature Importance: Kontribusi masing-masing indeks │  
└─────────────────────┬───────────────────────────────────────────┘  
│  
▼  
┌─────────────────────────────────────────────────────────────────┐  
│ 7. POST-PROCESSING & ANALYSIS │  
│ • Deteksi Anomali (STL Decomposition) │  
│ • Klasifikasi Status (Normal/Waspada/Kritis) │  
│ • Alert Generation │  
│ • Visualisasi & Reporting │  
└─────────────────────────────────────────────────────────────────┘

### 4.2 Detail Model Machine Learning

#### A. Random Forest Regressor (Model Baseline)

**Keunggulan:** - **Akurasi Tinggi:** Terbukti mencapai R² 0.80-0.85 untuk estimasi kanopi perkebunan tropis - **Robust terhadap Overfitting:** Ensemble method mengurangi variance - **Interpretable:** Feature importance mudah dipahami oleh agronomis - **Tidak Perlu Feature Scaling:** Bekerja baik dengan fitur berbeda skala

**Hyperparameter Kunci:**

RandomForestRegressor(  
n_estimators=200, # Jumlah trees  
max_depth=15, # Kedalaman maksimum tree  
min_samples_split=10, # Minimum sampel untuk split  
min_samples_leaf=5, # Minimum sampel per leaf  
max_features='sqrt', # Fitur per split  
random_state=42,  
n_jobs=-1 # Parallel processing  
)

**Training Workflow:** 1. Load data training (indeks vegetasi + GCC ground-truth) 2. Split data: 70% train, 15% validation, 15% test 3. Train model dengan cross-validation (5-fold spatial) 4. Hyperparameter tuning dengan Grid Search 5. Evaluasi pada test set 6. Save model (.pkl) dan feature importance

#### B. XGBoost Regressor (Model Advanced)

**Keunggulan:** - **Akurasi Lebih Tinggi:** Potensi R² 0.85-0.90 - **Gradient Boosting:** Sequential learning untuk memperbaiki error - **Regularization:** L1/L2 regularization untuk mencegah overfitting - **Handle Missing Data:** Built-in handling untuk gap time-series

**Hyperparameter Kunci:**

XGBRegressor(  
n_estimators=300,  
max_depth=8,  
learning_rate=0.05,  
subsample=0.8,  
colsample_bytree=0.8,  
reg_alpha=0.1, # L1 regularization  
reg_lambda=1.0, # L2 regularization  
random_state=42,  
n_jobs=-1  
)

**Kapan Menggunakan XGBoost:** - Fase 2 MVP (setelah baseline Random Forest stabil) - Ketika data training > 1000 sampel - Ketika akurasi baseline < target (R² < 0.80)

### 4.3 Integrasi Data Ground-Truth Lapangan

#### A. Metode Pengukuran GCC Lapangan

**1\. Hemispherical Photography (Metode Standar)** - **Alat:** Kamera fisheye lens + tripod - **Prosedur:** 1. Ambil foto ke atas kanopi dari posisi di bawah pohon 2. Gunakan software (Gap Light Analyzer, CAN-EYE) untuk analisis 3. Hitung persentase gap vs. kanopi - **Output:** GCC (%) dengan akurasi tinggi - **Kelebihan:** Standar ilmiah, akurat - **Kekurangan:** Labor-intensive, butuh training

**2\. UAV/Drone RGB Imagery** - **Alat:** Drone DJI Phantom/Mavic dengan kamera RGB - **Prosedur:** 1. Terbang di atas blok (altitude 50-100m) 2. Ambil foto orthomosaic 3. Klasifikasi supervised (kanopi vs. tanah) - **Output:** GCC (%) per blok - **Kelebihan:** Coverage luas, cepat - **Kekurangan:** Butuh izin terbang, cuaca dependent

**3\. Visual Assessment (Metode Praktis)** - **Alat:** Checklist + smartphone GPS - **Prosedur:** 1. Observer terlatih menilai GCC secara visual 2. Kategori: 0-20%, 20-40%, 40-60%, 60-80%, 80-100% 3. Catat koordinat GPS dan tanggal - **Output:** GCC (%) estimasi - **Kelebihan:** Cepat, murah, scalable - **Kekurangan:** Subjektif, butuh kalibrasi dengan metode 1 atau 2

#### B. Protokol Pengumpulan Data Lapangan

**Sampling Strategy:** - **Jumlah Sampel Minimum:** - Training: 200-300 blok per estate - Validation: 50-100 blok per estate - **Stratifikasi:** Sampel merata dari berbagai: - Umur tanaman (young, mature, old) - Klon (berbeda karakteristik kanopi) - Kondisi kesehatan (sehat, stress, sakit) - Musim (leaf flush, leaf fall, stable)

**Temporal Matching:** - Pengukuran lapangan harus dilakukan ±7 hari dari akuisisi satelit - Idealnya same-day untuk menghindari perubahan kondisi

**Spatial Matching:** - Koordinat GPS blok harus akurat (error < 10m) - Untuk blok besar, ambil multiple sampel dan rata-rata

**Format Database:**

┌──────────┬──────────┬────────────┬──────────┬──────────┬──────────┐  
│ Blok*ID │ GPS_Lat │ GPS_Lon │ Tanggal │ GCC*% │ Metode │  
├──────────┼──────────┼────────────┼──────────┼──────────┼──────────┤  
│ A01-001 │ -2.5432 │ 112.3456 │ 2026-01 │ 85.3 │ UAV │  
│ A01-002 │ -2.5445 │ 112.3478 │ 2026-01 │ 72.1 │ UAV │  
│ A02-015 │ -2.5523 │ 112.3512 │ 2026-01 │ 45.8 │ Visual │  
│ ... │ ... │ ... │ ... │ ... │ ... │  
└──────────┴──────────┴────────────┴──────────┴──────────┴──────────┘

### 4.4 Deteksi Anomali & Fenologi

#### A. Tantangan Khusus Karet: Gugur Daun Musiman

**Fenologi Normal Karet:** - **Leaf Fall (Gugur Daun):** 2-4 minggu per tahun (biasanya musim kemarau) - **Leaf Flush (Daun Baru):** 2-3 minggu setelah leaf fall - **Pola:** NDVI/GCC turun drastis (30-50%) lalu naik kembali

**Problem:** Sistem harus membedakan: - **Penurunan Normal:** Gugur daun musiman (tidak perlu alert) - **Penurunan Abnormal:** Penyakit, stres, defoliasi (perlu alert)

#### B. Solusi: STL Decomposition + Anomaly Detection

**STL (Seasonal-Trend decomposition using Loess):**

GCC_observed = Trend + Seasonal + Residual

**Komponen:** 1. **Trend:** Tren jangka panjang (naik/turun per tahun) 2. **Seasonal:** Pola musiman berulang (fenologi normal) 3. **Residual:** Deviasi dari pola normal (anomali)

**Algoritma Deteksi Anomali:**

from statsmodels.tsa.seasonal import STL  
<br/>\# 1. Decompose time-series GCC  
stl = STL(gcc_timeseries, seasonal=52) # 52 weeks = 1 tahun  
result = stl.fit()  
<br/>trend = result.trend  
seasonal = result.seasonal  
residual = result.resid  
<br/>\# 2. Hitung baseline normal (expected GCC)  
gcc_expected = trend + seasonal  
<br/>\# 3. Deteksi anomali dari residual  
threshold = 2 \* np.std(residual) # ±2 SD  
anomaly_mask = np.abs(residual) > threshold  
<br/>\# 4. Klasifikasi severity  
if residual < -threshold:  
status = "Anomali Negatif (Penurunan Abnormal)"  
if residual < -3 \* np.std(residual):  
priority = "Kritis"  
else:  
priority = "Waspada"  
elif residual > threshold:  
status = "Anomali Positif (Peningkatan Tidak Biasa)"  
priority = "Info"  
else:  
status = "Normal"  
priority = "OK"

**Visualisasi:**

GCC Time-Series dengan STL Decomposition  
─────────────────────────────────────────  
│ GCC Observed (%)  
│ 100 ┤ ╭╮  
│ 90 ┤ ╭╮ ╭╯╰╮ ╭╮  
│ 80 ┤ ╭──╯╰─╮ ╭─╯ ╰─╮ ╭─╯╰─  
│ 70 ┤ ╭─╯ ╰─╮╭─╯ ╰─╮╭╯  
│ 60 ┤ ╭─╯ ╰╯ ╰╯  
│ 50 ┤──╯  
│ └─────────────────────────────────────  
│ 2024 2025 2026  
│  
│ Trend (%)  
│ 85 ┤ ╭───────────────────  
│ 80 ┤ ╭────╯  
│ 75 ┤ ╭────╯  
│ 70 ┤────╯  
│ └─────────────────────────────────────  
│  
│ Seasonal (%)  
│ +15┤ ╭╮ ╭╮ ╭╮  
│ 0┤────╯╰────────╯╰────────╯╰───────  
│ -15┤ ╰╮ ╰╮ ╰╮  
│ └─────────────────────────────────────  
│  
│ Residual (Anomaly)  
│ +20┤ ● ← Anomali Positif  
│ 0┤────────────────────────────────────  
│ -20┤ ● ● ← Anomali Negatif  
│ └─────────────────────────────────────

#### C. Klasifikasi Status Blok

**Aturan Klasifikasi:**

| Status              | Kriteria                          | Warna  | Prioritas              |
| ------------------- | --------------------------------- | ------ | ---------------------- |
| **Normal**          | GCC dalam ±1 SD dari expected     | Hijau  | OK                     |
| **Waspada**         | GCC -1 hingga -2 SD dari expected | Kuning | Monitoring             |
| **Kritis**          | GCC < -2 SD dari expected         | Merah  | Inspeksi Segera        |
| **Anomali Positif** | GCC > +2 SD dari expected         | Biru   | Info (verifikasi data) |

## 5\. Arsitektur Sistem

### 5.1 Arsitektur Cloud-Native

┌─────────────────────────────────────────────────────────────────┐  
│ USER INTERFACE LAYER │  
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ │  
│ │ Web App │ │ Mobile App │ │ Admin Panel │ │  
│ │ (React) │ │ (Flutter) │ │ (React) │ │  
│ └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ │  
│ │ │ │ │  
│ └──────────────────┴──────────────────┘ │  
│ │ │  
└────────────────────────────┼─────────────────────────────────────┘  
│  
▼  
┌─────────────────────────────────────────────────────────────────┐  
│ API GATEWAY LAYER │  
│ ┌──────────────────────────────────────────────────────────┐ │  
│ │ FastAPI (Python) + Nginx │ │  
│ │ • Authentication (OAuth 2.0) │ │  
│ │ • Rate Limiting │ │  
│ │ • Request Routing │ │  
│ └──────────────────────────────────────────────────────────┘ │  
└────────────────────────────┬─────────────────────────────────────┘  
│  
┌──────────────┼──────────────┐  
│ │ │  
▼ ▼ ▼  
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐  
│ DATA SERVICE │ │ ML SERVICE │ │ ALERT SERVICE │  
│ │ │ │ │ │  
│ • Query GEE │ │ • Model Serving │ │ • Rule Engine │  
│ • Process │ │ • Batch Predict │ │ • Notification │  
│ • Cache Results │ │ • Explainability │ │ • Task Queue │  
└────────┬─────────┘ └────────┬─────────┘ └────────┬─────────┘  
│ │ │  
└────────────────────┴────────────────────┘  
│  
▼  
┌─────────────────────────────────────────────────────────────────┐  
│ DATA STORAGE LAYER │  
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ │  
│ │ PostgreSQL │ │ Redis │ │ Object │ │  
│ │ + PostGIS │ │ Cache │ │ Storage │ │  
│ │ (Metadata) │ │ (Sessions) │ │ (Rasters) │ │  
│ └──────────────┘ └──────────────┘ └──────────────┘ │  
└─────────────────────────────────────────────────────────────────┘  
│  
▼  
┌─────────────────────────────────────────────────────────────────┐  
│ SATELLITE DATA LAYER │  
│ ┌──────────────────────────────────────────────────────────┐ │  
│ │ Google Earth Engine (Primary) │ │  
│ │ • Sentinel-2 Archive │ │  
│ │ • Landsat-8/9 Archive │ │  
│ │ • Server-side Processing │ │  
│ └──────────────────────────────────────────────────────────┘ │  
│ │  
│ ┌──────────────────────────────────────────────────────────┐ │  
│ │ AWS S3 / GCS (Optional) │ │  
│ │ • Planet PlanetScope Data │ │  
│ │ • Preprocessed Composites │ │  
│ └──────────────────────────────────────────────────────────┘ │  
└─────────────────────────────────────────────────────────────────┘

### 5.2 Tech Stack Rekomendasi

#### A. Backend

| Komponen           | Teknologi                 | Justifikasi                                      |
| ------------------ | ------------------------- | ------------------------------------------------ |
| **API Framework**  | FastAPI (Python 3.10+)    | Async support, auto-documentation, type hints    |
| **Task Queue**     | Celery + Redis            | Async processing untuk batch prediction          |
| **Database**       | PostgreSQL 14+ + PostGIS  | Spatial queries, JSONB support, mature ecosystem |
| **Cache**          | Redis                     | High-performance caching untuk time-series data  |
| **ML Framework**   | scikit-learn, XGBoost     | Industry-standard, well-documented               |
| **GIS Processing** | GDAL, Rasterio, GeoPandas | Standard geospatial tools                        |
| **Time-Series**    | statsmodels, Prophet      | STL decomposition, forecasting                   |

#### B. Frontend

| Komponen             | Teknologi                | Justifikasi                                     |
| -------------------- | ------------------------ | ----------------------------------------------- |
| **Framework**        | React 18 + TypeScript    | Component-based, strong typing, large ecosystem |
| **Mapping**          | Leaflet / MapLibre GL JS | Open-source, performant, tile-based rendering   |
| **Charts**           | Plotly.js / Recharts     | Interactive charts, time-series support         |
| **State Management** | Redux Toolkit            | Predictable state, dev tools                    |
| **UI Components**    | Material-UI / Ant Design | Professional components, accessibility          |

#### C. Infrastructure

| Komponen             | Teknologi                   | Justifikasi                               |
| -------------------- | --------------------------- | ----------------------------------------- |
| **Cloud Platform**   | Google Cloud Platform (GCP) | Native GEE integration, geospatial tools  |
| **Containerization** | Docker + Docker Compose     | Reproducible environments                 |
| **Orchestration**    | Kubernetes (GKE)            | Scalability, auto-healing, load balancing |
| **CI/CD**            | GitHub Actions / GitLab CI  | Automated testing and deployment          |
| **Monitoring**       | Prometheus + Grafana        | Metrics, alerting, dashboards             |

### 5.3 Database Schema (Simplified)

\-- Tabel Estate (Hierarchy)  
CREATE TABLE estates (  
id SERIAL PRIMARY KEY,  
name VARCHAR(100),  
code VARCHAR(20) UNIQUE,  
geometry GEOMETRY(MultiPolygon, 4326),  
created_at TIMESTAMP DEFAULT NOW()  
);  
<br/>\-- Tabel Afdeling  
CREATE TABLE afdelings (  
id SERIAL PRIMARY KEY,  
estate_id INTEGER REFERENCES estates(id),  
name VARCHAR(100),  
code VARCHAR(20),  
geometry GEOMETRY(MultiPolygon, 4326)  
);  
<br/>\-- Tabel Blok  
CREATE TABLE blocks (  
id SERIAL PRIMARY KEY,  
afdeling_id INTEGER REFERENCES afdelings(id),  
name VARCHAR(100),  
code VARCHAR(20) UNIQUE,  
geometry GEOMETRY(Polygon, 4326),  
plant_year INTEGER,  
clone_type VARCHAR(50),  
area_ha NUMERIC(10, 2)  
);  
<br/>\-- Tabel Ground Truth (Data Lapangan)  
CREATE TABLE ground_truth (  
id SERIAL PRIMARY KEY,  
block_id INTEGER REFERENCES blocks(id),  
measurement_date DATE,  
gcc_percent NUMERIC(5, 2), -- Green Canopy Cover %  
method VARCHAR(50), -- 'UAV', 'Hemispherical', 'Visual'  
observer VARCHAR(100),  
notes TEXT,  
created_at TIMESTAMP DEFAULT NOW()  
);  
<br/>\-- Tabel Satellite Data (Preprocessed)  
CREATE TABLE satellite_data (  
id SERIAL PRIMARY KEY,  
block_id INTEGER REFERENCES blocks(id),  
acquisition_date DATE,  
sensor VARCHAR(20), -- 'Sentinel-2', 'Landsat-8', 'Planet'  
cloud_cover NUMERIC(5, 2),  
ndvi NUMERIC(6, 4),  
evi NUMERIC(6, 4),  
ndre NUMERIC(6, 4),  
savi NUMERIC(6, 4),  
gndvi NUMERIC(6, 4),  
created_at TIMESTAMP DEFAULT NOW(),  
UNIQUE(block_id, acquisition_date, sensor)  
);  
<br/>\-- Tabel Predictions (Output Model)  
CREATE TABLE predictions (  
id SERIAL PRIMARY KEY,  
block_id INTEGER REFERENCES blocks(id),  
prediction_date DATE,  
gcc_predicted NUMERIC(5, 2), -- Predicted Green Canopy Cover %  
gcc_confidence NUMERIC(5, 2), -- Confidence interval (±)  
model_version VARCHAR(20),  
created_at TIMESTAMP DEFAULT NOW()  
);  
<br/>\-- Tabel Anomalies (Deteksi Anomali)  
CREATE TABLE anomalies (  
id SERIAL PRIMARY KEY,  
block_id INTEGER REFERENCES blocks(id),  
detection_date DATE,  
anomaly_type VARCHAR(50), -- 'Negative', 'Positive'  
severity VARCHAR(20), -- 'Waspada', 'Kritis'  
residual_value NUMERIC(6, 2),  
status VARCHAR(20) DEFAULT 'Open', -- 'Open', 'Inspected', 'Resolved'  
notes TEXT,  
created_at TIMESTAMP DEFAULT NOW()  
);  
<br/>\-- Tabel Alerts (Alert untuk User)  
CREATE TABLE alerts (  
id SERIAL PRIMARY KEY,  
anomaly_id INTEGER REFERENCES anomalies(id),  
user_id INTEGER REFERENCES users(id),  
alert_type VARCHAR(50),  
priority VARCHAR(20), -- 'Tinggi', 'Sedang', 'Rendah'  
message TEXT,  
is_read BOOLEAN DEFAULT FALSE,  
created_at TIMESTAMP DEFAULT NOW()  
);  
<br/>\-- Tabel Field Inspections (Workflow Lapangan)  
CREATE TABLE field_inspections (  
id SERIAL PRIMARY KEY,  
anomaly_id INTEGER REFERENCES anomalies(id),  
inspector_id INTEGER REFERENCES users(id),  
inspection_date DATE,  
findings TEXT,  
photos JSONB, -- Array of photo URLs  
action_taken TEXT,  
created_at TIMESTAMP DEFAULT NOW()  
);

## 6\. Rekomendasi MVP

### 6.1 Fase 1: Core Foundation (Bulan 1-3)

**Tujuan:** Membangun fondasi sistem dengan fungsionalitas dasar

**Deliverables:**

- **Autentikasi & Manajemen User**
  - Login/logout (OAuth 2.0)
  - Role-based access (Admin, Manager, Viewer)
  - User profile management
- **Manajemen Area Kebun**
  - Upload batas estate/afdeling/blok (shapefile/GeoJSON)
  - CRUD operations untuk hierarchy kebun
  - Visualisasi peta batas
- **Pipeline Data Dasar**
  - Integrasi Google Earth Engine
  - Akuisisi Sentinel-2 dan Landsat-8/9
  - Perhitungan 5 indeks vegetasi (NDVI, EVI, NDRE, SAVI, GNDVI)
  - Cloud masking dan quality filtering
- **Peta Viewer (Explore Map)**
  - Visualisasi layer indeks vegetasi
  - Toggle layer on/off
  - Click blok → info panel
- **Time-Series Viewer Dasar**
  - Grafik NDVI/EVI/NDRE per blok (line chart)
  - Range selector (date range)

**Tech Stack:** - Backend: FastAPI + PostgreSQL + PostGIS - Frontend: React + Leaflet - Satellite: Google Earth Engine

**Success Criteria:** - User dapat login dan melihat peta estate - User dapat memilih blok dan melihat time-series NDVI/EVI - Data satelit ter-update otomatis setiap minggu

### 6.2 Fase 2: ML Model & Predictions (Bulan 4-6)

**Tujuan:** Implementasi model ML untuk prediksi GCC

**Deliverables:**

- **Data Lapangan Integration**
  - Form input data ground-truth (GCC %)
  - Upload batch dari CSV/Excel
  - Validasi spasial dan temporal matching
- **Model Training Pipeline**
  - Training Random Forest Regressor
  - Cross-validation dan hyperparameter tuning
  - Model evaluation (R², RMSE, MAE)
  - Save model dan feature importance
- **Batch Prediction**
  - Prediksi GCC untuk semua blok
  - Confidence interval calculation
  - Store predictions di database
- **Dashboard Utama**
  - KPI cards: Estate-level GCC, ΔMingguan, ΔBulanan
  - Peta status blok (color-coded by GCC)
  - Top 10 blok perlu inspeksi
- **Enhanced Time-Series**
  - Grafik GCC predicted + confidence interval
  - Overlay dengan GCC ground-truth (jika ada)
  - Export data ke CSV

**Tech Stack:** - ML: scikit-learn, XGBoost - Task Queue: Celery + Redis - Visualization: Plotly.js

**Success Criteria:** - Model mencapai R² > 0.75 pada test set - User dapat melihat prediksi GCC per blok di dashboard - Prediksi ter-update otomatis setiap minggu

### 6.3 Fase 3: Anomaly Detection & Alerts (Bulan 7-9)

**Tujuan:** Implementasi deteksi anomali dan alert system

**Deliverables:**

- **STL Decomposition**
  - Dekomposisi time-series GCC (Trend + Seasonal + Residual)
  - Visualisasi komponen terpisah di Time-Series Analyzer
- **Anomaly Detection**
  - Deteksi anomali dari residual (±2 SD threshold)
  - Klasifikasi severity (Waspada/Kritis)
  - Store anomalies di database
- **Alert System**
  - Configurable alert rules (per user/estate)
  - Email/SMS notifications
  - In-app notifications (badge counter)
- **Field Inspection Workflow**
  - Alert → Create inspection task
  - Mobile-friendly form untuk upload foto + notes
  - Update anomaly status (Open → Inspected → Resolved)
- **Reports & Export**
  - Monthly Canopy Health Report (PDF)
  - Anomaly & Inspection List (CSV)
  - Automated email delivery

**Tech Stack:** - Time-Series: statsmodels (STL) - Notifications: SendGrid (email), Twilio (SMS) - PDF Generation: ReportLab / WeasyPrint

**Success Criteria:** - Sistem dapat membedakan gugur daun musiman vs. anomali - Alert terkirim dalam < 24 jam setelah deteksi anomali - User dapat create dan track field inspection tasks

### 6.4 Fase 4: Advanced Features (Bulan 10-12 - Optional)

**Deliverables Lanjutan:**

- **Long-Term Trend Analysis**
  - 5-10 year trend per blok (slope, stability)
  - Year-over-year comparison heatmap
  - Regime shift detection
- **Model Studio**
  - Model management (versioning, A/B testing)
  - Explainability (SHAP values)
  - Data quality dashboard
- **Mobile App**
  - Flutter-based mobile app untuk field inspection
  - Offline mode untuk area tanpa internet
  - GPS-based photo tagging
- **Multi-Tenant Support**
  - Support multiple estates/companies
  - Data isolation per tenant
  - Billing & usage tracking
- **API Publik**
  - RESTful API untuk integrasi eksternal
  - API documentation (Swagger/OpenAPI)
  - Rate limiting dan authentication

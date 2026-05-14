Dokumentasi Arsitektur Basis Data PostGIS CanopySense

# Pendahuluan

Dokumen ini disusun untuk menjelaskan struktur, relasi, dan konfigurasi basis data spasial yang mendasari aplikasi Canopy Sense. Dokumentasi ini berfungsi sebagai panduan teknis untuk implementasi penyimpanan data menggunakan PostgreSQL dengan ekstensi PostGIS.

## Deskripsi

Canopy Sense merupakan platform pemantauan perkebunan karet berbasis cloud yang dirancang untuk mentransformasikan data mentah citra satelit optik—seperti Sentinel-2 dan Landsat-8/9—menjadi indikator Green Canopy Cover (GCC) yang konsisten. Arsitektur sistem ini mengintegrasikan algoritma Machine Learning (seperti Random Forest dan XGBoost) yang disinergikan dengan data validasi lapangan (ground-truth) guna menghasilkan estimasi persentase tutupan kanopi secara akurat. Melalui pengelolaan basis data spasial, Canopy Sense memungkinkan untuk melakukan pemantauan tren kesehatan vegetasi jangka panjang, mengidentifikasi anomali degradasi kanopi hingga skala blok, serta memicu notifikasi peringatan otomatis (alerts) untuk memfasilitasi kebutuhan inspeksi lapangan.

## Target Pengguna

Dokumentasi ini disusun sebagai kerangka operasional serta pedoman pengembangan teknis bagi para pemangku kepentingan berikut:

- Backend Developer; sebagai rujukan dalam implementasi koneksi, penyusunan spatial queries, pengelolaan task queue untuk prediksi batch, serta orkestrasi data interaksi aplikasi melalui framework FastAPI.
- Data Scientist; sebagai referensi akses data primer dalam ekstraksi fitur indeks vegetasi, pengembangan model Machine Learning, penyimpanan data ground-truth, serta mekanisme pencatatan hasil estimasi tutupan kanopi.
- Database Administrator; sebagai panduan utama manajemen instansi PostgreSQL/PostGIS, pemeliharaan skema tabel, performance tuning melalui pengindeksan spasial, pengelolaan struktur JSONB, serta optimasi relasi data.
- Tim Implementasi Teknis; guna memahami alur pemrosesan data secara menyeluruh, mulai dari penugasan inspeksi lapangan, identifikasi anomali vegetasi, hingga pembentukan laporan analitik yang terintegrasi ke dalam sistem.

# Arsitektur & Teknologi Basis Data

Komponen Data Storage Layer pada aplikasi Canopy Sense digunakan untuk menangani struktur data relasional sekaligus memfasilitasi penyimpanan dan pemrosesan komputasi cloud-based pada dataset spasial serta raster kompleks yang terintegrasi dengan citra satelit.

## DBMS Utama

Sistem manajemen basis data utama mengimplementasikan PostgreSQL versi 16.2 atau yang terbaru. Pemilihan arsitektur ini didasarkan pada maturitas ekosistem, stabilitas, serta performa optimal dalam mengelola volume data besar, termasuk penyimpanan data historis analitik time-series untuk pemantauan Green Canopy Cover (GCC) dan indeks vegetasi.

## Ekstensi Spasial

Guna mendukung kapabilitas operasional spasial, basis data diintegrasikan dengan ekstensi PostGIS yang memungkinkan sistem untuk:

- Mengelola penyimpanan data Geographic Information System (GIS) secara terpusat dalam skema basis data.
- Mengeksekusi fungsi analisis geospasial tingkat lanjut melalui pengindeksan spasial berbasis GiST (Generalized Search Tree) R-Tree guna optimasi pencarian data spasial skala besar.
- Menggunakan format JSONB untuk pencatatan metadata fleksibel serta penyimpanan array dokumentasi visual hasil inspeksi lapangan secara efisien.

## Tipe Data Spasial

Representasi batas wilayah perkebunan dalam sistem menggunakan tipe data Geometry dengan referensi koordinat SRID 4326 (WGS 84). Implementasi tipe data Geometry tersebut mencakup:

- Multipolygon; diimplementasikan pada entitas wilayah makro yang terdiri dari beberapa poligon terpisah, seperti pada level Estates (Kebun) dan Afdelings.
- Polygon; diimplementasikan untuk unit wilayah mikro pada tingkat Blocks (Blok) sebagai basis pemantauan varietas klon serta prediksi siklus umur tanaman secara presisi.

# Skema Tabel Basis Data

Bagian ini menyajikan rincian teknis mengenai skema tabel spasial yang merepresentasikan geometri wilayah, serta tabel atribut pendukung dalam ekosistem Canopy Sense. Seluruh arsitektur data ini dioptimasi secara khusus untuk mendukung kebutuhan spatial queries analitik serta orkestrasi relasi spasial tingkat lanjut.

## Tabel Hierarki Spasial Perkebunan

Penyimpanan delimitasi batas wilayah perkebunan diorganisir secara sistematis ke dalam beberapa tingkatan hierarki: Estates (Kebun), Afdelings, dan Blocks (Blok). Setiap tabel dilengkapi dengan kolom spasial yang dikonfigurasi melalui ekstensi PostGIS dengan sistem referensi koordinat SRID 4326 (WGS 84).

- Tabel estates

Tabel estates berfungsi untuk mengelola informasi deskriptif serta batas wilayah administratif kebun secara makro. Representasi geometri yang diterapkan pada entitas ini adalah tipe data MultiPolygon.

**Kolom**

**Tipe Data**

**Keterangan/Constraints**

id

SERIAL

PRIMARY KEY

name

VARCHAR(100)

NOT NULL, Identitas nama unit kebun/estate

code

VARCHAR(20)

UNIQUE NOT NULL, kode pengenal unik instansi

updated_at

TIMESTAMP

Metadata waktu pembaruan terakhir

geometry

GEOMETRY

MultiPolygonZ, SRID 4326, NOT NULL

envelope

GEOMETRY

GENERATED STORED, Bounding box spasial

area_ha

NUMERIC(10,2)

GENERATED STORED, Luas area dalam hektar

is_valid

BOOLEAN

GENERATED STORED, Hasil validasi geometri (ST_IsValid)

created_at

TIMESTAMP

DEFAULT NOW(), metadata waktu pembuatan

CREATE TABLE estates (

 id SERIAL PRIMARY KEY,

 name VARCHAR(100) NOT NULL,

 code VARCHAR(20) UNIQUE NOT NULL,

 geometry GEOMETRY(MultiPolygonZ,4326) NOT NULL,

 envelope GEOMETRY GENERATED ALWAYS AS (ST_Envelope(geometry)) STORED,

 area_ha NUMERIC(10,2) GENERATED ALWAYS AS (ST_Area(geometry::geography)/10000) STORED,

 is_valid BOOLEAN GENERATED ALWAYS AS (ST_IsValid(geometry)) STORED,

 created_at TIMESTAMP DEFAULT NOW(),

 updated_at TIMESTAMP

);

-- Indexes WAJIB

CREATE INDEX CONCURRENTLY idx_estates_geom ON estates USING GIST(geometry);

CREATE INDEX CONCURRENTLY idx_estates_envelope ON estates USING GIST(envelope);

CREATE INDEX idx_estates_code ON estates(code);

-- Constraints WAJIB

ALTER TABLE estates ADD CONSTRAINT chk_estate_valid

CHECK (ST_IsValid(geometry) AND ST_SRID(geometry)=4326);

 

- Tabel afdelings

Tabel afdelings menyimpan batas tingkat afdeling (pembagian lahan di bawah tingkat estate). Tabel ini memiliki relasi Foreign Key ke tabel estates untuk merangkai hierarki data. Representasi geometri yang diterapkan adalah MultiPolygon.

**Kolom**

**Tipe Data**

**Keterangan/Constraints**

id

SERIAL

PRIMARY KEY

estate_id

INTEGER

REFERENCES estates(id)

name

VARCHAR(100)

Identitas nama unit afdeling

code

VARCHAR(20)

Kode pengenal unik afdeling

geometry

GEOMETRY

MultiPolygon, SRID 4326

CREATE TABLE afdelings (

    id SERIAL PRIMARY KEY,

    estate_id INTEGER REFERENCES estates(id),

    name VARCHAR(100),

    code VARCHAR(20),

    geometry GEOMETRY(MultiPolygon, 4326) NOT NULL

);

-- Indexes WAJIB

CREATE INDEX CONCURRENTLY idx_afdelings_geom ON afdelings USING GIST(geometry);

CREATE INDEX idx_afdelings_estate ON afdelings(estate_id);

-- Constraints WAJIB

ALTER TABLE afdelings ADD CONSTRAINT chk_afdeling_type

CHECK (GeometryType(geometry) = 'MULTIPOLYGON');



- Tabel blocks

Tabel blocks menyimpan batas tingkat blok terkecil yang menjadi unit operasional utama dalam Canopy Sense. Tabel ini tidak hanya menyimpan batas poligon, tetapi juga atribut agronomi penting seperti umur tanaman dan jenis klon. Geometri yang digunakan adalah Polygon.

**Kolom**

**Tipe Data**

**Keterangan/Constraints**

id

SERIAL

PRIMARY KEY

afdeling_id

INTEGER

REFERENCES afdelings(id)

name

VARCHAR(100)

Identitas nama unit blok

code

VARCHAR(20)

UNIQUE

geometry

GEOMETRY

Polygon, SRID 4326, NOT NULL

plant_year

INTEGER

Tahun penanaman

clone_type

VARCHAR(50)

Jenis klon karet

area_ha

NUMERIC(10,2)

GENERATED STORED, Luas area dalam hektar

CREATE TABLE blocks (

    id SERIAL PRIMARY KEY,

    afdeling_id INTEGER REFERENCES afdelings(id),

    name VARCHAR(100),

    code VARCHAR(20) UNIQUE,

    geometry GEOMETRY(Polygon, 4326) NOT NULL,

    plant_year INTEGER,

    clone_type VARCHAR(50),

    area_ha NUMERIC(10, 2) GENERATED ALWAYS AS (ST_Area(geometry::geography)/10000) STORED

);

ALTER TABLE blocks ADD CONSTRAINT chk_blocks_type CHECK (GeometryType(geometry) = 'POLYGON');



## 

## Tabel Data Analitik & Operasional (Non-Spatial/Relational Tables)

	Tabel-tabel di bawah ini berelasi dengan tabel spasial blocks menggunakan Foreign Key, memungkinkan integrasi antara data atribut time-series dengan batas geografis untuk divisualisasikan pada Peta Interaktif (Explore Map). 

- Tabel ground_truth

Tabel ground_truth Menyimpan data pengukuran persentase Green Canopy Cover (GCC) aktual dari lapangan yang digunakan sebagai data latih (training data) bagi model Machine Learning.

**Kolom**

**Tipe Data**

**Keterangan/Constraints**

id

SERIAL

PRIMARY KEY

block_id

INTEGER

REFERENCES blocks(id)

satellite_data_id

INTEGER

REFERENCES satellite_data(id)

measurement_date

DATE

Tanggal pengukuran lapangan

gcc_percent

NUMERIC(5, 2)

Green Canopy Cover %

method

VARCHAR(50)

Metode pengukuran ('UAV', 'Hemispherical', 'Visual')

observer

VARCHAR(100)

Nama petugas/observer

notes

TEXT

Catatan tambahan

created_at

TIMESTAMP

DEFAULT NOW(), metadata waktu pembuatan

CREATE TABLE ground_truth (

    id SERIAL PRIMARY KEY,

    block_id INTEGER REFERENCES blocks(id),

    satellite_data_id INTEGER REFERENCES satellite_data(id),

    measurement_date DATE,

    gcc_percent NUMERIC(5, 2),

    method VARCHAR(50),

    observer VARCHAR(100),

    notes TEXT,

    created_at TIMESTAMP DEFAULT NOW()

);



- Tabel satellite_data

Tabel satellite_data Menyimpan data pra-pemrosesan metrik satelit (seperti Sentinel-2 atau Landsat-8/9) per akuisisi. Seluruh data pada tabel ini bersifat **immutable (tidak dapat diperbarui)** guna menjaga integritas data historis. Tabel ini merekam tingkat tutupan awan (cloud cover) dan kelima indeks vegetasi utama yang menjadi fitur (feature engineering) dalam pemodelan.

**Kolom**

**Tipe Data**

**Keterangan/Constraints**

id

SERIAL

PRIMARY KEY

block_id

INTEGER

REFERENCES blocks(id)

acquisition_date

DATE

Tanggal akuisisi citra satelit

sensor

VARCHAR(20)

Tipe sensor ('Sentinel-2', 'Landsat-8', 'Planet')

cloud_cover

NUMERIC(5, 2)

Persentase tutupan awan

ndvi

FLOAT

Normalized Difference Vegetation Index

evi

FLOAT

Enhanced Vegetation Index

ndre

FLOAT

Normalized Difference Red Edge

savi

FLOAT

Soil Adjusted Vegetation Index

gndvi

FLOAT

Green Normalized Difference Vegetation Index

features

JSONB

Kumpulan fitur indeks vegetasi tambahan

created_at

TIMESTAMP

DEFAULT NOW(), metadata waktu pembuatan

(Constraint)

UNIQUE

block_id, acquisition_date, sensor

CREATE TABLE satellite_data (

    id SERIAL PRIMARY KEY,

    block_id INTEGER REFERENCES blocks(id),

    acquisition_date DATE,

    sensor VARCHAR(20) DEFAULT 'sentinel-2',

    cloud_cover NUMERIC(5, 2),

    ndvi FLOAT,

    evi FLOAT,

    ndre FLOAT,

    savi FLOAT,

    gndvi FLOAT,

    features JSONB,

    created_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(block_id, acquisition_date, sensor)

);



- Tabel predictions

Tabel predictions menyerap data hasil prediksi Green Canopy Cover per blok per tanggal akuisisi. Menggunakan sistem append-only untuk menjaga riwayat versi model.

**Kolom**

**Tipe Data**

**Keterangan/Constraints**

id

SERIAL

PRIMARY KEY

satellite_data_id

INTEGER

REFERENCES satellite_data(id)

prediction_date

DATE

Tanggal prediksi dilakukan

gcc_predicted

FLOAT

Predicted Green Canopy Cover %

gcc_confidence

FLOAT

Confidence interval (±)

model_version

VARCHAR(30)

Versi model ML yang digunakan

created_at

TIMESTAMP

DEFAULT NOW()

(Constraint)

UNIQUE

satellite_data_id, model_version

CREATE TABLE predictions (

    id SERIAL PRIMARY KEY,

    satellite_data_id INTEGER REFERENCES satellite_data(id),

    prediction_date DATE,

    gcc_predicted FLOAT,

    gcc_confidence FLOAT,

    model_version VARCHAR(30),

    created_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(satellite_data_id, model_version)

);



- Tabel anomalies

Tabel anomalies wajib menyimpan prediction_id untuk memastikan keterlacakan (traceability) antara deteksi dan hasil model ML.

**Kolom**

**Tipe Data**

**Keterangan/Constraints**

id

SERIAL

PRIMARY KEY

prediction_id

INTEGER

REFERENCES predictions(id), UNIQUE

actual_gcc

FLOAT

GCC aktual dari ground truth

deviation

FLOAT

Selisih prediksi vs aktual

status

VARCHAR(20)

CHECK status IN ('OPEN', 'VERIFIED', 'FALSE_POSITIVE', 'RESOLVED')

detected_at

TIMESTAMP

Waktu anomali terdeteksi

reviewed_at

TIMESTAMP

Waktu review oleh petugas

reviewed_by

INTEGER

REFERENCES users(id)

notes

TEXT

Catatan internal sistem

CREATE TABLE anomalies (

    id SERIAL PRIMARY KEY,

    prediction_id INTEGER REFERENCES predictions(id) UNIQUE,

    actual_gcc FLOAT,

    deviation FLOAT,

    status VARCHAR(20) DEFAULT 'OPEN',

    detected_at TIMESTAMP DEFAULT NOW(),

    reviewed_at TIMESTAMP,

    reviewed_by INTEGER REFERENCES users(id),

    notes TEXT,

    CONSTRAINT chk_status CHECK (status IN ('OPEN', 'VERIFIED', 'FALSE_POSITIVE', 'RESOLVED'))

);



- Tabel alerts

Tabel alerts Menampung notifikasi peringatan yang ditujukan kepada pengguna/pengelola kebun berdasarkan aturan yang memicu deteksi pada tabel anomalies. (Catatan: Relasi users(id) merujuk pada tabel manajemen pengguna di skema autentikasi aplikasi).

**Kolom**

**Tipe Data**

**Keterangan/Constraints**

id

SERIAL

PRIMARY KEY

anomaly_id

INTEGER

REFERENCES anomalies(id)

user_id

INTEGER

REFERENCES users(id) (Merujuk skema autentikasi)

alert_type

VARCHAR(50)

Jenis peringatan

priority

VARCHAR(20)

Tingkat prioritas ('Tinggi', 'Sedang', 'Rendah')

message

TEXT

Pesan notifikasi

is_read

BOOLEAN

DEFAULT FALSE, status sudah dibaca

created_at

TIMESTAMP

DEFAULT NOW(), metadata waktu pembuatan

CREATE TABLE alerts (

    id SERIAL PRIMARY KEY,

    anomaly_id INTEGER REFERENCES anomalies(id),

    user_id INTEGER REFERENCES users(id),

    alert_type VARCHAR(50),

    priority VARCHAR(20),

    message TEXT,

    is_read BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMP DEFAULT NOW()

);



- Tabel field_inspections

Tabel field_inspections mencatat hasil penugasan pemeriksaan lapangan oleh petugas lapangan saat merespons sebuah anomali. Pencatatan inspeksi **wajib memicu pembaruan pada tabel anomalies (khususnya kolom actual_gcc dan status)** untuk menjaga kontrak siklus hidup anomali. Tabel ini berupa penyimpanan JSONB pada PostgreSQL untuk menyimpan format array berisi tautan foto.

**Kolom**

**Tipe Data**

**Keterangan/Constraints**

id

SERIAL

PRIMARY KEY

anomaly_id

INTEGER

REFERENCES anomalies(id), UNIQUE

inspector_id

INTEGER

REFERENCES users(id)

actual_gcc

FLOAT

Nilai GCC hasil validasi lapangan

notes

TEXT

Temuan dan tindakan korektif lapangan

photos

JSONB

Array tautan dokumentasi visual

inspected_at

TIMESTAMP

Waktu pelaksanaan inspeksi

created_at

TIMESTAMP

DEFAULT NOW()

CREATE TABLE field_inspections (

    id SERIAL PRIMARY KEY,

    anomaly_id INTEGER REFERENCES anomalies(id) UNIQUE,

    inspector_id INTEGER REFERENCES users(id),

    actual_gcc FLOAT,

    notes TEXT,

    photos JSONB,

    inspected_at TIMESTAMP,

    created_at TIMESTAMP DEFAULT NOW()

);



- Tabel users

Tabel users berperan sebagai repositori pusat untuk manajemen data otentikasi serta profil pengguna di dalam ekosistem Canopy Sense. Entitas ini menjadi referensi Foreign Key fundamental bagi mekanisme Role-Based Access Control (RBAC) serta orkestrasi penugasan operasional, termasuk distribusi notifikasi alerts dan identifikasi personel inspeksi lapangan.

**Kolom**

**Tipe Data**

**Keterangan/Constraints**

id

SERIAL

PRIMARY KEY

email

VARCHAR(150)

UNIQUE, alamat email pengguna

full_name

VARCHAR(150)

Nama lengkap pengguna sesuai identitas

username

VARCHAR(150)

Nama pengenal unik akun (username)

phone_number

VARCHAR(20)

Nomor kontak telepon aktif

is_global_admin

BOOLEAN

DEFAULT FALSE, hak akses sistem secara global

is_active

updated_at

BOOLEAN

TIMESTAMP

DEFAULT TRUE, status aktifasi akun

Metadata waktu pembaruan terakhir

created_at

TIMESTAMP

DEFAULT NOW(), metadata waktu pendaftaran

CREATE TABLE users (

    id SERIAL PRIMARY KEY,

    email VARCHAR(150) UNIQUE,

    full_name VARCHAR(150),

    username VARCHAR(150),

    phone_number VARCHAR(20),

    is_global_admin BOOLEAN DEFAULT FALSE,

    is_active BOOLEAN DEFAULT TRUE,

    updated_at TIMESTAMP,

    created_at TIMESTAMP DEFAULT NOW()

);



- Tabel user_estate_roles

Tabel user_estate_roles diimplementasikan sebagai entitas asosiatif guna memodelkan relasi Many-to-Many (N-N) antara pengguna (users) dan unit kebun (estates). Tabel ini mendefinisikan otoritas dan peran spesifik yang dimiliki pengguna dalam lingkup administrasi wilayah kebun tertentu.

**Kolom**

**Tipe Data**

**Keterangan/Constraints**

user_id

INTEGER

PRIMARY KEY & REFERENCES users(id)

scope_id

INTEGER

PRIMARY KEY, ID dari wilayah terkait (Estate/Afdeling/Block)

scope_type

VARCHAR(50)

PRIMARY KEY, Tipe cakupan ('Estate', 'Afdeling', 'Block')

role

VARCHAR(50)

Peran pengguna ('Manager', 'Viewer', 'Inspector')

(Constraint)

PRIMARY KEY

Komposit user_id, scope_id, dan scope_type

CREATE TABLE user_estate_roles (

    user_id INTEGER REFERENCES users(id),

    scope_id INTEGER,

    scope_type VARCHAR(50),

    role VARCHAR(50) NOT NULL,

    created_at TIMESTAMP DEFAULT NOW(),

    PRIMARY KEY (user_id, scope_id, scope_type)

);

## 

## Implementasi Role-Based Access Control (RBAC)

Dalam sistem aplikasi Canopy Sense, otoritas pengguna dikelola melalui mekanisme Role-Based Access Control (RBAC). Hak akses didefinisikan ke dalam empat peran utama yang menentukan level kontrol terhadap data spasial dan operasional sebagai berikut:

**Peran**

**Level Kontrol**

**Tabel Relasi**

**Hak Akses**

Administrator

Global (Sistem)

users.is_global_admin

**System Write & Full Control;** mengelola seluruh konfigurasi sistem, basis data, manajemen pengguna global, serta fitur level aplikasi secara menyeluruh.

Manager

Estate (Wilayah)

user_estate_roles

**Estate Write & Control;** melakukan kurasi batas wilayah estate/block, konfigurasi unit kebun, manajemen keanggotaan pengguna, penunjukan inspektor, serta akses penuh terhadap data analitik.

Inspector

Operasional

user_estate_roles

**Operational Write;** mengeksekusi penugasan inspeksi lapangan, melakukan pencatatan observasi pada tabel field_inspections, serta mengunggah dokumentasi visual. Memiliki hak akses Viewer.

Viewer

Wilayah (Read-Only)

user_estate_roles

**Read-Only Access;** visualisasi seluruh data geospasial (peta interaktif, batas blok/afdeling), akses data time-series, hasil estimasi predictions, serta penerimaan notifikasi anomali tanpa hak modifikasi data.

# Diagram Hubungan Entitas (ERD)

Bagian ini memaparkan representasi visual arsitektur basis data Canopy Sense guna mengilustrasikan interkoneksi antar entitas melalui mekanisme kunci (Primary Key dan Foreign Key) serta kardinalitas sistem yang diimplementasikan pada skema fisik relasional PostGIS 16.2.

![placeholder](https://markdowntoword.io/placeholder.png)

Arsitektur data dalam ekosistem Canopy Sense dikonstruksi berbasis hierarki spasial yang berfungsi sebagai jangkar integrasi bagi dataset analitik time-series serta orkestrasi data operasional lapangan. Struktur relasi kunci utama didefinisikan sebagai berikut:

- Relasi One-to-Many diterapkan secara berjenjang dari entitas estates menuju afdelings, hingga berakhir pada tingkat blocks. Relasi ini menjamin integritas topologi di mana setiap unit lahan mikro dipastikan berada dalam unit administratif yang lebih luas.
- Entitas satellite_data dan ground_truth terhubung secara One-to-Many dengan tabel blocks melalui referensi block_id. Khusus pada satellite_data, diterapkan unique constraint pada kombinasi block_id dan acquisition_date guna menjaga konsistensi data spektral.
- Entitas predictions berelasi dengan blocks serta memiliki referensi Foreign Key eksplisit menuju satellite_data_id. Implementasi kolom model_version menjadi instrumen krusial dalam membedakan luaran antar iterasi model Machine Learning.
- Entitas anomalies mengimplementasikan relasi ganda, yakni terhubung ke blocks untuk referensi lokasi spasial serta ke predictions_id guna menyediakan konteks kausalitas deteksi. Arsitektur ini memungkinkan sistem memberikan eksplanasi atas pemicu munculnya peringatan kepada pengguna.
- Tabel operasional alerts dan field_inspections dikaitkan melalui relasi One-to-Many dengan entitas anomalies. Hal ini memastikan setiap intervensi korektif di lapangan memiliki jejak digital yang merujuk pada pemicu anomali yang spesifik.
- abel users berperan sebagai aktor utama dalam penerimaan alerts dan pelaksanaan field_inspections. Otoritas hak akses pada wilayah kebun tertentu dimodelkan melalui relasi Many-to-Many melalui entitas asosiatif user_estate_roles.

# Optimasi Indeks Spasial & Performa

Guna menjamin efisiensi eksekusi spatial queries pada dataset bervolume besar, strategi pengindeksan diterapkan secara komprehensif. Hal ini krusial untuk mendukung visualisasi intensif seperti heatmap serta pemantauan status anomali pada berbagai tingkatan hierarki wilayah perkebunan.

## Pengindeksan Spasial dengan GiST

Seluruh entitas kolom bertipe Geometry dalam PostGIS disarankan untuk didukung oleh indeks spasial. Standar arsitektur ini mengimplementasikan indeks GiST (Generalized Search Tree) berbasis R-Tree guna mengakselerasi fungsi analitik geospasial, seperti identifikasi interseksi blok secara presisi.

Implementasi SQL:

CREATE INDEX CONCURRENTLY idx_estates_geometry ON estates USING GIST (geometry);

CREATE INDEX CONCURRENTLY idx_afdelings_geometry ON afdelings USING GIST (geometry);

CREATE INDEX CONCURRENTLY idx_blocks_geometry ON blocks USING GIST (geometry);



## Optimasi CLUSTERing pada Geometri

Pada tabel dengan volume data tinggi, optimasi dilakukan melalui teknik CLUSTER berdasarkan indeks geometri. Mekanisme ini menyusun ulang organisasi data fisik pada disk sesuai urutan spasialnya, sehingga kueri terhadap unit wilayah yang berdekatan dapat dimuat dengan performa yang jauh lebih optimal.

Implementasi SQL:

CLUSTER blocks USING idx_blocks_geometry;

ANALYZE blocks;



## Pengindeksan Data Time-Series (Non-Spasial)

Seiring dengan pertumbuhan volume data pada tabel satellite_data dan predictions akibat akumulasi siklus akuisisi satelit, implementasi indeks komposit (composite index) menjadi krusial. Indeks ini diterapkan pada Foreign Key dan atribut tanggal untuk mempercepat filtrasi kueri berbasis rentang waktu.

Implementasi SQL:

CREATE INDEX idx_satellite_date_block ON satellite_data (block_id, acquisition_date DESC);

CREATE INDEX idx_predictions_date_block ON predictions (block_id, prediction_date DESC);

CREATE INDEX idx_anomalies_detection_block ON anomalies (block_id, detection_date DESC);

.

# Manajemen Data Spasial

Lapis manajemen data spasial menetapkan standar protokol bagi mekanisme ingest (loading) serta ekstraksi dataset geospasial dalam ekosistem Canopy Sense. Arsitektur ini dirancang untuk menjamin persistensi integritas antara representasi lokasi spasial dengan atribut deskriptif non-spasial di sepanjang siklus hidup data.

- **Impor Data (Loading Spatial Data):** Pada fase inisiasi, delimitasi batas hierarki wilayah (estate, afdeling, dan blok) dapat diunggah melalui format vektor standar industri, seperti Shapefile atau GeoJSON. Dataset vektor ini krusial untuk analisis dengan presisi geometris tinggi, seperti penentuan batas kadaster perkebunan. Data kemudian ditransformasikan menjadi tipe Geometry pada PostGIS dengan referensi koordinat SRID 4326.
- **Ekspor Vektor (Extracting Spatial Data):** Guna mendukung interoperabilitas dengan sistem GIS eksternal, dataset anomali, hasil inspeksi, dan batas wilayah dapat diekstraksi ke dalam format GeoJSON, Shapefile, maupun GeoPackage untuk keperluan pelaporan analitik lanjut.
- **Ekspor Data Raster (Extracting Raster Data):** Guna mendistribusikan luaran estimasi model dalam bentuk visualisasi spasial Green Canopy Cover (GCC), sistem menyediakan kapabilitas ekspor menuju format Cloud Optimized GeoTIFF (COG). Struktur raster berbasis grid (piksel) tersebut dioptimasi secara khusus guna mempercepat performa penyajian pada platform pemetaan berbasis cloud. Sebagai alternatif, metodologi Vector Point Cloud dapat diimplementasikan melalui pendefinisian nilai setiap piksel ke dalam skema tabel; kendati demikian, penentuan paradigma ini secara signifikan mempengaruhi skalabilitas performa sistem, sebagaimana diuraikan secara komprehensif pada sub-bab berikutnya.

## Analisis Komparatif Metodologi Vektor Point-Cloud dan Cloud-Tiling Raster

Bagian ini menyajikan evaluasi teknis mengenai arsitektur dalam mekanisme dataset raster ke dalam repositori basis data. Perbandingan mendalam antara kedua metodologi tersebut diuraikan pada tabel berikut.

**Metodologi Arsitektur**

**Luaran Penyimpanan**

**Risiko Performa & Skalabilitas**

**Keunggulan Teknis**

Vektor Point-Cloud

PostGIS (Entitas Tabel Titik/Piksel)

**Risiko Tinggi;** volume data berpotensi menjadi masif (mencapai jutaan baris per siklus akuisisi), degradasi latensi kueri, serta beban komputasi tinggi pada backend dalam membuat grid raster.

Fleksibilitas kueri dalam bentuk data spasial titik, simplisitas implementasi dalam skema relasional, serta kemudahan kalkulasi nilai untuk kebutuhan visualisasi grafik analitik.

Raster/ Cloud Tiling (COG)

Object Storage (S3/GCS) atau Tipe Data RASTER PostGIS

**Risiko Rendah;** performa optimal dalam pengelolaan volume data besar, penyajian data secara langsung dalam format tiles, namun data menjadi terpisah dari database pusat yang mana perlu disimpan melalui layanan cloud storage.

Sangat optimal dan dirancang khusus untuk kebutuhan visualisasi peta web berbasis raster dengan performa tinggi.

Terlepas dari metodologi mana yang akan diimplementasikan, tim pengembang harus memitigasi risiko performa guna menjamin stabilitas operasional pada aplikasi Canopy Sense.

# Kueri Spasial & Fungsi PostGIS (Spatial Queries & Functions)

Operasional aplikasi berbasis PostGIS ini sangat bergantung pada kapabilitas eksekusi kueri dalam mengidentifikasi relasi spasial. Berikut merupakan implementasi kueri spasial utama yang dikelola oleh backend Canopy Sense melalui framework FastAPI:

- **Pemetaan Data Lapangan ke Blok (Spatial Joins):** Saat sistem menerima unggahan titik koordinat data ground-truth, fungsi ST_Contains atau ST_Intersects digunakan untuk melakukan validasi pencocokan koordinat terhadap poligon unit blok secara otomatis.
- **Menghitung Area Luasan Blok:** pengukuran luas pada PostGIS (ST_Area) diimplementasikan untuk memverifikasi akurasi nilai atribut area_ha memastikan integritas data geometris tetap krusial untuk normalisasi data analitik GCC.
- **Ekstraksi untuk Peta Web (Web Mapping):** Guna memfasilitasi visualisasi batas blok pada peta interaktif, sistem mengeksekusi fungsi ST_AsGeoJSON untuk konversi geometri langsung dari sisi server.

# Administrasi & Pemeliharaan Database

Bagian ini berfungsi sebagai kerangka operasional bagi Database Administrator (DBA) dalam mengelola instansi PostgreSQL/PostGIS guna menjamin stabilitas ekosistem.

- **Pembuatan Template Database Spasial:** Implementasi template_postgis direkomendasikan untuk memfasilitasi replikasi environment secara instan di seluruh tahap development, testing, hingga production.

Dokumentasi implementasi skema SQL template_postgis guna mendukung operasional sistem.

-- Instruksi DDL untuk implementasi Template Basis Data Spasial

CREATE DATABASE canopy_template_db WITH TEMPLATE = template0 ENCODING = 'UTF8';

\c canopy_template_db

CREATE EXTENSION postgis;

-- Entitas template tersebut selanjutnya dimanfaatkan sebagai basis replikasi environment sistem.

- **Pencadangan dan Pemulihan (Backup & Restore):** Mekanisme pencadangan periodik harus mengamankan dataset relasional time-series sekaligus data spasial guna menjaga persistensi log peringatan (alerts) serta dokumentasi inspeksi.
- **Pembaruan Versi (Upgrading):** Dalam proses pemutakhiran versi PostGIS, integritas fungsi geometri dan performa indeks GiST harus dipastikan tetap optimal tanpa mendegradasi integritas data historis sistem.
- **Pembaruan Data Citra secara Berkala:** Guna menjamin aktualitas data pada platform Canopy Sense, orkestrasi scheduled_task mingguan dikonfigurasi pada jam non-operasional untuk menjaga efisiensi performa sistem secara menyeluruh.
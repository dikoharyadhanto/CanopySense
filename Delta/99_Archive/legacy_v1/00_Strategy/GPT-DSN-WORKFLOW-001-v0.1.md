# GPT Design Doc (Workflow/UI)
> [!IMPORTANT]
> **Logic Dependencies**: Requires `GMN-PRD` + `GMN-FLOW`.

# GPT Design Document (DSN)

## Metadata

Project ID: 001  
Product Name: Canopy Sense  
Product Type:

* SaaS
* AI Agent
* CLI Tool
* API
* Automation
* Internal Tool
* System
* Other: Remote Sensing Monitoring Engine

Target Type:

* WORKFLOW

Version: v0.1  
File: GPT-DSN-WORKFLOW-001-v0.1.md  
Author: ChatGPT (Workflow Consultant)  
Date: 2026-03-31

## Related Documents:

* GMN-PRD-001 (Canopy Sense Product Requirement)
* GMN-FLOW-001 (Weekly Monitoring Flow)

---

# 1. Problem Framing

## Current Situation:
Manager perkebunan membutuhkan monitoring kondisi kanopi mingguan berbasis satelit. Data tersedia dari Sentinel dan Landsat namun memiliki masalah utama berupa awan, noise, dan variasi temporal. Tanpa workflow seleksi kualitas, nilai indeks vegetasi menjadi tidak stabil dan sulit digunakan untuk keputusan operasional.

## User Pain:
- Nilai NDVI berubah drastis akibat awan
- Tidak ada indikator kualitas data
- Tidak jelas apakah perubahan vegetasi nyata atau artefak citra
- Monitoring multi-estate sulit dilakukan manual
- Data satelit tidak konsisten mingguan

## Why existing solutions fail:
- Menggunakan composite yang terlalu “bersih” dan tidak realistis
- Menggunakan scene terbaru tanpa quality control
- Tidak ada valid pixel ratio
- Tidak ada mekanisme flag kualitas rendah

## Opportunity:
Membangun workflow engine mingguan yang memilih citra terbaru yang memenuhi standar kualitas minimum, tetap menjaga realitas observasi, dan menghasilkan indikator kualitas untuk pengambilan keputusan manajerial.

---

# 2. Target User

## Primary User:
Manager Perkebunan (Estate Manager / Regional Manager)

## Secondary User:
- Agronomy Team
- GIS Analyst
- Plantation Data Team
- Head Office Monitoring Team

User Skill Level:

* Non-technical
* Semi-technical

## User Goal:
Melihat kondisi vegetasi mingguan yang stabil, realistis, dan dapat dipercaya untuk mendeteksi perubahan kondisi kebun.

---

# 3. Product Positioning

This product is:
"A weekly satellite-based canopy monitoring engine for plantation managers"

## Category:
Remote Sensing Monitoring Engine

## Differentiation:
- Weekly deterministic pipeline
- Quality-aware scene selection
- No temporal composite
- Valid pixel ratio metric
- Multi-estate batch processing
- Dual sensor support (Sentinel + Landsat)

## Anti-Goals:

* Tidak melakukan temporal smoothing
* Tidak melakukan composite lintas tanggal
* Tidak melakukan AI prediction
* Tidak melakukan anomaly detection (Stage 1)

---

# 4. Core Value Proposition

## Primary Value:
Memberikan nilai indeks vegetasi mingguan yang realistis dan dapat dipercaya untuk monitoring kondisi kebun.

## Secondary Value:
Memberikan indikator kualitas data agar manager memahami reliabilitas observasi.

## First Value Moment:
User melihat NDVI mingguan dengan flag kualitas dan memahami apakah perubahan nilai valid.

## Why user continues using:
- Konsistensi mingguan
- Data tidak misleading
- Mudah dibandingkan antar estate
- Mendukung keputusan operasional

---

# 5. Workflow Overview

High-level flow:

Step 1: Weekly scheduler trigger  
Step 2: Loop multi-estate processing  
Step 3: Scene query last 7 days  
Step 4: Quality-aware scene selection  
Step 5: Vegetation index computation  
Step 6: Zonal statistics per block  
Step 7: Quality evaluation  
Step 8: Save versioned result  

## Entry Point:
Weekly cron scheduler (Senin 02:00)

## Exit Output:
Weekly vegetation index per block dengan quality flag

---

# 6. User Journey (Detailed)

## User enters with:
User mengupload boundary estate dan block.

## System responds:
System menjalankan engine mingguan secara otomatis.

## User decision:
User hanya melihat hasil monitoring mingguan.

## AI action:
- Query citra Sentinel & Landsat
- Cloud dan shadow masking
- Hitung indeks vegetasi
- Hitung zonal statistik
- Evaluasi valid pixel ratio
- Pilih scene terbaik terbaru

## Final result:
User melihat nilai indeks vegetasi mingguan dengan indikator kualitas.

---

# 7. AI Responsibility Model

AI Role:

* Planner
* Executor
* Generator

## Human Role:
- Upload boundary
- Review hasil monitoring
- Interpretasi kondisi kebun

## AI Boundaries:
- Tidak melakukan prediksi
- Tidak melakukan smoothing
- Tidak melakukan gap filling temporal

## Failure Handling:
Jika tidak ada scene valid:
- gunakan scene terbaru
- flag low quality

---

# 8. Interaction Model

## User Input Type:
- GeoJSON
- Shapefile

## System Feedback:
- Weekly NDVI
- Quality flag
- Valid pixel ratio

## Iteration Loop:
Weekly automated processing

## Completion Condition:
Data mingguan tersimpan per sensor per block

---

# 9. Scope Definition

## In Scope:

* Weekly satellite ingestion
* Cloud masking
* Vegetation index calculation
* Zonal statistics per block
* Quality-aware scene selection
* Multi estate batch processing
* Versioned dataset

## Out of Scope:

* Temporal composite
* Machine learning prediction
* Alert engine
* Trend smoothing
* Anomaly detection

---

# 10. Design Tradeoffs

## Speed vs Quality:
Memilih scene terbaru yang memenuhi kualitas minimum untuk menjaga keseimbangan antara aktualitas dan stabilitas.

## Automation vs Control:
Fully automated weekly pipeline tanpa intervensi manual.

## Flexibility vs Simplicity:
Single dataset dipilih untuk menjaga kesederhanaan UI dan interpretasi.

## Risk:
- Time series noisy saat musim hujan
- Valid pixel rendah pada beberapa minggu
- Perbedaan resolusi sensor

---

# 11. Edge Considerations

## Empty input:
Tidak ada estate → engine skip

## Invalid input:
Geometry invalid → estate dilewati

## User confusion risk:
Perubahan indeks akibat awan

## Misuse:
Interpretasi nilai tanpa melihat quality flag

---

# 12. Success Criteria

## User Success:
Manager dapat melihat kondisi vegetasi mingguan dengan confidence tinggi.

## System Success:
Pipeline berjalan weekly tanpa error untuk multi estate.

## Adoption Signal:
User menggunakan dashboard mingguan untuk monitoring kebun.

---

# 13. Open Questions

1. Threshold valid pixel ratio final
2. Cloud mask method tuning
3. Landsat vs Sentinel weighting

---

# 14. Recommended Next Document

Next Step:

* Create AI Workflow
* Create ARCH
* Define Execution

Reason:
Workflow sudah ditetapkan dan siap diturunkan menjadi arsitektur teknis dan implementasi engine GEE.


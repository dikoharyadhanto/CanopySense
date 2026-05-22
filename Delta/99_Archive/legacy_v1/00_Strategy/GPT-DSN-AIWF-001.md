# GPT Design Doc (AI Workflow)

> [!IMPORTANT]
> Logic depends on GPT-DSN-WORKFLOW-001

# GPT Design Document (AIWF)

## Metadata

Project ID: 001
Product Name: Canopy Sense
Target: AI Workflow
Version: v0.1
File: GPT-DSN-AIWF-001-v0.1.md
Author: ChatGPT (Workflow Consultant)
Date: 2026-03-31

---

# 1. AI Workflow Purpose

Define bagaimana engine membuat keputusan otomatis dalam pemilihan citra mingguan, evaluasi kualitas, dan produksi indeks vegetasi tanpa composite temporal.

Workflow ini menggunakan pendekatan:

Quality-aware Observational Engine (Option B)

AI memilih:

* citra terbaru
* dengan kualitas minimum
* tanpa manipulasi temporal

---

# 2. AI Roles

AI bertindak sebagai:

1. Scene Selector
2. Quality Evaluator
3. Sensor Router
4. Weekly Orchestrator
5. Zonal Statistics Generator
6. Quality Flag Generator

AI tidak bertindak sebagai:

* Predictor
* Smoother
* Composite generator
* Temporal filler

---

# 3. Decision Flow Overview

High-level AI decision flow:

Weekly Trigger
→ Estate Loop
→ Sensor Loop
→ Scene Query
→ Scene Grouping
→ Quality Evaluation
→ Scene Selection
→ Index Calculation
→ Zonal Statistics
→ Quality Flagging
→ Save Output

---

# 4. Weekly Orchestrator Logic

Trigger:

Every Monday
02:00 AM

Processing Window:

Last 7 days

AI melakukan:

1. Load estate list
2. Loop setiap estate
3. Loop setiap sensor
4. Jalankan workflow ekstraksi

---

# 5. Scene Selector Logic

Input:

* sensor
* estate geometry
* date range (7 days)

AI Query:

Sentinel-2 collection
Landsat collection

Output:

List scene kandidat dalam 7 hari

---

# 6. Scene Grouping Logic

Jika terdapat multiple scene pada tanggal sama:

AI melakukan:

Group by acquisition date
→ mosaic spatial

Tujuan:

menghindari tile overlap
menyatukan area estate

---

# 7. Cloud Masking Logic

Sentinel-2:

Remove:

* cloud
* cloud shadow
* cirrus

Landsat:

Remove:

* cloud
* shadow
* snow (optional)

Tidak ada temporal filling.

---

# 8. Quality Evaluator Logic

AI menghitung:

valid_pixel_ratio = valid_pixels / total_pixels

Per block

Quality threshold:

valid_pixel_ratio >= threshold

Jika memenuhi:

scene dianggap valid

Jika tidak:

scene dianggap low quality

---

# 9. Scene Selection Logic (Option B)

Langkah AI:

Filter scene valid

Jika ada:

select newest(valid)

Jika tidak ada:

select newest(all)
low_quality = true

Ini menjaga:

* realism
* kualitas minimum
* konsistensi weekly

---

# 10. Sensor Router Logic

AI memproses sensor secara independen:

Sentinel-2 → 10m
Landsat → 30m

Tidak ada resampling lintas sensor

NDRE:

Sentinel → dihitung
Landsat → null

---

# 11. Vegetation Index Generator

AI menghitung:

NDVI
EVI
NDRE
SAVI
GNDVI

Per pixel

Setelah masking cloud

---

# 12. Zonal Statistics Generator

AI menghitung per block:

mean
std
valid_pixel_ratio

Output satu nilai per block

---

# 13. Quality Flag Generator

AI menentukan:

low_quality = true jika:

valid_pixel_ratio < threshold
atau
scene fallback digunakan

---

# 14. Output Writer Logic

AI menyimpan:

* acquisition_date
* sensor
* block_id
* vegetation indices
* std values
* valid_pixel_ratio
* low_quality flag
* version

Output:

1 row per block per sensor per minggu

---

# 15. Failure Handling

Case 1: tidak ada scene

AI:

skip
create notice

Case 2: semua cloudy

AI:

ambil terbaru
low_quality = true

Case 3: valid pixel kecil

AI:

insert data
low_quality = true

---

# 16. AI Boundaries

AI tidak boleh:

* melakukan composite temporal
* melakukan smoothing
* interpolasi minggu kosong
* melakukan AI prediction
* menggabungkan sensor

AI hanya:

memilih observasi terbaik yang tersedia

---

# 17. Deterministic Behavior

Workflow harus menghasilkan:

Input sama → output sama

Tidak ada randomness

Tidak ada probabilistic selection

---

# 18. AI Workflow Summary

Weekly run
→ query scene
→ mosaic same date
→ cloud mask
→ hitung valid pixel
→ filter quality
→ pilih newest valid
→ compute index
→ zonal stats
→ flag quality
→ save versioned

Ini adalah AI workflow final untuk Core Engine Stage 1.

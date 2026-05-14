# Panduan Director — Delta Ecosystem

Dokumen ini menjelaskan cara mengoperasikan Delta Ecosystem secara benar, dari membuat project baru sampai mengelola eksekusi AI agent. Ditulis untuk Director — yaitu kamu, manusia yang memegang otoritas tertinggi di seluruh sistem ini.

---

## Apa itu Delta Ecosystem?

Delta adalah sistem kerja terstruktur antara kamu (Director) dan beberapa AI agent yang masing-masing punya peran berbeda. Tujuannya satu: mengubah intent kamu menjadi produk nyata dengan cara yang traceable, terstruktur, dan tidak bergantung pada ingatan atau keberuntungan.

Setiap keputusan penting punya dokumen. Setiap AI agent punya role yang jelas. Setiap eksekusi punya audit trail.

### AI Agents dalam Delta

| Agent        | Nama Peran              | Fungsi Utama                                                              |
| ------------ | ----------------------- | ------------------------------------------------------------------------- |
| **GMN**      | Global System Architect | Merancang strategi dan arsitektur tingkat tinggi                          |
| **ANT**      | Technical Foreman       | Menerjemahkan strategi menjadi Work Order + ANT-STR + PDC                 |
| **CDC**      | Lead Developer          | Menulis kode berdasarkan Work Order dari ANT                              |
| **GPT**      | Brutal Auditor          | Mengaudit hasil kerja secara adversarial — tidak terikat Delta governance |
| **PPX**      | Verificator             | Memverifikasi dan melakukan research untuk mendukung keputusan            |
| **Director** | Kamu                    | Pemilik intent, pemberi keputusan akhir, pemegang otoritas konstitusional |

### Hierarki Otoritas

```
DELTA_CONSTITUTION  ← tertinggi, tidak bisa dilanggar tanpa proses formal
      ↓
DIRECTOR_INTENT (DIR-DI)
      ↓
DELTA_PROTOCOL
      ↓
Agent Rule Files (Delta/00_Rules/)
      ↓
STRAT → WO → ANT-STR → IMPL/WALK → DIR-STR → PDC
      ↓
CDC (eksekutor)
```

---

## Rantai Dependensi Dokumen

```
DI new → DI lock (Director audit)
  ↓
STRAT new → complete → lock (Director + GPT + PPX audit)
  ↓
WO new → advance → complete → lock (Director audit)
  ↓
ANT-STR new ─────── (gate: WO harus LOCKED)
  ↓                   ANT menjalankan automated simulation test
ANT-STR advance → complete → lock
  │                   STR lock auto-locks IMPL + WALK
  ↓
IMPL new ────────── (gate: WO LOCKED + ANT-STR exists)
  ↓
WALK new ────────── (gate: WO LOCKED + ANT-STR exists)
  ↓
DIR-STR new ─────── (gate: WO+STR+IMPL+WALK latest LOCKED)
  ↓                   Opsional — tidak memblokir apapun
PDC new → COMPLETE → LOCKED → project end
```

---

## Struktur Folder Project

```
NamaProject/              ← folder project kamu (buat sendiri, lalu cd ke sini)
│
├── project.json          ← identitas project (dikelola CLI)
├── DELTA_README.md       ← panduan ini
├── CLAUDE.md             ← konfigurasi Claude
├── GEMINI.md             ← konfigurasi Gemini
├── AGENTS.md             ← konfigurasi Codex / agent lain
├── DEEPSEEK.md           ← konfigurasi DeepSeek
├── .mcp.json             ← MCP server config
├── .vscode/mcp.json      ← MCP config VS Code
├── .cursor/mcp.json      ← MCP config Cursor
├── .codex/mcp.json       ← MCP config Codex
├── .gitignore
├── .claudesignore
├── ANT-PDC-XXX-v1.0.md   ← PDC (Product Documentation / Product Closure) — WAJIB
│
├── Delta/                ← semua governance Delta (jangan edit manual)
│   ├── DELTA_CONSTITUTION.md
│   ├── DELTA_PROTOCOL.md
│   ├── DELTA-REGISTRY.json
│   ├── progress.json     ← workflow state (dikelola CLI)
│   ├── 00_Rules/         ← rule files tiap agent
│   ├── 01_Strategy/      ← dokumen strategi (DIR-DI, GMN-STRAT)
│   ├── 02_Blueprint/     ← work orders + test reports (ANT-WO, ANT-STR, DIR-STR)
│   ├── 03_Build/         ← implementation logs (CDC-IMPL, CDC-WALK)
│   ├── 07_Logs/          ← session logs (CSO — optional)
│   ├── delta_reference/  ← doctrine docs (jarang dibaca, referensi saja)
│   └── ...
│
└── src/, tests/, dll.    ← kode dan output project yang sebenarnya
```

**Aturan penting:**

- Folder `Delta/` dan isinya **jangan disentuh manual** kecuali kamu tahu apa yang kamu lakukan. CLI yang mengelolanya.
- `progress.json` **jangan diedit manual**. Ini adalah satu-satunya sumber kebenaran untuk workflow state.
- Kode project dan output nyata ada di luar folder `Delta/` — di root folder project.

---

## Delta CLI — Setup

### Install (sekali saja per mesin)

```bash
npm install -g github:dikoharyadhanto/delta-ecosystem
```

### Setup agents dan tools

```bash
delta setup install
```

Wizard ini mendeteksi tool yang terinstall (Claude Code, Antigravity, Codex CLI/App) dan men-deploy role agents / shortcut prompts (`/gmn`, `/ant`, `/cdc`) ke masing-masing tool.

Target utama:

- Claude Code: `~/.claude/commands/`
- Antigravity: `~/.gemini/agents/`
- Codex CLI/App: `~/.codex/skills/`

### Maintenance Ecosystem

```bash
delta setup update
```

Perintah ini menyinkronkan templates, bridge files, dan reference docs ke `~/.delta/`. **Tidak pernah menyentuh** dokumen Strategy/Blueprint/Build — aman dijalankan kapan saja.

### Memory MCP Isolation

`~/.delta/memory_delta.jsonl` hanya untuk Delta ecosystem memory: governance invariant, CLI behavior, path convention, setup facts, role bootstrap, dan environment quirks yang stabil.

Jangan gunakan Memory MCP untuk project-specific memory, product context, implementation detail, atau preferensi umum AI. Context project disimpan di CSO dan governance artifacts. Jika sebuah dokumen punya linked CSO, status command dokumen akan menampilkannya agar AI bisa membuka CSO tanpa Director mengetik path berulang.

### Pola Perintah

```
delta {domain} {action} [--flags]
```

Domain yang tersedia: `project`, `session`, `wo`, `strat`, `str`, `dir-str`, `cso`, `di`, `impl`, `pdc`, `override`, `sync`, `audit`, `setup`, `operation`, `block`, `unblock`, `skill`

---

## Alur Kerja Standar — Dari Nol ke Project Closed

### Langkah 1 — Buat Folder Project dan Inisialisasi

```bash
mkdir NamaProject
cd NamaProject
delta project start
```

CLI otomatis mendeteksi nama project dari nama folder dan memberikan ID project dari global registry. Flag `--name` dan `--id` opsional — CLI akan auto-assign kalau tidak diberikan.

Perintah ini membuat struktur `Delta/` di dalam folder saat ini, meng-copy semua governance documents, dan membuat `project.json` serta `progress.json`.

### Langkah 2 — Bootstrap Session

Setiap kali mulai kerja di project, jalankan ini dulu:

```bash
delta session bootstrap
```

Ini memuat state terakhir project dan memunculkan alert jika ada sesuatu yang perlu perhatianmu — misalnya WO yang masih BLOCKED atau override yang aktif.

### Langkah 3 — Buat Director's Intent (DI)

```bash
delta di new
```

CLI otomatis meng-inject template dan auto-generate nama file. DI adalah fondasi segalanya. Tanpa DI yang jelas, GMN tidak bisa membuat strategi yang benar.

DI harus menjawab:

- Apa yang ingin dicapai?
- Mengapa ini penting?
- Apa batasannya (waktu, budget, teknologi)?
- Bagaimana kamu tahu kalau ini berhasil?

Setelah konten DI selesai, complete dan lock:

```bash
delta di complete   # (jika ada command-nya, atau edit manual lalu)
delta audit record --di <file> --actor Director --approve
delta di lock
```

`delta di lock` adalah **hard gate** — STRAT tidak bisa dibuat sebelum DI di-lock.

### Langkah 4 — Aktifkan GMN untuk Strategy

Di Claude Code, ketik `/gmn`. Di Antigravity, buka agent `gmn`. Di Codex CLI/App, gunakan shortcut skill `/gmn` setelah `delta setup install`. GMN akan otomatis membaca Constitution, Protocol, dan DI kamu, lalu membuat `Delta/01_Strategy/GMN-STRAT-XXX-v1.0.md`.

### Langkah 5 — Audit STRAT dengan Director, GPT, dan PPX

Sebelum STRAT bisa di-lock, tiga pihak harus mencatat audit verdict:

```bash
# Director menyetujui STRAT
delta audit record --strat --actor Director --approve

# GPT melakukan brutal audit (via Codex CLI / ChatGPT dengan AGENTS.md)
delta audit record --strat --actor GPT --approve

# PPX melakukan verifikasi arsitektur (via Perplexity)
delta audit record --strat --actor PPX --approve
```

Cek status audit kapan saja:

```bash
delta audit status --strat <file>
```

### Langkah 6 — Complete & Lock STRAT

```bash
delta strat complete
delta strat lock
```

CLI akan otomatis mengecek ketiga audit record sebelum mengizinkan lock. STRAT yang sudah di-lock tidak bisa diubah tanpa proses formal (`delta strat pivot`).

### Langkah 7 — ANT Membuat Work Order

Di Claude Code, ketik `/ant`. Di Antigravity, buka agent `ant`. Di Codex CLI/App, gunakan shortcut skill `/ant` setelah `delta setup install`. ANT akan membaca STRAT dan membuat `ANT-WO-XXX-v0.1.md`.

```bash
delta wo new
delta wo advance
```

Setelah WO siap, Director mencatat audit lalu mengunci WO:

```bash
delta audit record --wo --actor Director --approve
delta wo complete
delta wo lock
```

### Langkah 8 — ANT Membuat ANT-STR Baseline

```bash
delta str new
delta str advance
```

ANT-STR dibuat setelah WO LOCKED. Ini membuka gate untuk IMPL/WALK, karena CDC tidak boleh mulai tanpa WO LOCKED dan ANT-STR yang sudah ada di versi yang sama.

### Langkah 9 — CDC Eksekusi

Di Claude Code, ketik `/cdc`. Di Codex CLI/App, gunakan shortcut skill `/cdc` setelah `delta setup install`. CDC akan membaca WO dan menyiapkan Pre-Implementation Plan.

```bash
# Setelah CDC menyelesaikan IMPL:
delta impl new
delta impl complete

# Setelah CDC menyelesaikan WALK:
delta impl new --file CDC-WALK-XXX-v0.1.md
delta impl complete
```

> **Gate IMPL/WALK:** WO harus LOCKED dan ANT-STR harus exists (dibuat dulu) di versi yang sama.

### Langkah 10 — ANT Menyelesaikan ANT-STR

```bash
delta str complete           # Test selesai, hasil PASS/FAIL direkam
```

### Langkah 11 — Audit & Lock STR

```bash
# Director mencatat audit ANT-STR
delta audit record --str --actor Director --approve

# Lock ANT-STR — auto-locks IMPL + WALK
delta str lock
```

**Auto-lock cascade:** `delta str lock` otomatis mengunci IMPL dan WALK di versi yang sama (jika statusnya COMPLETE/IMPLEMENTED).

### Langkah 12 — Director Manual Testing (Opsional)

```bash
delta dir-str new
```

DIR-STR hanya bisa dibuat setelah WO + ANT-STR + IMPL + WALK semuanya LOCKED di versi terbaru. Ini opsional — tidak memblokir dokumen apapun.

### Langkah 13 — PDC (Product Documentation / Product Closure) — WAJIB

```bash
delta pdc new
```

PDC adalah **mandatory closure evidence**. Template di-inject ke root project (bukan Delta/). Isi PDC dengan bukti bahwa produk final sesuai dengan DI dan STRAT, lalu jalankan `delta pdc complete` dan minta Director untuk melakukan `delta pdc lock` (membutuhkan audit record).

### Langkah 14 — Tutup Project

```bash
delta project end
```

CLI akan mengecek:

- File PDC exists di root project
- Status PDC sudah LOCKED

Jika valid, project ditutup. Gunakan `delta project end --force` untuk bypass PDC gate.

---

## Mengelola Situasi Tidak Normal

### WO Terlanjur IN_PROGRESS, Tapi Perlu WO Baru

```bash
delta override declare --scope wo_gate --reason "Penjelasan singkat" --expires session
delta wo new
```

Override tercatat di `progress.json` dan berlaku sampai session berakhir.

### WO Stuck / Paused

```bash
delta wo pause --reason "Menunggu keputusan arsitektur dari GMN"
```

Ketika masalah sudah clear, **resume**:

```bash
delta wo resume
```

Ini hanya menunda eksekusi WO: `IN_PROGRESS -> BLOCKED -> IN_PROGRESS`. Gunakan ini untuk pause biasa, bukan untuk quarantine dokumen cacat.

### Cascade Quarantine / Block Berantai

Gunakan `delta block` ketika sebuah dokumen atau chain dokumen dianggap tidak trusted dan harus membekukan operasi downstream.

```bash
delta block --doc strat --v 1.0 --reason "STRAT tidak valid setelah audit Director"
delta block list
```

Efeknya berantai: jika dokumen upstream di-block, operasi mutation pada dokumen downstream yang terdampak harus gagal. Status lifecycle asli tidak ditimpa; block adalah marker terpisah.

Unblock hanya dilakukan oleh Director/admin:

```bash
delta unblock --id BLK-...
# atau deliberate bulk action:
delta unblock
```

`delta unblock` tidak otomatis meng-approve atau meng-lock dokumen. Setelah unblock, dokumen tetap harus melewati gate normal.

### External Skill Repository

Skill dari GitHub repo orang lain tidak diedit langsung. Delta menyimpan metadata global di `~/.delta/skills/` melalui manifest dan lock file. Dokumen project hanya mereferensikan skill ID di STRAT allowlist dan WO binding.

```bash
delta skill add <github-url>
delta skill pin <skill-id> <commit>
delta skill update <skill-id>
delta skill validate
delta skill list
```

`delta skill add` hanya membuat manifest `staged`; tidak mengaktifkan skill. Aktivasi runtime tetap wajib melewati triple-gate:

```text
authorized_skills = routing_candidates ∩ STRAT_skill_allowlist ∩ WO_skill_binding
```

Jika skill terdeteksi oleh `~/.delta/skills/SKILLS_ROUTING.json` tetapi tidak ada di STRAT allowlist atau WO binding, statusnya `NOT_AUTHORIZED` dan tidak boleh di-load.

### STRAT Ternyata Salah di Tengah Eksekusi

Ada dua jenis **STRAT_INVALIDATION**:

- **SOFT** — CDC menemukan hambatan kecil, bisa diselesaikan lokal tanpa ubah STRAT.
- **HARD** — CDC menemukan kontradiksi fundamental. CDC raise flag ke ANT → ANT eskalasi ke GMN → GMN revisi STRAT.

```bash
delta strat pivot         # unlock STRAT untuk revisi
# ... GMN revisi STRAT ...
delta strat lock
```

### Resume Project yang Sudah Ditutup

```bash
cd NamaProject
delta project start
```

Semua state di `Delta/progress.json` tetap tersimpan — tidak ada yang hilang.

---

## Dokumen yang Akan Kamu Buat Sendiri

### DIR-DI (Director's Intent)

```bash
delta di new
```

Ini adalah satu-satunya dokumen yang murni milikmu. Isi: intent, nilai, batasan, dan definisi sukses. CLI akan auto-inject template.

### DIR-STR (Director Manual Testing)

```bash
delta dir-str new
```

Gate: WO + ANT-STR + IMPL + WALK harus LOCKED di versi terbaru. Opsional — buat ketika kamu ingin melakukan manual testing sendiri terhadap hasil CDC. Tidak memblokir dokumen apapun.

### PDC (Product Documentation / Product Closure)

```bash
delta pdc new
```

**Mandatory.** Version-coupled ke STRAT atau DI yang terkunci. Template di-inject ke root project. Isi dengan bukti closure, complete dan lock via CLI, lalu jalankan `delta project end`.

---

## GPT — Cara Menggunakannya

GPT adalah **external auditor**, tidak terikat Delta governance.

1. Arahkan GPT ke file yang mau di-audit: *"baca Delta/01_Strategy/GMN-STRAT-XXX-v1.0.md dan audit secara adversarial"*

2. GPT memberikan analisis dan verdict

3. Kamu (Director) mencatat verdict GPT via CLI:
   
   ```bash
   delta audit record --strat --actor GPT --approve
   # atau jika conditional:
   delta audit record --strat --actor GPT --conditional --conditions-open --note "Masalah X perlu diselesaikan"
   ```

**Yang perlu diingat:**

- GPT boleh membaca file Delta langsung via file path
- GPT tidak menulis ke file manapun — Director yang menjalankan `delta audit record`
- GPT juga tidak menjalankan CLI — semua perintah CLI dijalankan oleh Director
- Kalau GPT tidak menemukan masalah serius, minta dia audit lebih keras
- Verdict GPT dicatat sebagai immutable audit record di `progress.json`
- GPT juga bisa mengaudit PDC saat project closure — minta dia baca file PDC di root

---

## Director Override vs Constitutional Deviation

### Director Override (Protocol-level)

Bypass aturan operasional di `Delta/DELTA_PROTOCOL.md`:

```bash
delta override declare --scope wo_gate --reason "..." --expires session
delta override list
delta override revoke --id OVR-20260509-XXXXXX
```

**Catatan:** `delta override declare` sekarang membutuhkan **akses Administrator**. Buka terminal sebagai Administrator untuk menjalankannya. AI akan membimbing Director dengan command yang tepat jika fitur ini diperlukan.

Scope yang tersedia: `wo_gate`, `strat_gate`, `audit_gate`, `document_order`, `agent_boundary`, `project_closed`

### Temporary Experimental Authorization / TEA (Constitutional-level)

Digunakan saat bertentangan dengan `Delta/DELTA_CONSTITUTION.md`. Jauh lebih jarang — refer ke Constitution Article VIII.

---

## Menjaga Kesehatan Ecosystem

```bash
delta sync registry        # validasi DELTA-REGISTRY.json
delta audit session        # full state overview (workflow + dokumen + audit)
delta audit list           # semua audit records
delta audit status --wo ... # cek status audit untuk artifact tertentu
delta project status       # identitas dan status project
delta project list         # lihat semua project di global registry
delta project refresh      # validasi registry terhadap filesystem
delta wo status            # WO aktif sekarang
delta wo list              # semua WO terdaftar
delta str list             # semua STR terdaftar
delta cso list             # semua CSO terdaftar (jika ada)
delta pdc status           # status PDC saat ini
delta override list        # semua overrides
delta setup update         # sync templates, bridge files, reference docs
delta skill validate       # validasi manifest dan lock skill
delta skill list           # lihat skill registry
delta block list           # lihat active/resolved cascade blocks
```

---

## Referensi Cepat — Semua Perintah CLI

```bash
# Setup (sekali per mesin)
npm install -g github:dikoharyadhanto/delta-ecosystem
delta setup install

# Mulai project baru
mkdir NamaProject && cd NamaProject
delta project start

# Tiap kali mulai kerja
delta session bootstrap

# Aktifkan role di Claude Code / Codex shortcut
/gmn    /ant    /cdc

# ── DI lifecycle ──
delta di new                                # inject template
delta di lock                               # lock DI (gate: complete + Director audit)

# ── STRAT lifecycle ──
delta strat new                             # inject template (gate: DI locked)
delta strat complete
delta audit record --strat --actor Director --approve
delta audit record --strat --actor GPT --approve
delta audit record --strat --actor PPX --approve
delta strat lock                            # gate cek ketiga verdict
delta strat pivot                           # unlock untuk revisi

# ── WO lifecycle ──
delta wo new                                # inject template (gate: STRAT locked)
delta wo advance                            # PENDING → IN_PROGRESS
delta audit record --wo --actor Director --approve
delta wo complete                           # IN_PROGRESS → COMPLETE
delta wo lock                               # gate: COMPLETE + STRAT locked + Director audit
delta wo pause --reason "..."               # IN_PROGRESS → BLOCKED
delta wo resume                             # BLOCKED → IN_PROGRESS
delta wo supersede --new-file ANT-WO-XXX-v0.2.md

# ── ANT-STR lifecycle ──
delta str new                               # inject template (gate: WO LOCKED)
delta str advance                           # PENDING → IN_PROGRESS (ANT running tests)
delta str complete                          # IN_PROGRESS → COMPLETE (tests executed)
delta audit record --str --actor Director --approve
delta str lock                              # gate: COMPLETE + audit → auto-locks IMPL+WALK

# ── DIR-STR lifecycle ──
delta dir-str new                           # inject template (gate: WO+STR+IMPL+WALK latest LOCKED)
delta dir-str advance                       # PENDING → IN_PROGRESS
delta dir-str complete                      # IN_PROGRESS → COMPLETE
delta dir-str lock                          # gate: COMPLETE + audit

# ── IMPL/WALK lifecycle ──
delta impl new                              # inject IMPL template (gate: WO locked + STR exists)
delta impl new --file CDC-WALK-XXX-v0.1.md  # auto-detect WALK → WALK template
delta impl complete

# ── PDC lifecycle ──
delta pdc new                               # inject template ke root project
delta pdc complete                          # DRAFT → COMPLETE
delta pdc lock                              # gate: COMPLETE + Director audit
delta pdc status                            # cek status PDC

# ── Audit records ──
delta audit record --wo --actor Director --approve    # auto-target active WO
delta audit record --strat --actor Director --approve # auto-target active STRAT
delta audit record --di --actor Director --approve    # auto-target active DI
delta audit list                            # semua audit records
delta audit status --wo <file>              # status audit per artifact
delta audit resolve --wo ... --actor GPT    # OPEN → RESOLVED
delta audit waive --wo ... --actor GPT      # OPEN → WAIVED_BY_DIRECTOR
delta audit session                         # full state overview

# ── CSO (Cognitive State Objects — optional) ──
delta cso new --agent GPT                  # standalone CSO
delta cso new --agent ANT --wo             # auto-link ke active WO
delta cso complete --latest
delta cso lock --latest
delta cso status --latest
delta cso link --latest --wo
delta cso unlink --latest --wo
delta cso list

# ── Override ──
delta override declare --scope wo_gate --reason "..." --expires session
delta override declare --scope audit_gate --reason "..." --expires session
delta override list
delta override revoke --id OVR-...

# ── Cascade quarantine ──
delta block --doc strat --v 1.0 --reason "..."
delta block --doc wo --v 0.1 --reason "..."
delta block list
delta unblock --id BLK-...
delta unblock                              # deliberate bulk unblock

# ── Skill registry ──
delta skill validate
delta skill add <github-url>
delta skill pin <skill-id> <commit>
delta skill update <skill-id>
delta skill list

# ── Maintenance ──
delta setup update                          # sync templates + bridge + references
delta sync registry                         # validasi DELTA-REGISTRY.json
delta project status                        # status project saat ini
delta project list                          # semua project di global registry
delta project refresh                       # validasi registry vs filesystem
delta project archive --id 001              # arsipkan project
delta wo status
delta wo list

# ── Tutup ──
delta session close
delta project end                           # gate: PDC exists + LOCKED
```

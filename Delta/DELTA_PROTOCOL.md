# Delta Ecosystem

## Constitutional Subordination

> [!IMPORTANT]
> This document is subordinate to the Delta Constitution, which defines the supreme authority, hierarchy, and invariant principles of the Delta Ecosystem. This document governs operational execution, workflow standards, and governance procedures. In any conflict between this document and the Delta Constitution, the Delta Constitution prevails.

---

## Overview

**Delta** is an integrated, document-driven AI ecosystem designed for systematic product development and project execution. The ecosystem comprises six specialized AI agents, each with distinct roles and responsibilities, coordinated under the strategic direction of the **Director: Diko Hary Adhanto**.

> [!IMPORTANT]
> **Director's Override Protocol**: The Director holds ultimate authority over all decisions within the Delta Ecosystem as established in the Delta Constitution. While the Delta Protocol defines the default structure, roles, and execution pathways, it is not intended to constrain real-world judgment or operational flexibility. In situations where strict adherence introduces unnecessary friction, inefficiency, or misalignment with actual conditions, the Director may intentionally deviate from the protocol. Such deviations are permitted as part of adaptive execution, but must be explicitly acknowledged as a `DIRECTOR_OVERRIDE` event, including a brief rationale and accepted trade-offs. This ensures that flexibility does not degrade system integrity, preserving traceability, clarity of intent, and the ability to reconstruct decision logic over time.

## System Architecture

The Delta ecosystem operates across four operational layers:

1. **Strategy Layer** — High-level strategic planning and vision
2. **Planning Layer** — Technical decomposition and work formulation
3. **Implementation Layer** — Code development and execution
4. **Quality Assurance Layer** — Validation, verification, and continuous improvement

---

## Project Folder Structure

### Standard Project Root Folder Format

The project root folder is created by the Director before running `delta project start`. The recommended naming convention is:

```
{PROJECT_ID}_{Project_Name}/
```

**Example:** `002_CanopySense`, `001_DataPipeline`, `003_CloudInfra`

This convention is recommended for consistency but not enforced by the CLI. The Director may use any valid folder name.

### Two-Layer Separation Principle

Every Delta project separates its contents into two distinct layers:

- **Delta layer** (`Delta/`) — all Delta ecosystem governance files: doctrine documents, agent rules, strategy/planning/implementation documents, skills, logs, and runtime state. This layer is owned by the Delta ecosystem and must not be mixed with project work.
- **Project layer** (root-level folders) — all actual project work: source code, tests, builds, assets, and project-specific outputs. This layer is owned by the project team.
- **Bridge files** (root-level) — `project.json`, `DELTA_README.md`, `CLAUDE.md`, `GEMINI.md`, `AGENTS.md`, `.gitignore`, `.claudesignore` — files that apply to both layers and must be discoverable at the root.

> **Why CLAUDE.md and GEMINI.md stay at root:** AI model configuration files must be discoverable from the project working directory. If placed inside `Delta/`, they would not be auto-loaded by AI hosts (Claude Code, Gemini) that scan from the project root. These files reference Delta governance paths explicitly.

### Mandatory Folder & File Structure

```
NamaProject/                            # Created by Director; cd into this, then run delta project start
│
├── project.json                        # Project identity (CLI-managed — DO NOT EDIT MANUALLY)
├── DELTA_README.md                     # Director guidance & quick reference
├── CLAUDE.md                           # Claude Code rules & context (root for discoverability)
├── GEMINI.md                           # Gemini rules & context (root for discoverability)
├── AGENTS.md                           # Codex / external agent config
├── .gitignore                          # Git ignore patterns
├── .claudesignore                      # Claude Code ignore patterns
├── PDC — Product Documentation / Product Closure (MANDATORY closure evidence)
│
├── Delta/                              # Delta governance layer (CLI-managed)
│   │
│   ├── DELTA_CONSTITUTION.md           # Constitutional charter (supreme SSoT) — READ EVERY SESSION
│   ├── DELTA_PROTOCOL.md               # Operational governance (SSoT) — READ EVERY SESSION
│   ├── DELTA-REGISTRY.json             # Semantic Governance Registry (CLI-validated)
│   ├── progress.json                   # Runtime workflow state (CLI-managed — DO NOT EDIT MANUALLY)
│   │
│   ├── 00_Rules/                       # Agent-specific rules — READ EVERY SESSION
│   │   ├── ANT-RULE.md
│   │   ├── CDC-RULE.md
│   │   └── GMN-RULE.md
│   │
│   ├── 01_Strategy/                    # Strategy-layer documents
│   │   ├── DIR-DI-{ID}-v1.0.md
│   │   └── GMN-STRAT-{ID}-v1.0.md
│   │
│   ├── 02_Blueprint/                   # Planning-layer documents
│   │   ├── ANT-WO-{ID}-v0.1.md
│   │   ├── ANT-STR-{ID}-v0.1.md
│   │   └── DIR-STR-{ID}-v0.1.md
│   │
│   ├── 03_Build/                       # Implementation-layer documents
│   │   ├── CDC-IMPL-{ID}-v0.1.md
│   │   └── CDC-WALK-{ID}-v0.1.md
│   │
│   ├── 05_References/                  # Reference materials
│   ├── 06_Knowledge/                   # NLM knowledge modules
│   │   └── NLM-{TOPIC}.md
│   │
│   ├── 07_Logs/                        # CSO session logs
│   │   └── CSO-{AGENT}-{YYYYMMDD-HHMMSS}.md
│   │
│   ├── 08_Test/                        # Testing simulation space
│   ├── 99_Docs/                        # Supporting documentation
│   │
│   └── delta_reference/                # On-demand doctrine docs (NOT read every session)
│       ├── DELTA-MEMORY-DOCTRINE.md
│       ├── DELTA-REGISTRY-DOCTRINE.md
│       ├── DELTA-TRANSIENT-COGNITION.md
│       ├── DELTA-LIFECYCLE-RETENTION.md
│       ├── DELTA-LOG-REFERENCE.md
│       ├── DELTA-CLI-ARCHITECTURE.md
│       ├── DELTA-RUNTIME-SCHEMA.md
│       ├── DELTA-OPERATION-REGISTRY-SCHEMA.md
│       └── DELTA-CONSTITUTIONAL-SYNC.md
│
└── [Project Work Folders]/             # Actual project implementation
    ├── src/
    ├── tests/
    └── (other project-specific content)
```

### Path Reference Convention

All agent rule files and governance documents reference paths **relative to the `Delta/` folder**. When agents are working within the Delta ecosystem context, `01_Strategy/`, `02_Blueprint/`, `03_Build/` etc. are resolved relative to `Delta/`. When referencing from the project root, prefix with `Delta/` (e.g., `Delta/01_Strategy/`).

### Inheritance & Initialization

**When creating a new project** — use the Delta CLI:

```bash
mkdir NamaProject
cd NamaProject
delta project start
```

The CLI automatically:

1. Creates `Delta/` subfolder in the current directory and copies the full governance layer:
   - Core files: `DELTA_CONSTITUTION.md`, `DELTA_PROTOCOL.md`, `DELTA-REGISTRY.json`
   - All numbered folders: `00_Rules/` through `99_Docs/` and `delta_reference/`
   - Initializes `Delta/progress.json` (CLI-managed state — do not edit manually)

2. Copies bridge files to project root:
   - `CLAUDE.md`, `GEMINI.md`, `AGENTS.md`, `DELTA_README.md`
   - Generates `.gitignore`, `.claudesignore`, `README.md`
   - Creates `project.json` (CLI-managed — do not edit manually)

**Preserve DELTA_CONSTITUTION.md and DELTA_PROTOCOL.md:**
- Do NOT modify either document in `Delta/` project folders
- They remain the constitutional and operational SSoT across all projects
- Project-specific variations go in `Delta/00_Rules/` or root `CLAUDE.md`/`GEMINI.md`

### Folder & File Ownership & Responsibilities

| Item | Location | Owner | Modification |
| ---- | -------- | ----- | ------------ |
| `project.json` | Project root | CLI (Director) | CLI-managed; Director-owned |
| `README.md` | Project root | Project Owner | Customize per project |
| `CLAUDE.md` | Project root | System Admin (Director) | Customize per project |
| `GEMINI.md` | Project root | System Admin (Director) | Customize per project |
| `.gitignore` / `.claudesignore` | Project root | System Admin (Director) | Director only |
| `Delta/DELTA_CONSTITUTION.md` | Delta layer | System Admin (Director) | Director only — unmodified copy |
| `Delta/DELTA_PROTOCOL.md` | Delta layer | System Admin (Director) | Director only — unmodified copy |
| `Delta/delta_reference/` | Delta layer | System Admin (Director) | Read-only reference — never modified in project |
| `Delta/DELTA-REGISTRY.json` | Delta layer | CLI (Director) | CLI-validated via `delta sync registry` |
| `Delta/progress.json` | Delta layer | CLI only | **CLI-managed — NEVER manually edited** |
| `Delta/00_Rules/` | Delta layer | System Admin (Director) | Director only |
| `Delta/01_Strategy/` | Delta layer | System Admin (Director) | Director only (templates) |
| `Delta/02_Blueprint/` | Delta layer | ANT | Per document governance rules |
| `Delta/03_Build/` | Delta layer | CDC | Per document governance rules |
| `Delta/05_References/` | Delta layer | Project Team | Add/update as needed |
| `Delta/06_Knowledge/` | Delta layer | NLM / Director | NLM on Director request |
| `Delta/99_Docs/` | Delta layer | Project Team | Add/update as needed |
| Project Work Folders | Project layer | Project Team | Full control |

---

## AI Agents & Roles

### GMN — Global System Architect

**Primary Function:** Strategic architecture, product strategy design, and executive consultation

**Core Responsibilities:**

- Consult and strategize with Director to define product/project strategy
- Design strategic roadmaps and system architecture
- Maintain organizational coherence and strategic alignment

**Input Requirements:**

- DI Document (Director's Intent) — must be provided by Director before strategy formulation

**Key Deliverables:**

- STRAT Document (Project Strategy)

**Constraints:**

- The STRAT document must strictly align with DI (Director's Intent)
- STRAT requires audit records with satisfied verdicts from Director, GPT, and PPX before `delta strat lock`
- Lock gate enforces: all three approvers must have `APPROVED` or resolved/waived `CONDITIONAL_APPROVAL` verdicts recorded via `delta audit record`
- WO and STR lock gates require at minimum Director audit verdict (additional approvers per policy)

**Output Format:** Markdown (.md)

---

### GPT — Brutal Auditor

**Primary Function:** Critical quality assurance and strategic challenge

**Core Responsibilities:**

- Conduct brutal, objective audits across all strategic and technical layers
- Identify inconsistencies, risks, and logical gaps
- Challenge assumptions and strategy validity

**Audit Scope:**

- Strategy Documents (DIR-DI, GMN-STRAT)
- Technical Documents (WO, STR, IMPL, WALK)
- Post-Production Documents (product documentation, source code)

**Key Deliverables:** Audit verdicts recorded via `delta audit record` against strategy and technical artifacts. Verdicts are stored as immutable governance evidence in `progress.json`.

**Output Format:** Markdown (.md)

---

### PPX — Verificator & Researcher

**Primary Function:** Verification, validation, and research-backed documentation

**Core Responsibilities:**

- Verify correctness and feasibility of strategy and technical documents
- Conduct research to support or challenge design decisions
- Ensure coherence between planning and execution

**Verification Scope:**

- Strategy Documents (DIR-DI, GMN-STRAT)
- Technical Documents (WO, STR, IMPL, WALK)
- Post-Production Documents (product documentation, source code)

**Key Deliverables:** Conversational verification feedback (No formal research documents are produced for simplicity)

**Output Format:** Markdown (.md)

---

### ANT — Technical Foreman & QA Controller

**Primary Function:** Work order formulation, testing strategy, documentation, and technical governance

**Core Responsibilities:**

- Formulate Work Orders (WO) aligned with strategy documents
- Design Software Test Reports (STR) based on implementation requirements
- Validate alignment between planning and strategy
- Approve technical implementation documentation
- Produce PDC (Product Documentation / Product Closure) — mandatory closure evidence required before project closure

**Key Deliverables:**

- **WO** — Work Order (technical specification & task breakdown)
- **ANT-STR** — Automated Simulation Test Report (validates CDC implementation code; gate: WO locked)
- **DIR-STR** — Director Manual Testing Report (optional; gate: WO+ANT-STR+IMPL+WALK latest locked)
- **PDC** — Product Documentation / Product Closure (MANDATORY closure evidence; version-coupled to STRAT/DI; locked prior to project end)

**Constraints:**

- **WO Creation:** Requires STRAT locked. WO lock requires Director audit verdict.
- **ANT-STR Creation:** Requires WO locked. ANT-STR is the automated simulation test report validating CDC implementation.
- **ANT-STR Lock Cascade:** Locking ANT-STR auto-locks IMPL and WALK at the same version (if COMPLETE/IMPLEMENTED).
- **IMPL & WALK Creation:** Require WO locked + ANT-STR exists at same version. Both require ANT or Director approval before finalization.
- **PDC Creation:** Mandatory closure evidence. Created via `delta pdc new`. Must exist at project root with LOCKED status before `delta project end` can succeed. Version-coupled to locked STRAT or DI version. PDC locked via `delta pdc lock` after Director approval.
- **Iterative Versioning:** For WO/ANT-STR versions beyond v1.0, prior baseline version must have WO+STRAT+IMPL+WALK in COMPLETE state. If immediate previous version is PENDING, validate against older completed version.

**Output Format:** Markdown (.md)

---

### CDC — Lead Developer & Autonomous Execution Engine

**Primary Function:** Code implementation and technical execution

**Core Responsibilities:**

- Execute heavy-duty code implementation aligned with work orders
- Create Pre-Implementation Plans documenting technical approach
- Generate Implementation Reports documenting execution and results
- Incorporate ANT/Director feedback into implementation cycle

**Key Deliverables:**

- **IMPL** — Pre-Implementation Plan (technical approach & architecture)
- **WALK** — Implementation Report (execution summary & technical details)

**Constraints:**

- Both IMPL and WALK documents require ANT or Director review and approval
- Implementation scope must strictly adhere to approved WO documents

**Output Format:** Markdown (.md)

---

### NLM — Ecosystem Knowledge Constructor

**Primary Function:** Research, synthesize, and maintain ecosystem-level knowledge modules from authoritative external sources

**Core Responsibilities:**

- Research official documentation, technical forums, academic papers, and trusted sources for specified technical domains
- Synthesize findings into structured, standardized Knowledge Modules (KNOW)
- Maintain knowledge currency by updating modules when technologies or standards change
- Provide grounded reference knowledge that reduces hallucination and error risk across all agents

**Independence Principle:**

NLM operates in complete isolation from project-specific context. It has no access to strategy documents, work orders, implementation details, or any Delta project documents. NLM works as a Q&A research tool — Director loads relevant sources using keywords, then asks Critical Questions one by one.

**How NLM Works:**

1. GMN or ANT submits a structured NLM Knowledge Request to Director containing Keywords and Critical Questions
2. Director loads sources into NLM using the provided Keywords via NLM's search/source feature
3. Director asks each Critical Question to NLM individually
4. Director saves each NLM response as a separate MD file in a topic subfolder under `06_Knowledge/`
5. GMN or GPT compiles all raw MD files into the final `NLM-{TOPIC}.md` using the compilation template

**Input Requirements:**

- Keywords for source loading — provided by GMN or ANT, executed by Director in NLM
- Critical Questions — provided by GMN or ANT, asked by Director one by one
- NLM does not receive the compilation template — template is used by GMN or GPT after raw files are collected

**Trigger Conditions:**

- STRAT introduces a complex, uncommon, or deep-knowledge architecture domain (e.g., Remote Sensing, Cyber Security, PostGIS, ML pipelines) — optional, not obligatory
- GMN or ANT identifies a knowledge gap and requests NLM activation via Director
- Request chain: GMN or ANT → Director → NLM → raw MD files → GMN or GPT compiles

**Key Deliverables:**

- **Raw MD files** — individual NLM responses per Critical Question (staged in topic subfolder)
- **KNOW** — final compiled Knowledge Module assembled by GMN or GPT from raw files

**Constraints:**

- NLM does not receive or reference any Delta project documents
- All NLM requests must be routed through Director — agents cannot directly instruct NLM
- KNOW documents are ecosystem-level assets, not project-specific
- KNOW documents are living documents — updated in place, not versioned per audit trail rules
- Raw MD files are staging artifacts — kept for traceability but not the final deliverable

**Output Format:** Markdown (.md) — raw files in `06_Knowledge/{TOPIC_FOLDER}/`, compiled final in `06_Knowledge/`

---

### Director (User) — Strategic Vision & Quality Assurance

**Primary Function:** Strategic intent definition and manual quality validation

**Core Responsibilities:**

- Define strategic vision, values, intention, and reasoning for product/project
- Provide Director's Intent (DI) document as input to strategy formulation
- Conduct manual testing and validation of implementation
- Final decision authority for all approvals across ecosystem

**Key Deliverables:**

- **DIR-DI** — Director's Intent (strategic vision, values, intention, reasoning, product/project scope)
- **DIR-STR** — Director Manual Testing (manual testing report & validation findings)

**Constraints:**

- DIR-DI document must be completed and provided before GMN begins strategy formulation
- DIR-STR is optional per version; created on-demand when Director conducts manual testing
- DIR-STR requires CDC (IMPL, WALK) and ANT (WO, STR) documents to be in Completed/Implemented status
- DIR-STR typically created at: mid-version checkpoints, near-final versions, or Director-initiated testing moments

**Output Format:** Markdown (.md)

---

## Document Flow & Dependencies

```
ECOSYSTEM KNOWLEDGE LAYER (NLM — fully independent)
└── KNOW (Knowledge Modules) — stored in 06_Knowledge/
    └── Available to all agents as reference throughout all phases

DIRECTOR LEVEL
└── DI (Director's Intent) — manually created
    └── ↓ delta di lock (Director audit)

STRATEGY LAYER (GMN)
├── STRAT (created by GMN, aligned with locked DI)
├── ↓ (audit records: Director + GPT + PPX)
├── ↓ delta strat lock (gate checks all three verdicts)
│
PLANNING LAYER (ANT)
├── WO formulated from locked STRAT
├── ↓ delta wo lock (Director audit)
├── ANT-STR (automated simulation tests) — gate: WO locked
│   └── Created before IMPL/WALK so CDC has a same-version test contract
│   └── PENDING → IN_PROGRESS (ANT runs tests) → COMPLETE → LOCKED
│   └── STR lock auto-locks IMPL + WALK at same version
│
IMPLEMENTATION LAYER (CDC)
├── IMPL — gate: WO locked + ANT-STR exists at same version
├── WALK — gate: WO locked + ANT-STR exists at same version
│
DOCUMENTATION & QUALITY ASSURANCE LAYER
├── DIR-STR (Director Manual Testing) — optional
│   └── Gate: WO + ANT-STR + IMPL + WALK latest LOCKED
│   └── Does not gate WO, STR, IMPL, WALK, or PDC
├── PDC (Product Documentation / Product Closure) — MANDATORY
│   └── Hard-gate: `delta project end` rejected if PDC is missing or not LOCKED
│   └── PDC locked via delta pdc lock after Director approval
└── Final validation and documentation closure
```

---

## Workflow Sequence & Document Dependency Chain

```
DI new → DI lock (Director audit)
  ↓
STRAT new → complete → lock (Director + GPT + PPX audit)
  ↓
WO new → advance → complete → lock (Director audit)
  ↓
ANT-STR new ─────── (gate: WO must be LOCKED; creates same-version test contract)
  ↓
IMPL new ────────── (gate: WO LOCKED + ANT-STR exists)
  ↓
WALK new ────────── (gate: WO LOCKED + ANT-STR exists)
  ↓
ANT-STR advance → complete → lock
  │                   STR lock → auto-locks IMPL + WALK at same version
  ↓
DIR-STR new ─────── (gate: WO + STR + IMPL + WALK latest LOCKED)
  ↓                   Optional Director manual testing — does not gate anything
PDC new → COMPLETE → LOCKED → project end
```

### Detailed Sequence

1. **Director** creates DI (`delta di new`), completes content, locks DI (`delta di lock` — requires Director audit verdict)
2. **GMN** creates STRAT (`delta strat new` — gate: DI locked), completes content, locks STRAT (`delta strat lock` — gate: Director + GPT + PPX audit verdicts)
3. **ANT** creates WO (`delta wo new` — gate: STRAT locked), advances, completes, locks WO (`delta wo lock` — gate: Director audit)
4. **ANT** creates ANT-STR (`delta str new` — gate: WO locked). ANT-STR establishes the same-version automated simulation contract CDC must satisfy.
5. **CDC** creates IMPL (`delta impl new` — gate: WO locked + ANT-STR exists at same version), completes implementation plan.
6. **CDC** creates WALK (`delta walk new` — gate: WO locked + ANT-STR exists at same version), completes walkthrough after execution.
7. **ANT** executes and locks ANT-STR (`delta str advance` → `delta str complete` → `delta str lock` — gate: COMPLETE + audit policy). **Auto-lock cascade**: STR lock auto-locks IMPL and WALK at the same version (if they are COMPLETE/IMPLEMENTED).
8. **Director** (optional) creates DIR-STR (`delta dir-str new` — gate: WO + STR + IMPL + WALK all LOCKED at latest version). DIR-STR is the Director's manual testing report. It is optional and does not gate WO, STR, IMPL, WALK, or PDC creation.
9. **ANT** creates PDC (`delta pdc new` — gate: STRAT or DI locked; version-coupled). PDC is mandatory closure evidence.
10. **ANT** completes and locks PDC (`delta pdc complete` -> `delta pdc lock` — gate: Director approval). **Director** runs `delta project end` — hard gate: PDC must exist at root with LOCKED status.
   5a. **NLM** (optional/on-demand): If STRAT introduces a complex or uncommon technical domain, GMN or ANT submits a structured NLM Knowledge Request to Director.

---

## Document Types & Purposes

| Document | Owner    | Purpose                                           | Layer          | Approval     | Gate for `new` |
| -------- | -------- | ------------------------------------------------- | -------------- | ------------ | -------------- |
| DI       | Director | Director's intent, vision, values, reason         | Pre-Strategy   | Director | — |
| STRAT    | GMN      | Project strategy & execution control system       | Strategy       | Director + GPT + PPX (audit records) | DI locked |
| WO       | ANT      | Work order & technical specification              | Planning       | Director | STRAT locked |
| ANT-STR  | ANT      | Automated simulation test report (validates CDC code) | Planning   | Director | WO locked |
| IMPL     | CDC      | Pre-implementation technical plan                 | Implementation | ANT/Director | WO locked + ANT-STR exists |
| WALK     | CDC      | Implementation report & execution summary         | Implementation | ANT/Director | WO locked + ANT-STR exists |
| DIR-STR  | Director | Director manual testing report (optional)         | Quality        | Director | WO+STR+IMPL+WALK latest locked |
| PDC      | ANT      | Product Documentation / Product Closure (mandatory) | Documentation | Director | STRAT or DI locked |
| KNOW     | NLM      | Ecosystem knowledge module for a technical domain | Ecosystem      | — | — |
| CSO      | All      | Cognitive State Object (session handoff/caching)  | Logging        | — | — |

---

## Coordination Model

- **Director (DIR)** defines strategic intent (DI) and serves as final decision authority across all layers; conducts optional manual testing; routes all NLM requests from agents
- **GMN** maintains strategic coherence and aligns all strategy documents with Director's Intent; may request NLM knowledge modules via Director
- **GPT** conducts independent risk audits and quality assessment
- **PPX** conducts independent architectural verification and research validation
- **ANT** ensures alignment between planning and strategy; creates WO and ANT-STR; authors mandatory PDC closure evidence; approves technical implementation; may request NLM knowledge modules via Director
- **CDC** focuses on autonomous, high-quality execution aligned with approved strategy
- **NLM** operates as an independent ecosystem knowledge layer; constructs and maintains KNOW documents from authoritative external sources; has no access to project documents; all requests routed through Director

## AI-to-AI Orchestration & Cognitive State Objects (CSO)

Formal document handoffs between agents (e.g., ANT to CDC, CDC to ANT) should maintain strict metadata tracking and standardized file output across the ecosystem. Ad-hoc queries can use standard chat modes.

To prevent context window bloat and ensure zero-loss handoffs across sessions, agents may utilize the **CSO (Cognitive State Object)**. CSO is an optional context artifact — not every session produces one. When created, the CSO captures the explicit intent, cognitive reasoning, adversarial tension, and exact state of a conversation at a specific point in time, allowing a new session to resume perfectly without loading all previous chat history.

## Document Standardization & Naming Convention

### File Naming Format

All documents must follow the standardized naming convention:

```
{AGENT_CODE}-{DOCUMENT_CODE}-{PROJECT_ID}-{VERSION}
```

**Components:**

- **AGENT_CODE:** AI model or Director code (DIR, GMN, GPT, PPX, ANT, CDC)
- **DOCUMENT_CODE:** Document type code (DI, STRAT, WO, STR, IMPL, WALK, CSO)
- **PROJECT_ID:** Numeric project identifier (e.g., 002)
- **VERSION:** Semantic version (v1.0, v0.1, v0.2, etc.)

**Examples:**

- `DIR-DI-002-v1.0` — Director's Intent document for Project 002, version 1.0
- `GMN-STRAT-002-v1.0` — Project strategy document for Project 002, version 1.0
- `ANT-STR-002-v0.2` — Software test report for Project 002, version 0.2

---

### Version Management Rules

#### Tier 1: Major Version Documents (v1.0, v2.0, v3.0...)

**Scope:** STRAT, DI, and Product Documentation

**Characteristics:**

- Start at **v1.0** (first major version)
- Each new version represents significant strategic or product changes
- All documents in this tier must maintain **synchronized versions**
- Single document per tier per version (overwrites/updates in place)

**Constraint:** Other documents cannot equal or exceed these versions (e.g., if STRAT is v1.5, other docs max out at v1.4)

#### Tier 2: Minor Version Documents (v0.1, v0.2, v0.3...)

**Scope:** WO, STR, IMPL, WALK

**Characteristics:**

- Start at **v0.1** (first minor version)
- Each new version represents incremental changes or revisions
- Must remain **below Tier 1 version** (if STRAT is v2.0, these stay at v1.x max)
- Update strategy:
  - **Multi-document versioning:** WO, STR, WALK, IMPL (create new versioned file, preserve history)

#### Tier 3: Audit & Testing Documents

**Scope:** STR, WO, IMPL, WALK, DIR-STR

**Characteristics:**

- Must create **separate versioned files** (never overwrite)
- Purpose: Historical documentation and audit trail
- Example progression: `ANT-WO-002-v0.1` → `ANT-WO-002-v0.2` → `ANT-WO-002-v0.3`

#### Tier L: Logs & State Objects

**Scope:** CSO (Cognitive State Objects)

**Characteristics:**

- **Timestamp-based versioning** instead of semantic versioning (e.g., `YYYYMMDDHHMM`)
- Used exclusively to serialize session context before a handoff or context clear
- Never overwritten; provides an immutable log of execution states
- Example: `CSO-GMN-20260428-103700.md`

#### Tier E: Ecosystem Living Documents

**Scope:** KNOW (NLM Knowledge Modules)

**Characteristics:**

- **No version number** in filename — naming format is `NLM-{TOPIC}.md`
- **No PROJECT_ID** — ecosystem-level, shared across all projects
- **Overwrite in place** when knowledge is updated (not an audit trail document)
- Purpose: Grounded reference layer for all agents, maintained currency with external sources
- Example: `NLM-PostGIS.md`, `NLM-RemoteSensing.md`, `NLM-CyberSecurity.md`

**Constraint:** Tier E documents are the only exceptions to the 4-component naming convention.

---

### Project ID Rules

1. **Canonical Source of Truth:** The definitive Project ID is declared in `project.json` (`project_id` field).
2. **Folder Naming Recommendation:** The format `{PROJECT_ID}_{Project_Name}` is recommended for visual consistency but is NOT enforced by the CLI. Projects operate normally in ANY directory name.
3. **Document Alignment:** All governance documents created within the project MUST use the canonical Project ID in their filename and metadata. Mismatched IDs between documents and runtime state are forbidden.

---

### Agent Code & Document Code Ownership

1. **Code Ownership:** Each document code belongs exclusively to its owning agent (e.g., DI only for Director, PROJ only for GMN)
2. **Permission Required:** Document codes cannot be reassigned or modified by other agents unless:
   - Explicitly authorized by Director
   - Director provides written permission
   - Director creates/edits the document directly
3. **Role Boundary:** Agents operate within their assigned document scope only

#### Document Ownership Matrix

| Agent    | Code | Documents Owned          | Tier                          | Version Strategy                  |
| -------- | ---- | ------------------------ | ----------------------------- | --------------------------------- |
| Director | DIR  | DI, DIR-STR              | Tier 1 (DI), Tier 2 (DIR-STR) | Synchronized (DI), Separate (STR) |
| GMN      | GMN  | STRAT                    | Tier 1                        | Synchronized within tier          |
| GPT      | GPT  | None (Conversational)    | -                             | -                                 |
| PPX      | PPX  | None (Conversational)    | -                             | -                                 |
| ANT      | ANT  | WO, ANT-STR, PDC          | Tier 2/3                      | Separate versioned files          |
| CDC      | CDC  | IMPL, WALK               | Tier 2/3                      | Separate versioned files          |
| NLM      | NLM  | KNOW (Knowledge Modules) | Tier E (Ecosystem)            | Living document (overwrite)       |
| All      | *    | CSO (State Objects)      | Tier L (Logs)                 | Timestamp-based (immutable logs)  |

---

## Governance & Template Standards

### Source of Truth

**This document is the Single Source of Truth for operational governance within the Delta Ecosystem.** For constitutional invariants and ecosystem-level authority principles, refer to the Delta Constitution.

All documents created within this ecosystem must:

- Conform to the roles, responsibilities, and constraints defined herein
- Follow the standardized naming convention: `{AGENT_CODE}-{DOCUMENT_CODE}-{PROJECT_ID}-{VERSION}` (exception: NLM KNOW documents use `NLM-{TOPIC}.md` — see Tier E)
- Adhere to the version management rules (Tier 1, 2, 3) specified in this document
- Maintain alignment with the workflow sequence and approval gates outlined
- Respect agent code ownership and role boundaries

### Template Documents & Detailed Rules

Individual template documents for each document type (DI, STRAT, WO, ANT-STR, IMPL, WALK, DIR-STR, PDC, CSO) will be provided separately.

**Each template file will contain:**

- Detailed content structure and sections
- Specific writing guidelines and quality standards
- Required fields, optional fields, and conditional fields
- Examples and use cases
- Agent-specific instructions and constraints

**Critical Principle:** Template documents provide *detailed implementation guidance* for their respective document types, but they must always remain **aligned with and subordinate to the rules, constraints, and governance defined in this document and the Delta Constitution.**

## Sequential Reasoning & Self-Correction Protocol

The Delta Ecosystem formally incorporates the **Sequential Thinking Protocol** to ensure that all agents (GMN, ANT, CDC) engage in highly rigorous, self-correcting, and non-linear reasoning before outputting final deliverables.

### 1. The Core Principles of AI Self-Correction

- **Dynamic Thought Estimation**: When starting an analysis, the agent must estimate the number of analytical steps required. This estimate is a living value that must be adjusted up or down as the problem's true complexity is uncovered.
- **Explicit Backtracking (Revisions)**: If an agent realizes that a previous assumption was incorrect, it is forbidden from ignoring the error. It must explicitly declare a revision, identify the failed step, and backtrack to correct its reasoning.
- **Exploring Alternatives (Branching)**: For high-risk decisions or complex designs, agents must formulate multiple parallel hypotheses (branches), evaluate their respective trade-offs, and document why specific options are selected or shelved.

### 2. Document-Level Integration

To preserve an audit trail of this reasoning even in non-MCP environments, the protocol is embedded into our core deliverables:

- **Pre-Implementation Plans (`CDC-IMPL`)**: Developers must include a Sequential Reasoning & Branching Analysis under Section 2b, documenting design path revisions and fallback execution pathways.

---

## Dynamic Metadata Memory Layer Protocol

The Delta Ecosystem utilizes a **Dynamic Metadata Memory Layer** powered by the **Memory MCP Server** for Delta ecosystem memory only. The configured memory file is `~/.delta/memory_delta.jsonl`; it must not be used as general assistant memory or project-specific memory.

Project/session context is preserved through Delta documents, especially CSO and linked artifact status. Linked CSO is the project-scoped persistence mechanism. Memory MCP is reserved for ecosystem-level constants, governance invariants, CLI behavior, path conventions, role bootstrap facts, and stable environment quirks that apply across Delta operations.

### 1. The Core Memory Primitives

The persistent memory graph (`~/.delta/memory_delta.jsonl` - stored machine-locally to prevent Google Drive synchronization locks) consists of:

- **Entities (Nodes)**: Standalone concepts categorized by `entityType` (e.g., `agent`, `document`, `component`, `guideline`). Node identifiers (`name`) must use camelCase or snake_case with no spaces (e.g., `C#_Wrapper`, `linker_executor`).
- **Relations (Edges)**: Directed connections between entities. Relations must always be written in the **active voice** (e.g., `creates`, `consumes`, `requires`, `validates`) to ensure bi-directional readability.
- **Observations (Facts)**: Atomic, single-sentence string statements attached to entities. Multiple observations can be appended to a single node, but each observation must represent exactly one fact.

### 2. Operational Pipelines

Agents (GMN, ANT, CDC) must perform the following memory actions during project execution:

- **Context Bootstrapping**: At the beginning of any Delta operational session, agents must run `search_nodes` or `read_graph` to retrieve Delta ecosystem constants, path conventions, CLI behavior, and governance invariants before making design decisions.
- **CSO Project Persistence**: Project-specific context, decisions, intent, process discussion, and implementation lessons must be stored in CSO or governed project artifacts, not in `~/.delta/memory_delta.jsonl`.
- **Ecosystem Memory Writes**: Agents may write to Memory MCP only for Director-approved ecosystem-level facts that are stable across projects. CSO Section 9 may propose ecosystem memory candidates, but project/session facts remain in CSO.
- **Dependency Mapping**: Prior to making code changes, CDC may query the graph for ecosystem-level dependency conventions, but project-specific dependency knowledge must be discovered from project files, status commands, and linked CSOs.

### 3. Memory Classification

Memory entities in the Delta Ecosystem are classified into three tiers:

- **Constitutional Memory** — High-priority invariants distilled from the Delta Constitution and this document. Rarely changes. Director-gated for writes. Invalidated only on constitutional amendment.
- **Operational Memory** — Reusable ecosystem-level conventions, routing patterns, host setup facts, path conventions, and stable environment quirks. Project-specific operational knowledge belongs in CSO/project documents, not Memory MCP.
- **Ephemeral Cognitive Memory** — Session-level reasoning residue. Must NOT be persisted to the memory graph. Governed by the Transient Cognition Doctrine in the Delta Constitution.

**Constitutional Memory entities must be distilled as atomic invariant observations — never stored as raw document blobs.**

Full memory classification criteria, qualification rules, Director approval gate, MCP entity schema, observation standards, and session bootstrap/handoff obligations are defined in the **Memory Architecture Doctrine** (`DELTA-MEMORY-DOCTRINE.md`). That document is the Single Source of Truth for memory governance. The classifications above are a summary only — the doctrine governs in all detail conflicts.

---

## Conditional Agent Skill Routing Engine Protocol

The Delta Ecosystem formally incorporates a deterministic **Skill Routing Engine** to enforce standardized execution boundaries.

### Core Doctrine

**Skill routing is mandatory. Skill activation is a conditional outcome.** Every CDC execution must pass through the routing engine (evaluation is non-optional). The AI does not decide whether to use skills or which skills to use; it strictly executes the deterministic outcome resolved by the routing engine, which can evaluate to zero skills (a perfectly valid outcome), a single skill, or multiple coordinated skills.

#### Skill Authorization Triple-Gate

The global `~/.delta/skills/SKILLS_ROUTING.json` is a **resolver**, not an authority source. A matching routing result is a candidate, not a permission. Before any skill may be loaded and executed, it must satisfy all three gates:

```
candidate_skills  = routing_result(~/.delta/skills/SKILLS_ROUTING.json, context_schema)
authorized_skills = candidate_skills ∩ STRAT_skill_allowlist ∩ WO_skill_binding
```

| Gate | Source | Condition |
|---|---|---|
| Routed | `~/.delta/skills/SKILLS_ROUTING.json` | Skill matches current context schema |
| Allowed by STRAT | `GMN-STRAT` Section 2d Strategic Skill Allowlist | Skill is explicitly listed in the active STRAT |
| Bound by WO | `ANT-WO` Skill Routing Authorization section | Skill is explicitly bound to the active WO |

A skill that passes routing but fails any gate is classified as **NOT_AUTHORIZED** and must not be loaded. CDC must report all NOT_AUTHORIZED skills to ANT in the Pre-Implementation Walkthrough.

If the active WO has no Skill Routing Authorization section, the default is: **no skills authorized**.

Skills cannot expand scope, alter acceptance criteria, change governance gates, or override STRAT, WO, runtime state, block state, or Director Override rules.

### 1. Dual-Reference Architecture

* **Machine Routing (`~/.delta/skills/SKILLS_ROUTING.json`)**: Context resolver for skill candidates. Not an authority source — routing result is input to the triple-gate, not the final authorization decision.
* **Human Index (`~/.delta/skills/SKILLS_CATALOG.md`)**: A purely human-readable catalog indexing available skills across the 5 taxonomy layers without carrying active routing burden.
* **Skill Source (`~/.delta/skills/external/`)**: External skill repositories cloned by `delta skill add`. Project documents reference skill IDs; they do not vendor skill source into `Delta/`.

### 2. The 5-Layer Skill Taxonomy

Skills are strictly classified into five vertical hierarchical layers:

* **CORE**: Foundational, tool-agnostic primitives (e.g., `ReactCore`, `DatabaseCore`).
* **RUNTIME / ENVIRONMENT**: Execution boundaries and environment behaviors (e.g., `ReactRuntime-Web`).
* **PLATFORM**: Thin, constraint-driven vendor overrides (e.g., `PostgresPlatform-Supabase`, `HostingPlatform-Vercel`). *Holds higher routing precedence than RUNTIME in conflicts.*
* **INTENT**: Action-oriented routing based on the primary goal (e.g., `BrowserAutomation-Intent-Scraping`).
* **ORCHESTRATION**: Cross-skill interaction and composition management.

### 3. The Input Context Schema

To query the routing JSON, the agent must construct a standardized input schema representing the current task state:

* `goal`: High-level objective (`feature_delivery`, `diagnostics`, `optimization`, etc.).
* `operation`: Specific actions (`component_build`, `api_design`, `issue_isolation`, etc.).
* `environment`: Execution boundary array (`["web_client", "web_server"]`, etc.).
* `platform`: Hosting or cloud providers (`["vercel", "supabase"]`, etc.).
* `artifact`: Outputs being generated (`["ui_component", "test_suite"]`, etc.).
* `tooling`: Frameworks/libs explicitly used (`["react", "playwright"]`).
* `symptom`: Error details acting as routing overrides (`["hydration error"]`).
* `scope`: Blast radius (`single_file`, `feature`, `system`).

---

## Runtime Authority & CLI

The Delta CLI is mandatory operational middleware for all project-level AI execution. The full CLI architecture — including command surface, execution boundaries, workflow gating, Director Override doctrine, and the runtime vs markdown authority boundary — is defined in the **CLI Architecture document** (`DELTA-CLI-ARCHITECTURE.md`). That document is the Single Source of Truth for CLI architecture. The summary below is for orientation only.

### Runtime vs Markdown Authority

The Delta ecosystem maintains two distinct authority layers:

- **Markdown governance documents** (this document, role rule files, doctrine files) define **semantic truth** — what *should* happen
- **Runtime state (`progress.json`)** defines **operational truth** — what *is* happening in the current project execution

When the two conflict, `progress.json` governs current CLI behavior. An agent cannot override a runtime gate by citing a markdown document. Changing a gate requires advancing the workflow state through normal execution, or a Director Override declaration (`delta override declare`).

### Director Override (Runtime Declaration)

Director Override is declared via the CLI — it is a runtime event, not a markdown annotation. **Director Override requires Administrator access.** The AI must instruct the Director on the specific code/command to enter for the override when a situation necessitates it. All overrides are recorded in `progress.json` with a closed scope vocabulary, declared reason, and expiry condition. Override records are permanent audit artifacts. Full Director Override doctrine is in `DELTA-CLI-ARCHITECTURE.md` §5.

### Runtime Metadata Schema

The canonical schema for `progress.json` — including the WO lifecycle state machine, document state tracking, override record format, gate transition log, and logs registry — is defined in `DELTA-RUNTIME-SCHEMA.md`.

### Operation Registry

The Delta Operation Registry (`DELTA-OPERATION-REGISTRY.json`) is the machine-readable definition of all valid CLI operations. Each entry defines a governance contract: role authorization, required inputs, expected outputs, gating pre/post conditions, and governance constraints. Operations are governance abstractions — they do not contain prompt text. The Operation Registry schema is defined in `DELTA-OPERATION-REGISTRY-SCHEMA.md`.

---

## Conflict Resolution Protocols

### 1. The Conflict Resolution Hierarchy

In the event of structural overlaps or logical conflicts between strategy, planning, and implementation boundaries, the following strict hierarchy of authority must be applied:

$$\text{STRAT} \gt \text{WO} \gt \text{SKILLS} \gt \text{CDC}$$

* **STRAT (Project Strategy)**: Overrides all downstream project systems; defines global architectural invariants.
* **WO (Work Order)**: Defines the target execution intent and boundaries for the specific task.
* **SKILLS (Routing Engine)**: Enforces physical runtime, platform, and tool implementation constraints.
* **CDC (Lead Developer)**: Owns execution methods but cannot override constraints set by higher layers.

#### 🚨 Escape Hatch: SKILL_CONFLICT_ESCALATION

If a loaded `SKILL` constraint detects that the active `STRAT` document relies on outdated engineering practices, CDC is forbidden from silently violating the hierarchy. Instead, CDC triggers a **`SKILL_CONFLICT_ESCALATION`** flag, forcing an immediate, fast-tracked strategic review by GMN.

### 2. Execution Mode — STRICT Only

Delta operates exclusively in **STRICT Mode**: full multi-agent, document-driven governance with no procedural shortcuts. Every task flows through the formal DI → STRAT → WO → ANT-STR → IMPL → WALK lifecycle. There are no bypass lanes, adaptive pathways, or execution-mode toggles.

The former Adaptive Mode concept has been permanently removed from the Delta core and will be developed as a separate standalone tool (`delta-lite`).

### 3. Controlled Feedback Loop (STRAT Invalidation)

If physical implementation by `CDC` uncovers an architectural design flaw, it must classify the invalidation to prevent strategic churn:

* **SOFT Invalidation**: Minor implementation friction or local tool constraints. CDC must resolve this locally using alternative methods without altering upstream strategy.
* **HARD Invalidation**: Direct architectural contradiction. CDC raises a formal `STRAT_INVALIDATION` flag in its Pre-Implementation Plan, forcing GMN to trigger an immediate, fast-track revision of the `STRAT` document without restarting the entire project cascade.

---

### Compliance & Enforcement

1. All template documents explicitly reference the relevant sections in this document and the Delta Constitution
2. Deviations from this protocol require Director approval and documented exceptions
3. Document creation must validate compliance with both this document and the Delta Constitution before acceptance
4. Version management, naming conventions, and approval gates are non-negotiable

**When in doubt, refer to this document for operational governance. When template documents conflict with this document, this document takes precedence. When this document conflicts with the Delta Constitution, the Delta Constitution takes precedence.**

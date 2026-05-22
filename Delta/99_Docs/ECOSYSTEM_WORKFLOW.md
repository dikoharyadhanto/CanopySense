# Delta Ecosystem Workflow

This document displays the complete lifecycle of a Delta project from Director's Intent to Final Approval, aligned with DELTA_PROTOCOL.md governance.

## Complete Project Workflow Diagram

```mermaid
graph TD
    %% Phase 1: Director Intent
    subgraph DIRECTOR_INTENT["DIRECTOR LEVEL - Strategic Intent"]
        DI["📋 DIR: Director's Intent<br/>(DI Document)<br/>Vision, Values, Reasoning"]
    end

    %% Phase 2: Strategy Layer
    subgraph STRATEGY["STRATEGY LAYER - GMN"]
        STRAT["📊 GMN: Project Strategy<br/>(STRAT Document)<br/>v1.0 (Anchor)"]
    end

    %% Phase 4: Strategy Approval - Parallel Tracks
    subgraph APPROVAL_STRATEGY["STRATEGY APPROVAL - Parallel Tracks"]
        GPT_AUDIT["🔍 GPT: Conversational Audit<br/>Risk & Quality Review"]
        PPX_VERIFY["✅ PPX: Conversational Verification<br/>Architecture & Research"]
    end

    %% Phase 5: Planning Layer
    subgraph PLANNING["PLANNING LAYER - ANT"]
        WO["📋 ANT: Work Order<br/>(WO Document)<br/>Technical Specification"]
        STR["🧪 ANT: Test Report<br/>(STR Document)<br/>Testing Strategy"]
    end

    %% Phase 6: Implementation Layer
    subgraph IMPLEMENTATION["IMPLEMENTATION LAYER - CDC"]
        IMPL["🔧 CDC: Pre-Implementation<br/>(IMPL Document)<br/>Technical Approach"]
        CODE["💻 CDC: Code Implementation<br/>Development Execution"]
        WALK["📝 CDC: Implementation Report<br/>(WALK Document)<br/>Execution Summary"]
    end

    %% Phase 7: Implementation Approval
    subgraph APPROVAL_IMPL["IMPLEMENTATION APPROVAL - ANT"]
        ANT_REVIEW["✔️ ANT: Review & Approve<br/>IMPL & WALK Documents"]
    end

    %% Phase 8: Final QA
    subgraph FINAL_QA["FINAL QUALITY ASSURANCE"]
        GPT_FINAL["🔍 GPT: Conversational Audit<br/>Technical & Post-Production"]
        PPX_FINAL["✅ PPX: Conversational Verification<br/>Technical & Post-Production"]
    end

    %% Phase 9: Director Testing (Optional)
    subgraph DIRECTOR_TEST["DIRECTOR TESTING - Optional"]
        DIR_STR["🎯 DIR: Manual Testing<br/>(DIR-STR Document)<br/>Mid-version / Near-final / On-demand"]
    end

    %% Phase 10: Final Approval
    subgraph FINAL_APPROVAL["FINAL APPROVAL - Director"]
        FINAL["✨ Director: Final Review<br/>& Approval<br/>Project Closure"]
    end

    %% References & Logs
    subgraph SUPPORT["SUPPORTING ARTIFACTS"]
        REFS["05_References/<br/>Code, Notes, Links"]
        KNOW["06_Knowledge/<br/>NLM Knowledge Modules"]
        LOGS["07_Logs/<br/>CSO & Conversation Logs"]
    end

    %% Workflow Connections
    DI --> STRAT

    STRAT --> GPT_AUDIT
    STRAT --> PPX_VERIFY

    GPT_AUDIT -.-->|Approved| WO
    PPX_VERIFY -.-->|Approved| WO
    WO --> STR

    STR --> IMPL
    IMPL --> CODE
    CODE --> WALK
    WALK --> ANT_REVIEW

    ANT_REVIEW -.-->|Approved| GPT_FINAL
    ANT_REVIEW -.-->|Approved| PPX_FINAL

    GPT_FINAL --> DIR_STR
    PPX_FINAL --> DIR_STR
    DIR_STR --> FINAL

    FINAL --> LOGS
    FINAL --> REFS
    FINAL --> KNOW

    %% Styling
    style DIRECTOR_INTENT fill:#1a1a2e,stroke:#ff6b6b,stroke-width:3px,color:#fff
    style STRATEGY fill:#2d1a2d,stroke:#ff00ff,stroke-width:2px,color:#fff
    style APPROVAL_STRATEGY fill:#1a2b3c,stroke:#3498db,stroke-width:2px,color:#fff
    style PLANNING fill:#3d2b1a,stroke:#e67e22,stroke-width:2px,color:#fff
    style IMPLEMENTATION fill:#1a3d1a,stroke:#2ecc71,stroke-width:2px,color:#fff
    style APPROVAL_IMPL fill:#1a2b3c,stroke:#3498db,stroke-width:2px,color:#fff
    style FINAL_QA fill:#3d3d1a,stroke:#f1c40f,stroke-width:2px,color:#000
    style DIRECTOR_TEST fill:#2d1a2d,stroke:#9b59b6,stroke-width:2px,color:#fff
    style FINAL_APPROVAL fill:#1a1a2e,stroke:#e74c3c,stroke-width:3px,color:#fff
    style SUPPORT fill:#34495e,stroke:#95a5a6,stroke-width:2px,color:#fff
```

## Workflow Phases Explained

### Phase 1: Director Intent (DI)
- **Owner:** Director (User)
- **Document:** `DIR-DI-{PROJECT_ID}-v1.0.md`
- **Purpose:** Strategic vision, values, reasoning
- **Output:** DI document serves as the mandatory input to GMN strategy work

### Phase 2: Strategy Layer (GMN)
- **Owner:** GMN (Global System Architect)
- **Document:** `GMN-STRAT-{PROJECT_ID}-v1.0.md`
- **Purpose:** Define complete strategic architecture aligned with DI (for mid/large projects)

### Phase 4: Strategy Approval (Conversational)
- **GPT Track:** GPT conducts independent risk audit and approves STRAT
- **PPX Track:** PPX conducts independent architecture verification and approves STRAT
- **Gate:** Both tracks must grant conversational approval before proceeding to planning
- **Outputs:** Verified and locked Strategy Layer

### Phase 5: Planning Layer (ANT)
- **Owner:** ANT (Technical Foreman)
- **Documents:**
  - `ANT-WO-{PROJECT_ID}-v0.1+` (separate versioned files)
  - `ANT-STR-{PROJECT_ID}-v0.1+` (separate versioned files)
- **Prerequisites:** Approved strategy from Phase 4
- **Purpose:** Translate strategy into actionable, testable technical tasks

### Phase 6: Implementation Layer (CDC)
- **Owner:** CDC (Lead Developer)
- **Documents:**
  - `CDC-IMPL-{PROJECT_ID}-v0.1+` (separate versioned files)
  - `CDC-WALK-{PROJECT_ID}-v0.1+` (separate versioned files)
- **Purpose:** Pre-implementation design and code execution aligned with WO

### Phase 7: Implementation Approval (ANT)
- **Owner:** ANT (Technical Foreman)
- **Purpose:** Validate IMPL and WALK against the WO
- **Gate:** Both documents must be approved by ANT/Director before final QA

### Phase 8: Final Quality Assurance (Conversational)
- **GPT Track:** Final conversational risk audit of technical implementation and deliverables
- **PPX Track:** Final conversational research/validation of technical implementation and deliverables

### Phase 9: Director Testing (Optional)
- **Owner:** Director
- **Document:** `DIR-STR-{PROJECT_ID}-v0.1+.md`
- **When:** Mid-version, near-final, or Director-initiated manual testing checkpoints

### Phase 10: Final Approval
- **Owner:** Director
- **Purpose:** Final review and project closure
- **Outputs:** All documents finalized, project logged, and CSO serialized

## Document Versioning in Workflow

### Tier 1: Major Versions (Synchronized Anchor Documents)
- **Documents:** `DI`, `STRAT`, `DOCS`
- **Versioning:** v1.0, v2.0, v3.0...
- **Update:** Overwritten/updated in place (single file per version)
- **Constraint:** All downstream Tier 2/3 documents must stay below these versions

### Tier 2: Minor Versions (Execution & Progress)
- **Documents:** `WO`, `STR`, `IMPL`, `WALK`
- **Versioning:** v0.1, v0.2, v0.3... (max below current Tier 1 version)
- **Update:** Separate versioned files (preserves complete audit trail)

### Tier 3: Historical Records (Audit & Testing)
- **Documents:** `STR`, `WO`, `IMPL`, `WALK`, `DIR-STR`
- **Update:** New separate file per version (preserve history, never overwritten)

### Tier L: Logs & State Objects (immutable Context)
- **Documents:** `CSO` (Cognitive State Objects)
- **Versioning:** Timestamp-based (`YYYYMMDDHHMM`) to preserve immutable context logs

### Tier E: Ecosystem Living Documents
- **Documents:** `KNOW` (NLM Knowledge Modules)
- **Update:** Living modules updated in place (`NLM-{TOPIC}.md`) with no Project ID or version

## Folder Structure During Workflow

```
{PROJECT_ID}_{Project_Name}/
├── 00_Rules/             ← Phase 2-8 agent rule definitions (ANT, CDC, GMN)
├── 01_Strategy/          ← Phase 2 strategy outputs (DIR-DI, GMN-STRAT)
├── 02_Blueprint/         ← Phase 5 outputs (ANT-WO, ANT-STR)
├── 03_Build/             ← Phase 6-7 outputs (CDC-IMPL, CDC-WALK)
├── 05_References/        ← Project references, code snippets, external links
├── 06_Knowledge/    ← Ecosystem knowledge modules (NLM)
├── 07_Logs/              ← Phase 10 CSOs and immutable logs
└── 99_Docs/              ← Supporting documentation (this file, PDFs, etc.)
```

## Key Principles

1. **Single Source of Truth:** DELTA_PROTOCOL.md governs all workflow
2. **Approval Gates:** Explicit entry/exit criteria at each phase
3. **Parallel Processing:** GPT and PPX audit independently (no bias)
4. **Version Hierarchy:** Tier 1 documents anchor all downstream versions
5. **Historical Accuracy:** Tier 3 documents maintain complete audit trail
6. **Role Isolation:** Each agent operates strictly within assigned document scopes
7. **Director Authority:** Final decision maker across all ecosystem phases

---

**For detailed governance rules, constraints, and standards, refer to DELTA_PROTOCOL.md**

**Document Generated:** 2026-05-06
**Aligned With:** DELTA_PROTOCOL.md v1.0

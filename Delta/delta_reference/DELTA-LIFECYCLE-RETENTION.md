# Lifecycle Retention Doctrine

**Delta Ecosystem — Artifact Lifecycle & Retention Governance**
**Authority Tier:** Operational Doctrine (subordinate to the Delta Constitution and the operational governance protocol)
**Owner:** Director

> This document defines the lifecycle classification, retention rules, decay triggers, and archival doctrine for every artifact type produced within the Delta Ecosystem. This doctrine operationalizes the Lifecycle Governance principle established in the Delta Constitution. In any conflict between this document and the operational governance protocol or the Delta Constitution, those documents prevail.

---

## Section 1 — Foundational Lifecycle Classifications

Every artifact in the Delta Ecosystem belongs to exactly one lifecycle classification. Classification determines retention rules, decay behavior, and archival obligations.

### 1.1 Persistent

**Definition:** Artifacts that carry ongoing governance authority over future decisions. They must be explicitly created, versioned (where applicable), and approved. They retain authority until formally superseded, deprecated, or archived by the Director.

**Authority decay:** A persistent artifact does not lose authority through inactivity alone. It must be explicitly superseded or deprecated. However, a persistent artifact that has been structurally contradicted by a higher-tier document without reconciliation enters governance-conflicted state and loses authoritative standing until reconciled (per Constitution Article VIII).

### 1.2 Transient

**Definition:** Artifacts that serve immediate cognitive purposes — in-session reasoning, drafts, hypotheses, audit outputs. They carry no ongoing authority. They decay at session boundary or upon supersession within the session.

Governed in full by the Transient Cognitive Exchange Specification. Not addressed further in this document.

### 1.3 Immutable Log

**Definition:** Artifacts that, once created, are never modified. They provide an append-only audit trail. They do not carry governance authority — they record what happened. They cannot decay or be superseded; only archived when the project they belong to is archived.

### 1.4 Living

**Definition:** Artifacts that are updated in place without version increment. They do not accumulate versions — the current state is always the authoritative state. No prior version exists by design. They decay only when their subject domain becomes obsolete or the Director explicitly retires them.

---

## Section 2 — Document Type Lifecycle Classification

### 2.1 Ecosystem Governance Documents

These documents govern the entire Delta Ecosystem across all projects.

| Document | Lifecycle | Retention Rule | Decay Trigger |
|---|---|---|---|
| Delta Constitution | Persistent — Permanent | Never expires; changes only via amendment process | Constitutional amendment (Article VIII only) |
| Operational Governance Protocol | Persistent — Permanent | Never expires; changes only by Director | Director-initiated revision |
| Memory Architecture Doctrine | Persistent — Permanent | Never expires independently | Director revision or supersession by updated doctrine |
| Registry Doctrine | Persistent — Permanent | Never expires independently | Director revision or supersession by updated doctrine |
| Transient Cognition Specification | Persistent — Permanent | Never expires independently | Director revision or supersession |
| Lifecycle Retention Doctrine (this document) | Persistent — Permanent | Never expires independently | Director revision or supersession |
| Log Reference Semantics | Persistent — Permanent | Never expires independently | Director revision or supersession |
| Semantic Governance Registry | Living | Updated in place when documents are added, removed, or renamed | Entry removed when the document it references is archived |

### 2.2 Project-Level Strategy Documents

These documents govern a specific project. They are scoped to the project folder.

| Document | Lifecycle | Retention Rule | Decay Trigger |
|---|---|---|---|
| DIR-DI (Director's Intent) | Persistent — Versioned (Tier 1) | Retained for full project lifespan; all versions preserved | Major project pivot requiring new DI; prior version archived not deleted |
| GMN-STRAT (Project Strategy) | Persistent — Versioned (Tier 1) | Retained for full project lifespan; all versions preserved | Major STRAT revision (v1.x → v2.0); prior version archived |

**Authority decay rule for STRAT:** When a new major STRAT version is ratified, all Operational Memory entities in MCP that were derived from prior STRAT must be re-validated. Entities that contradict the new STRAT lose operational authority until updated (per DELTA-MEMORY-DOCTRINE.md Section 2).

### 2.3 Project-Level Planning Documents

| Document | Lifecycle | Retention Rule | Decay Trigger |
|---|---|---|---|
| ANT-WO (Work Order) | Persistent — Versioned (Tier 2/3) | All versions retained as audit trail; never deleted during active project | WO superseded by next version; prior version archived in `03_Build/99_Archive/` |
| ANT-STR (Software Test Report) | Persistent — Versioned (Tier 2/3) | All versions retained; tied to the WO version they test | Superseded by next STR version |
| DIR-STR (Director Manual Test Report) | Persistent — Versioned (Tier 2/3) | All versions retained; optional per project | Superseded by next DIR-STR version |

### 2.4 Project-Level Implementation Documents

| Document | Lifecycle | Retention Rule | Decay Trigger |
|---|---|---|---|
| CDC-IMPL (Pre-Implementation Plan) | Persistent — Versioned (Tier 2/3) | All versions retained; paired with the WO version they execute | Superseded when corresponding WO is superseded |
| CDC-WALK (Implementation Report) | Persistent — Versioned (Tier 2/3) | All versions retained as permanent execution record | Never decays; only archived when project is closed |

### 2.5 Cognitive State Objects

| Document | Lifecycle | Retention Rule | Decay Trigger |
|---|---|---|---|
| CSO (Cognitive State Object — any agent) | Immutable Log (Tier L) | Never modified after creation; retained for project lifespan | Archived (not deleted) when project is closed |

**CSO lifecycle states:** CSOs follow a defined lifecycle managed by `delta cso` commands:

| State | Meaning | Transition |
|-------|---------|-----------|
| `DRAFT` | Created via `delta cso new`; content being written | → `COMPLETE` or `LOCKED` |
| `COMPLETE` | Content finalized via `delta cso complete` | → `LOCKED` |
| `LOCKED` | Immutable historical record via `delta cso lock` | Terminal |
| `SUPERSEDED` | Replaced by newer CSO | Terminal |

**CSO retention note:** CSOs are the only artifacts where session cognition is partially preserved — specifically in Section 9 (Memory Candidates) and the declared session state. The cognitive reasoning within the CSO is historical record only; it does not carry forward as active authority. A CSO that was never reviewed by the Director before the next session began is treated as expired for promotion purposes, but remains as an immutable log record. CSOs are supporting documents — they never block lock gates or artifact approvals.

### 2.6 Audit Records

| Document | Lifecycle | Retention Rule | Decay Trigger |
|---|---|---|---|
| Audit Record (`delta audit record`) | Immutable Log | Append-only; never modified after creation (except `conditions_status` transitions); retained for project lifespan | Archived when project is closed |

**Audit record rules:**
- Audit records are governance evidence, not governance authority. They record who approved/rejected what and when.
- Only `conditions_status` may transition: `NONE` → `OPEN` → `RESOLVED` or `WAIVED_BY_DIRECTOR`.
- Audit records survive session boundaries — they are not transient cognition.
- They are never deleted during an active project.

### 2.7 Ecosystem Knowledge Documents

| Document | Lifecycle | Retention Rule | Decay Trigger |
|---|---|---|---|
| NLM-KNOW (Knowledge Module) | Living (Tier E) | Updated in place; no version history by design | Retired by Director when the technical domain is no longer relevant to the ecosystem |

**KNOW living document rule:** Because KNOW documents have no version history, agents must treat the current state as the only authoritative state. References to "what KNOW said previously" have no standing.

### 2.8 Product Documentation

| Document | Lifecycle | Retention Rule | Decay Trigger |
|---|---|---|---|
| DOCS (Product Documentation) | Persistent — Versioned | Created on Director request; retained for project lifespan | Superseded by updated DOCS version |

### 2.9 Agent Configuration & Rule Files

| Document | Lifecycle | Retention Rule | Decay Trigger |
|---|---|---|---|
| CLAUDE.md, GEMINI.md | Persistent — Permanent (per project) | Retained for project lifespan | Director revision |
| Agent Rule Files (00_Rules/) | Persistent — Permanent (ecosystem-level) | Retained indefinitely | Director revision |

---

## Section 3 — Retention Policies

### 3.1 Active Project Retention

During an active project (from DI creation to Director final review):
- All Tier 1 and Tier 2/3 documents must be retained in their original locations
- Superseded versions are moved to `03_Build/99_Archive/` — never deleted
- No governance document may be deleted during an active project without explicit Director authorization
- CSOs are retained in `07_Logs/` without modification

### 3.2 Project Closure Retention

When a project is formally closed (Director declares completion):
- All documents are archived in their final state
- No documents are deleted at project closure — archival is the closure action
- The project folder may be relocated or compressed but its contents must remain intact
- MCP Operational Memory entities scoped to the closed project are flagged as `project_closed` — they are not deleted but are deprioritized at session bootstrap

### 3.3 Ecosystem-Level Document Retention

Ecosystem governance documents (Constitution, Protocol, doctrines, rule files) have no expiry. They are retained indefinitely and may only be changed through their respective amendment or revision processes.

### 3.4 Supersession vs. Deletion

**Supersession** is the correct action when a document is replaced by a newer version. The prior version is moved to `99_Archive/` and its filename is preserved. The relationship between versions is maintained in the document's metadata.

**Deletion** is never a standard lifecycle action. Deletion may only occur under explicit Director authorization, with rationale recorded. Deleted documents must be noted in the project change log.

---

## Section 4 — Authority Decay Rules

Authority decay is the principle that aged, stale, or invalidated artifacts formally lose their claim to influence agent decisions (Constitution Article IX). This section operationalizes that principle.

### 4.1 Decay Conditions

An artifact enters authority decay when any of the following occurs:

| Condition | Effect |
|---|---|
| Document is superseded by a newer version | Prior version loses authority; new version is authoritative |
| Document contradicts a higher-tier document without reconciliation | Document enters governance-conflicted state; loses authority until reconciled |
| Document's source domain is retired by the Director | Document is retired and loses authority |
| MCP memory entity is contradicted by a constitutional amendment | Entity loses constitutional standing; must be re-validated or deleted |
| STRAT major version increment | Operational Memory entities derived from prior STRAT lose project-level authority |
| CSO Section 9 candidates not reviewed before next session | Candidates expire; they may not be promoted retroactively |

### 4.2 Governance-Conflicted State

A document in governance-conflicted state:
- May not be cited as authoritative by any agent
- Must be flagged to the Director at the first session where the conflict is detected
- Regains authority only when the Director explicitly reconciles the conflict
- Does not automatically resolve — conflict state persists until Director action

### 4.3 Authority Decay Does Not Mean Deletion

A decayed artifact remains in the archive as a historical record. Authority decay strips governance standing, not existence. An agent must not read a decayed artifact as if it carries current authority, but the artifact's historical record is preserved.

---

## Section 5 — Archival Doctrine

### 5.1 Archive Location

Superseded project-level documents are archived in `03_Build/99_Archive/` within the project folder. The archive is append-only — no document is removed from the archive once placed there.

### 5.2 Archive Naming

Archived documents retain their original filename. No renaming occurs at archival. The act of moving to `99_Archive/` is sufficient to denote superseded status.

### 5.3 Archive Access

Archived documents may be read for historical reference. They must never be:
- Cited as authoritative for current decisions
- Edited or modified
- Removed from the archive without explicit Director authorization

### 5.4 Ecosystem Document Archival

Ecosystem-level governance documents (Constitution, Protocol, doctrines) are not archived within project folders — they are ecosystem assets. When revised, the prior version may be preserved as a historical record in the ecosystem root `99_Docs/` folder with a date suffix, but this is optional and at Director discretion.

---

## Section 6 — Entropy Prevention

Artifact accumulation without lifecycle management degrades operational clarity and creates conditions for contradictory authority claims (Constitution Article IX). The following rules prevent lifecycle entropy:

1. **No orphaned documents.** Every document in the project must be traceable to an active project, an approved WO, or an ecosystem governance function. Documents with no traceable purpose are candidates for archival on Director review.

2. **No undeclared supersessions.** When a new document version is created, the prior version must be explicitly moved to archive in the same action. Leaving multiple active versions of the same document without declaring supersession creates competing authority.

3. **No accumulation of expired CSOs as active context.** At session bootstrap, agents must not load CSOs as active governance context — they are historical logs only. Bootstrap context comes from MCP Memory, the Registry, and formal governance documents.

4. **No governance documents outside the mandatory structure.** Ad-hoc governance documents created outside the standard folder structure and document taxonomy do not carry governance authority regardless of their content.

5. **WO reference obligation.** All Tier 2/3 documents must have a corresponding WO reference. Orphaned documents without a WO link must be reconciled at session close or flagged for Director review.

---

*This document is subordinate to the Delta Constitution and the operational governance protocol. For constitutional invariants, refer to the Delta Constitution. For operational workflow standards, refer to the operational governance protocol.*

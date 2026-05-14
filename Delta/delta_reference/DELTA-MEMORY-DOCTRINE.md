# Memory Architecture Doctrine

**Delta Ecosystem — Memory Governance**
**Authority Tier:** Operational Doctrine (subordinate to the Delta Constitution and the operational governance protocol)
**Owner:** Director
**Produced by:** GMN (Global System Architect)

> This document defines how knowledge is classified, stored, written, and retrieved in the Delta Ecosystem's MCP memory graph. All agents operating within the ecosystem must conform to the classification, schema, and gating rules defined herein. In any conflict between this document and the operational governance protocol or the Delta Constitution, those documents prevail.

---

## Section 1 — 3-Tier Memory Classification

All memory entities in the Delta Ecosystem belong to exactly one of three tiers. Tier assignment is not a suggestion — it determines write authority, invalidation triggers, and persistence rules.

---

### Tier 1: Constitutional Memory

**Definition:** Invariant principles and authority structures distilled directly from the Delta Constitution and the operational governance protocol. These entities reflect truths that hold across all projects, all sessions, and all agents without exception.

**Characteristics:**
- Derived exclusively from the Delta Constitution or the operational governance protocol
- Stable: changes only when the source document is formally amended
- Universal: applies to every agent, project, and context
- Atomic: each entity represents exactly one governance truth
- Director-gated: no agent may write or update a Constitutional Memory entity without explicit Director approval

**Invalidation trigger:** A Constitutional Memory entity is invalidated only when the Constitution or Protocol article it was derived from is amended. Invalidation must be declared by the Director.

**Examples of qualifying entities:**
- The Delta authority hierarchy chain (Article IV)
- The principle that runtime state derives authority from approved governance documents (Article X)
- The prohibition on mid-session role switching (Article III)
- The Director's position as final fallback authority in all governance failures

**Examples of non-qualifying entities (misclassified as Constitutional):**
- Project-specific routing patterns
- Version-specific naming conventions
- Agent implementation lessons from a specific project
- Any fact that applies only to a specific project or session

---

### Tier 2: Operational Memory

**Definition:** Reusable Delta ecosystem conventions, routing patterns, host setup facts, environment configurations, CLI behavior, and path conventions accumulated during execution. These entities persist across sessions but are scoped to operational decisions rather than constitutional principles.

**Characteristics:**
- Derived from Delta setup, agent execution, governance decisions, CLI behavior, host integration, or ecosystem-level doctrine
- Stable across projects or across Delta host/runtime usage
- Scoped to Delta ecosystem operations, not to a single product project
- Write-eligible only when the fact is ecosystem-level and Director-approved for Memory MCP persistence

**Invalidation triggers:**
- Explicit Director instruction to invalidate or supersede
- Discovery that the entity conflicts with a higher-tier authority
- Delta CLI, setup, host integration, or governance doctrine changes that supersede the fact

**Sub-classifications (for entity typing):**
- `routing_pattern` — Skill routing decisions, platform conventions, environment constraints
- `implementation_lesson` — ecosystem-level lessons about Delta CLI, setup behavior, host behavior, or reusable execution constraints
- `environment_config` — System paths, environment quirks, runtime configuration facts
- `governance_convention` — Operational conventions derived from agent rules or protocol that do not rise to constitutional level

**Explicit exclusion:** Project-specific lessons, product facts, STRAT/WO decisions, implementation details, feature context, and session discussion are not eligible for `~/.delta/memory_delta.jsonl`. They must be captured in CSO or governed project artifacts.

---

### Tier 3: Ephemeral Cognitive Memory

**Definition:** Session-level reasoning residue, mid-analysis hypotheses, draft conclusions, and exploratory thoughts generated during a single AI session.

**Characteristics:**
- Exists only within the active session context
- Must NOT be written to the MCP memory graph under any circumstance
- Governed by the Transient Cognition Doctrine (Constitution Article VI)
- Decays at session boundary — no persistence mechanism is permitted for this tier

**Examples:**
- Intermediate reasoning steps during STRAT formulation
- Draft architectural alternatives that were evaluated and discarded
- Speculative hypotheses raised and resolved within a single session
- Conversational audit feedback not approved for promotion to a formal document

**Escalation path:** If an ephemeral artifact contains a candidate insight that may qualify as Delta ecosystem Operational Memory, it must be recorded in CSO Section 9 as a Memory Candidate and reviewed by the Director before any persistence action is taken. Project-scoped candidates remain in CSO/project artifacts and must not be promoted to Memory MCP.

---

## Section 2 — Memory Authority Hierarchy

The memory authority hierarchy governs which governance tier is authoritative for each memory classification, and who may authorize write operations. This hierarchy is reconciled with the full authority chain defined in the Delta Constitution.

### Write Authority

| Tier | Write Authority | Approval Gate |
|---|---|---|
| Constitutional Memory | Director only | Director must explicitly approve each entity before write |
| Operational Memory — Ecosystem-level | GMN or ANT (initiates) → Director confirms | Flagged in CSO Section 9; Director approves promotion |
| Operational Memory — Project-level | Not eligible for Memory MCP | Persist in CSO/project artifacts only |
| Ephemeral Cognitive Memory | Forbidden from persistence | No write path exists |

### Read Authority

All agents may read from all tiers at any time. Read access is unrestricted. Constitutional Memory should be queried at session bootstrap to establish governance baseline. Operational Memory should be queried for Delta ecosystem constraints only. Project context must be discovered from project files, `delta session bootstrap`, artifact status commands, and linked CSOs.

### Authority Chain Alignment

Memory classification maps directly to the Constitution Article IV authority hierarchy as follows:

```
DELTA_CONSTITUTION          → Source of Constitutional Memory
        ↓
DELTA_PROTOCOL              → Source of Constitutional Memory (operational invariants)
        ↓
GLOBAL_RULES (00_Rules/)    → Source of Operational Memory (role-specific conventions)
        ↓
STRAT                       → Project artifact; CSO/project docs only
        ↓
WO                          → Project artifact; CSO/project docs only
        ↓
RUNTIME_STATE               → Ephemeral — not persisted to memory graph
        ↓
SKILLS                      → Source of Operational Memory (routing patterns, platform constraints)
        ↓
CDC (execution)             → Project artifact unless lesson is ecosystem-wide
```

**Key constraint:** Memory tier assignment follows source document authority tier, not the judgment of the writing agent. A lesson derived from a CDC execution session is Operational Memory regardless of how significant it feels to the agent that produced it.

---

## Section 3 — Qualification Criteria for Constitutional Invariants

An entity qualifies as Constitutional Memory only if it satisfies **all five** of the following criteria simultaneously. If any criterion fails, the entity must be reclassified as Operational Memory.

### Criterion 1: Universality
The fact must apply to every agent, every project, and every execution context without exception. Any fact that is conditional, project-scoped, or role-scoped fails this criterion.

> **Test:** Does this fact hold true in a project that has never started, in a project that is complete, and in a project in the middle of execution? If no — it is not universal.

### Criterion 2: Governance Origin
The fact must be directly and explicitly derived from the Delta Constitution or the operational governance protocol. It may not be inferred, extrapolated, or assembled from multiple sources. The source article or section must be citable.

> **Test:** Can you point to a specific article or section that states this fact? If no — it fails governance origin.

### Criterion 3: Stability
The fact must be expected to remain true indefinitely. It may only change when the Constitution or Protocol is formally amended. Facts that are likely to evolve with project conditions, technology choices, or operational patterns are Operational Memory.

> **Test:** Would this fact require updating if a new project is created, a STRAT is revised, or a new CDC is onboarded? If yes — it is not stable enough for constitutional tier.

### Criterion 4: Non-Derivability on Demand
The entity must represent a persistent truth that benefits from being pre-loaded into agent context, rather than something an agent can trivially re-derive by reading the source document. If an agent can reliably get the fact by reading the governing document, storing it adds no value and creates a drift risk.

> **Test:** Does persisting this fact meaningfully reduce an agent's cognitive load at session bootstrap, or does it merely duplicate document content? If it merely duplicates — do not persist it as Constitutional Memory.

### Criterion 5: Atomicity
The entity must express exactly one governance truth. It must not bundle multiple facts, contain conditional logic, or reference other entities implicitly. Compound facts must be decomposed into separate atomic entities.

> **Test:** Can this fact be stated in a single declarative sentence with no "and," "but," or "if"? If no — decompose it before persisting.

---

## Section 4 — Director Approval Gate for Constitutional Memory Writes

No Constitutional Memory entity may be written to the MCP memory graph without Director approval. This section defines the full gating procedure.

### Gate Procedure

**Step 1 — Candidate Identification**
During session execution, if an agent identifies a fact it believes qualifies as a Constitutional Memory invariant, it records the candidate in CSO Section 9 under the heading `Constitutional Memory Candidates`. The candidate must include:
- Proposed entity name (snake_case)
- Proposed entityType
- Proposed observations (atomic, declarative)
- Source document and article/section citation
- Justification against all 5 qualification criteria

**Step 2 — Director Review**
The Director reviews the candidate against the 5 qualification criteria in Section 3. The Director may:
- **Approve** — entity is accepted as Constitutional Memory; agent may proceed to write
- **Reclassify as Operational** — entity is valid but does not meet constitutional threshold; agent writes to Operational tier instead
- **Reject** — entity does not represent a valid memory candidate; no write occurs
- **Decompose** — entity bundles multiple facts; Director specifies the decomposition; each atomic entity is reviewed separately

**Step 3 — Approved Write**
After Director approval, the writing agent executes the `create_entities` and `add_observations` MCP calls. The write must include an observation recording:
- Approval date
- Source document and article/section
- Tier classification: `constitutional_invariant`

**Step 4 — No Retroactive Promotion**
An Operational Memory entity may not be retroactively promoted to Constitutional Memory without re-running the full gate procedure from Step 1. Existing operational entities are not grandfathered into constitutional tier.

### Default Behavior on Uncertainty

If an agent is uncertain whether a candidate qualifies as Constitutional or Operational, the default classification is **Operational**. The candidate is still flagged in CSO Section 9 for Director review. This prevents unauthorized constitutional writes while ensuring potentially valuable knowledge is not lost.

---

## Section 5 — Canonical MCP Entity Schema Format

All MCP memory entities written within the Delta Ecosystem must conform to the following schema. Agents may not invent alternative structures.

### 5.1 Entity Structure

```json
{
  "name": "<entity_name>",
  "entityType": "<entity_type>",
  "observations": [
    "<observation_1>",
    "<observation_2>"
  ]
}
```

**Field Definitions:**

| Field | Type | Rules |
|---|---|---|
| `name` | string | `snake_case` preferred; `camelCase` permitted for compound technical terms; no spaces; no special characters except underscore; globally unique within the memory graph |
| `entityType` | string | Must be from the approved type taxonomy (Section 5.2) |
| `observations` | string[] | Each string is one atomic fact; minimum 1; no maximum but prefer granular over bundled |

### 5.2 Approved Entity Type Taxonomy

| entityType | Tier | Use |
|---|---|---|
| `constitutional_invariant` | Constitutional | A governance truth derived from the Constitution or Protocol |
| `governance_principle` | Constitutional | A declared principle that shapes ecosystem behavior |
| `agent_role` | Operational | Role definition, boundary, or constraint for a specific agent |
| `document_type` | Operational | Classification and behavior of a Delta document type |
| `routing_pattern` | Operational | Skill routing decision, platform constraint, or environment rule |
| `project_lesson` | Operational | Retrospective knowledge from a completed project or WO cycle |
| `implementation_lesson` | Operational | CDC-level technical knowledge about code patterns or environment behavior |
| `environment_config` | Operational | System path, tool configuration, or runtime environment fact |
| `governance_convention` | Operational | Operational convention derived from agent rules or protocol |

No entity types outside this taxonomy are permitted. If a new type is needed, it must be proposed to the Director and added to this taxonomy before use.

### 5.3 Relation Structure

```json
{
  "from": "<entity_name>",
  "to": "<entity_name>",
  "relationType": "<active_voice_verb>"
}
```

**Relation rules:**
- `relationType` must be written in active voice (e.g., `creates`, `requires`, `validates`, `overrides`, `references`, `constrains`)
- Passive constructions are forbidden (e.g., `is_created_by`, `is_required_by`)
- Relations must be directional and semantically accurate — the `from` entity performs the action on the `to` entity
- Do not create relations between entities that have no direct authority or workflow dependency

### 5.4 Observation Standards

Each observation string must satisfy all of the following:

1. **One fact per observation.** No compound facts. No "and" or "but" linking two distinct claims.
2. **Present tense, declarative.** Observations state what is true now, not what was once true or might be true.
3. **No relative references.** Do not use "this," "the above," "the following," or any term that only makes sense in document context.
4. **No version numbers in observation text** unless the version number is itself the invariant being recorded (rare).
5. **No document filenames in observation text.** Reference roles and authority tiers, not specific filenames.
6. **Standalone intelligibility.** An observation must be fully interpretable by an agent reading it without additional context — it cannot depend on other observations in the same entity to be meaningful.

**Valid observation examples:**
- `"The Director holds final fallback authority in all governance failures."`
- `"An agent may not switch operational roles mid-session."`
- `"Operational Memory entities derived from CDC execution are invalidated on major STRAT version increment."`

**Invalid observation examples:**
- `"The Director holds final authority and no agent can override this."` ← compound fact; split into two
- `"As described above, CDC must follow WO boundaries."` ← relative reference
- `"Per DELTA_PROTOCOL.md Section 7, runtime state is authoritative."` ← filename reference; reference the role/concept instead
- `"This entity was added in v1.0."` ← version number with no invariant value

### 5.5 Naming Conventions

| Element | Convention | Example |
|---|---|---|
| Entity names | `snake_case` | `director_override_doctrine`, `constitutional_memory_gate` |
| Compound technical names | `camelCase` permitted | `C#_Wrapper`, `postgresConnection` |
| Relation types | lowercase `snake_case` | `overrides`, `requires`, `constrains` |
| Entity type values | `snake_case` | `constitutional_invariant`, `routing_pattern` |

### 5.6 Prohibited Patterns

The following patterns are explicitly forbidden in the Delta MCP memory graph:

| Pattern | Why Forbidden |
|---|---|
| Storing raw document blobs as observations | Violates atomicity; creates drift risk when source doc changes |
| Using a single entity to represent multiple concerns | Violates Single Source of Truth (Constitution Article V) |
| Writing Ephemeral Cognitive Memory to the graph | Violates Transient Cognition Doctrine (Constitution Article VI) |
| Writing Constitutional Memory without Director approval | Violates the Director approval gate (Section 4 of this document) |
| Using undeclared entity types | Prevents consistent querying and classification |
| Passive-voice relation types | Reduces graph readability and bi-directional clarity |
| Creating duplicate entities for the same concern | Creates competing authority claims within the graph |
| Retroactive tier promotion without re-running the gate | Circumvents constitutional write authority controls |
| Writing project-specific memory to `~/.delta/memory_delta.jsonl` | Leaks project context across projects and violates Delta memory isolation |
| Using Memory MCP as general assistant memory | Mixes non-Delta facts with governance memory and weakens source-of-truth boundaries |
| Storing CSO content wholesale in Memory MCP | Duplicates project/session artifacts and creates drift from linked CSO |

---

## Section 6 — Context Bootstrap & Handoff Obligations

These obligations apply to all agents operating in GMN, ANT, or CDC roles.

### Session Bootstrap (Start of Session)

Before making any design, planning, or implementation decisions, every agent must:

1. Query the memory graph using `search_nodes` or `read_graph` to retrieve:
   - Constitutional Memory entities relevant to the current task domain
   - Operational Memory entities for Delta ecosystem behavior, host setup, path conventions, and stable environment quirks
2. Apply retrieved invariants as non-negotiable constraints on all session decisions
3. Flag any Constitutional Memory entity that appears stale or inconsistent with current governance documents — do not silently act on potentially outdated constitutional invariants
4. Retrieve project-specific context from `delta session bootstrap`, artifact status commands, linked CSOs, and governed project documents

### Session Handoff (End of Session)

Before closing a session, every agent must:

1. Review CSO Section 9 for Memory Candidates only when the candidate is ecosystem-level
2. Classify each candidate against the 3-tier classification (Section 1) and 5 qualification criteria (Section 3)
3. Record Constitutional Memory Candidates with full citation and gate justification for Director review
4. Execute approved ecosystem-level Operational Memory writes via `create_entities` and `add_observations`
5. Leave project-specific candidates in CSO/project artifacts and rely on linked CSO discovery
6. Do not write any Constitutional Memory entity in this step — those require Director approval per Section 4

---

## Section 7 — Enforcement & Compliance

1. Memory tier violations discovered during audit must be flagged to the Director for remediation
2. An entity written to the wrong tier must be deleted and re-written to the correct tier after Director review — it may not be silently reclassified in place
3. Any agent that cannot locate a Constitutional Memory entity that should exist must escalate to the Director rather than reconstructing it from inference
4. The memory graph is not a scratchpad — writes are semi-permanent and have governance weight; default to under-writing rather than over-writing when uncertain
5. This doctrine is the Single Source of Truth for memory governance within the Delta Ecosystem. Agent rule files may reference this document but may not redefine its classification rules

---

*This document is subordinate to the Delta Constitution and the operational governance protocol. For constitutional invariants and supreme authority principles, refer to the Delta Constitution. For operational workflow standards, refer to the operational governance protocol.*

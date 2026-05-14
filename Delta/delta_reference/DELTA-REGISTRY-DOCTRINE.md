# Semantic Governance Registry Doctrine

**Delta Ecosystem — Document Navigation Governance**
**Authority Tier:** Operational Doctrine (subordinate to the Delta Constitution and the operational governance protocol)
**Owner:** Director

> This document defines the schema, vocabulary, entropy rules, and update ownership for the Delta Semantic Governance Registry. The Registry is navigational infrastructure — it tells agents which document to read and when. It is not a knowledge store, not a semantic layer, and not a summary system. In any conflict between this document and the operational governance protocol or the Delta Constitution, those documents prevail.

---

## Section 1 — Purpose & Scope

### What the Registry IS

The Registry is a machine-readable index of all ecosystem governance documents. Its sole function is **document navigation**: given an operational trigger, the Registry resolves which document (and optionally which section) is relevant — enabling agents to read targeted content rather than scanning the full document landscape.

The Registry is **navigational infrastructure**. It operates between the MCP Memory Layer (distilled facts) and the Raw Governance Documents (full authority). When MCP memory is insufficient for a decision, the Registry routes the agent to the exact document and section needed.

### What the Registry is NOT

The Registry is not:

- A knowledge store — it contains no facts about governance
- A semantic layer — it carries no interpretation, summaries, or descriptions
- A second table of contents — section entries contain triggers, not content descriptions
- An MCP memory substitute — it routes to documents; it does not replace them
- A prose document — no narrative text belongs in the registry JSON

**Violation of these constraints constitutes registry entropy.** A registry with prose fields is no longer navigational infrastructure — it is a governance document that drifts from its sources.

### The 4-Layer Cognition Architecture

The Registry occupies Layer 3 in the Delta cognition stack:

```
Layer 1 — Runtime Metadata      CLI operational state; active WO, mode, flags
Layer 2 — MCP Memory Graph      Distilled invariants, routing patterns, lessons
Layer 3 — Registry              Document navigation — what to read, when, which section
Layer 4 — Raw Governance Docs   Full authority, nuance, rationale, conditional doctrine
```

An agent escalates through layers as needed. Layer 3 is consulted when Layer 2 (MCP) is insufficient. Layer 4 is consulted when the Registry points to a specific document.

---

## Section 2 — Registry Schema Specification

### 2.1 Top-Level Structure

```json
{
  "schema_version": "<semver>",
  "documents": [ ]
}
```

`schema_version` follows semantic versioning. It increments when the schema itself changes (new fields, removed fields, vocabulary changes). It does not increment when a document entry is added or updated.

### 2.2 Document Entry Schema

Each entry in the `documents` array must conform to:

```json
{
  "document_id": "<identifier>",
  "file": "<relative_path>",
  "authority_tier": "<tier_value>",
  "owner": "<owner_value>",
  "lifecycle": "<lifecycle_value>",
  "mandatory_when": ["<trigger>"],
  "sections": {
    "<section_id>": { "trigger": "<trigger>" }
  }
}
```

**Field definitions:**

| Field | Type | Required | Rules |
|---|---|---|---|
| `document_id` | string | yes | `snake_case`; unique across all entries; stable identifier that survives file renames |
| `file` | string | yes | Relative path from ecosystem root; updated if file is renamed |
| `authority_tier` | string | yes | Must be from the Authority Tier Vocabulary (Section 3.1) |
| `owner` | string | yes | Must be from the Owner Vocabulary (Section 3.2) |
| `lifecycle` | string | yes | Must be from the Lifecycle Vocabulary (Section 3.3) |
| `mandatory_when` | string[] | yes | Each value must be from the Trigger Vocabulary (Section 3.4); minimum 1 |
| `sections` | object | no | Keys are section identifiers (article numbers, section numbers, headings); values are `{ "trigger": "<trigger>" }` only |

**Forbidden fields:**
- `description`, `purpose`, `summary`, `notes`, `keywords` — these carry prose and cause drift
- Any field not listed in this schema

### 2.3 Section Entry Schema

```json
"<section_id>": { "trigger": "<trigger>" }
```

- `section_id`: The section's canonical identifier (e.g., `"IV"`, `"S3"`, `"workflow_sequence"`). Must match the actual heading identifier in the document.
- `trigger`: Exactly one value from the Trigger Vocabulary. The trigger represents the operational condition under which this specific section (not the whole document) is the resolution target.

**Only sections that may be read in isolation require an entry.** If a document is always read in full, `sections` may be omitted or left empty.

---

## Section 3 — Closed Vocabulary Taxonomy

All vocabulary values are closed enumerations. Free-text values are forbidden in any registry field. If a required value does not exist in the vocabulary, a vocabulary extension request must be submitted per Section 5 before the value may be used.

### 3.1 Authority Tier Vocabulary

| Value | Meaning |
|---|---|
| `constitutional` | Supreme authority — Constitution only |
| `operational_governance` | Primary operational authority — Protocol |
| `operational_doctrine` | Specialist doctrine subordinate to Protocol |
| `agent_rule` | Agent-specific behavioral constraints |
| `agent_config` | Model-specific configuration and context |
| `ecosystem_knowledge` | NLM knowledge modules — living reference |
| `ecosystem_log` | CSO and immutable session logs |

### 3.2 Owner Vocabulary

| Value | Meaning |
|---|---|
| `director` | Director owns and is the sole amendment authority |
| `gmn` | GMN is primary author; Director approval required for changes |
| `ant` | ANT is primary author; Director approval required for changes |
| `cdc` | CDC is primary author; Director approval required for changes |
| `nlm` | NLM constructs; Director approval required for changes |
| `all_agents` | Any agent may contribute; Director approval for structural changes |

### 3.3 Lifecycle Vocabulary

| Value | Meaning |
|---|---|
| `permanent` | Never expires; changes only on constitutional amendment or Director decision |
| `versioned` | Tied to a version cycle; may be superseded by a newer version |
| `living` | Updated in place without versioning (e.g., KNOW documents) |
| `immutable_log` | Timestamp-based; never overwritten after creation |

### 3.4 Trigger Vocabulary

Triggers are the atomic routing primitives for the Registry. They represent operational conditions that require document consultation. All triggers are lowercase `snake_case`.

| Trigger | Meaning |
|---|---|
| `session_bootstrap` | Start of any operational role session |
| `governance_conflict` | Two governance documents or principles appear to conflict |
| `constitutional_amendment` | Constitution is being amended |
| `director_override` | Director declares an intentional protocol deviation |
| `authority_hierarchy_query` | Agent needs to resolve which tier governs a decision |
| `runtime_authority_conflict` | Runtime state contradicts a governance document |
| `role_boundary_violation` | Agent attempts an action outside its authority domain |
| `memory_write_constitutional` | Agent intends to write a Constitutional Memory entity |
| `memory_classification_query` | Agent needs to classify a memory candidate into a tier |
| `document_navigation` | Agent needs to determine which documents apply to the current task |
| `escalation_required` | Lower authority tier failed or is unavailable; escalating upward |
| `lifecycle_conflict` | Artifact lifecycle classification is disputed |
| `skill_routing_conflict` | Skill routing produces a contradiction or ambiguity |
| `strat_invalidation` | Implementation contradicts approved strategy |
| `experimental_authorization` | Director intends a Temporary Experimental Authorization against a constitutional principle |
| `registry_update` | Registry itself is being updated — schema or vocabulary change |

---

## Section 4 — Entropy Prevention Rules

These rules are non-negotiable. A registry that violates them has entered entropy state.

1. **No prose fields.** `description`, `purpose`, `summary`, `notes`, `keywords` are forbidden at all levels of the registry JSON.

2. **No free-text values.** Every string value in a non-path field must come from an approved vocabulary. Paths (`file` field) are exempt.

3. **No content summaries in section entries.** A section entry contains exactly one field: `trigger`. It does not describe what the section contains.

4. **No MCP entity references.** The registry must not contain MCP entity names or MCP node identifiers. The registry routes to documents; MCP routes to facts. These are separate systems with a one-directional dependency (see Section 6).

5. **One trigger per section entry.** A section maps to exactly one trigger. If a section is relevant for multiple triggers, list the document under multiple `mandatory_when` triggers — do not add multiple triggers per section entry.

6. **Document ID stability.** Once assigned, a `document_id` must not be changed even if the file is renamed. File renames update the `file` field only. This ensures MCP entities that reference `document_id` remain valid.

7. **No duplicate document entries.** One governance concern — one document entry. A single document may not appear twice with different `document_id` values.

---

## Section 5 — Trigger Vocabulary Governance Rule

The trigger vocabulary is intentionally minimal. Its value comes from finiteness — a small, well-understood set of conditions that all agents interpret identically.

### Anti-Proliferation Rule

**A new trigger may only be added if no existing trigger, or compositional use of existing triggers, can route the required behavior.**

Before proposing a new trigger, the proposing agent must demonstrate:
1. Which existing trigger was evaluated as a candidate
2. Why the existing trigger is semantically insufficient (not merely imprecise)
3. That the new trigger does not overlap with any existing trigger's meaning

If two triggers are discovered to be synonymous, the less-used one must be removed and registry entries must be migrated.

### Compositional Routing

For situations that require reading multiple documents under multiple conditions, the correct approach is to list multiple `mandatory_when` triggers on a document entry — not to create a new compound trigger that bundles two conditions. Triggers are primitives, not sentences.

**Example of wrong approach (creates new trigger):**
```
"memory_write_during_constitutional_conflict"  ← compound; forbidden
```

**Example of correct approach (uses composition):**
```json
"mandatory_when": ["memory_write_constitutional", "governance_conflict"]
```

### Vocabulary Extension Process

1. Agent identifies a navigation scenario not covered by existing triggers
2. Agent records the proposed trigger in CSO Section 9 with justification against the anti-proliferation rule
3. Director reviews and approves or rejects
4. Approved triggers are added to this doctrine first, then the registry is updated
5. The doctrine is the Single Source of Truth for the trigger vocabulary — not the registry JSON

---

## Section 6 — MCP Linkage Rules

The Registry and the MCP Memory Graph are separate systems. Their dependency direction is strictly one-way:

```
MCP Entity
    ↓ (references)
Registry Document ID
    ↓ (routes to)
Raw Governance Document
```

**The Registry must never reference MCP entity names or node IDs.**

### Why This Direction

The Registry is stable infrastructure. The MCP graph is mutable operational memory. Infrastructure must not depend on volatile memory topology. If an MCP entity is renamed, split, or invalidated, the Registry must not break.

### How MCP Entities Reference the Registry

When a Constitutional or Operational Memory entity is created in MCP, it may include an observation recording its source document using the Registry's `document_id`:

```
"Derived from governance document: delta_constitution, Article IV."
```

This is a human-readable reference, not a programmatic link. It enables traceability without creating a hard dependency.

### What MCP and Registry Each Own

| Concern | Owner |
|---|---|
| Which document contains the answer | Registry |
| What the answer is | MCP Memory or Raw Document |
| When to consult a specific document | Registry (via trigger) |
| Distilled facts from that document | MCP Memory |
| Full rationale and nuance | Raw Document |

---

## Section 7 — Update Ownership

| Change Type | Who Updates | Gate |
|---|---|---|
| New governance document added to ecosystem | GMN (initiates) | Director approval |
| Existing document renamed or moved | Owner of that document | Director notification |
| New trigger added to vocabulary | GMN (initiates) | Director approval via Section 5 process |
| Trigger removed or merged | GMN (initiates) | Director approval; all registry entries must be migrated |
| Section entry added or updated | Owner of that document | Director notification |
| Schema version incremented | GMN (initiates) | Director approval |
| Authority tier or vocabulary updated | GMN (initiates) | Director approval |

**The Registry must be updated in the same action as the change that triggers it.** A new governance document that is not registered is a navigation gap. A renamed file that is not updated in the registry is a broken path.

---

## Section 8 — Enforcement

1. Agents operating in GMN, ANT, or CDC roles must consult the Registry at session bootstrap when MCP memory is insufficient to resolve the current task context
2. An agent that bypasses the Registry and performs a full document scan when a Registry-navigated partial read would suffice is operating inefficiently — this is not a governance violation but should be noted in CSO Section 9 as a context economy observation
3. A registry entry with a broken `file` path is a P1 maintenance issue — it must be resolved before the next operational session that depends on that document
4. Agents must not modify the registry JSON directly — all updates go through the update ownership process in Section 7
5. This doctrine is the Single Source of Truth for registry governance — the registry JSON is its operational output, not an independent authority

---

*This document is subordinate to the Delta Constitution and the operational governance protocol. For constitutional invariants, refer to the Delta Constitution. For operational workflow standards, refer to the operational governance protocol.*

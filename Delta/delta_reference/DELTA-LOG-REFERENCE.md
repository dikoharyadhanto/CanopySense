# Lightweight Log Reference Semantics

**Delta Ecosystem — Log Reference & Weak Linking Governance**
**Authority Tier:** Operational Doctrine (subordinate to the Delta Constitution and the operational governance protocol)
**Owner:** Director

> This document defines the semantics for referencing other artifacts from within log entries and CSO documents. It establishes the weak reference model, prohibits hard dependency creation in logs, and defines what constitutes graph over-engineering in the MCP memory context. In any conflict between this document and the operational governance protocol or the Delta Constitution, those documents prevail.

---

## Section 1 — The Reference Problem

As Delta projects grow, log artifacts (primarily CSOs) accumulate references to other artifacts — the WO being executed, the STRAT being followed, the MCP entities relevant to the session. Without a defined reference semantics, two failure modes emerge:

**Failure Mode A — Fragile Hard References:** Log artifacts create strong programmatic links to specific document versions and MCP entity names. When those documents are superseded or entities renamed, the logs break or point to stale authority. Agents following broken references get misleading governance signals.

**Failure Mode B — Graph Over-Engineering:** MCP memory accumulates a dense web of relations between entities in an attempt to model every inter-artifact dependency. The graph becomes expensive to query, difficult to maintain, and produces ambiguous results when relations become stale. The graph stops being a fast-lookup tool and becomes its own governance burden.

This document defines the **weak reference model** to prevent both failure modes.

---

## Section 2 — Weak vs. Strong References

### 2.1 Strong Reference

A **strong reference** is a dependency that must remain valid for the referencing artifact to function correctly. Breaking a strong reference breaks the referencing artifact.

**Strong references are appropriate for:**
- Document inheritance chains (IMPL references WO — the WO is required for the IMPL to have governance standing)
- MCP relations between entities that have a direct authority dependency (e.g., an `implementation_lesson` entity that `derived_from` a `routing_pattern` entity)
- Registry entries pointing to document files

**Strong references are NOT appropriate for:**
- Log artifacts referencing governance documents
- CSO entries referencing specific document versions
- MCP entities referencing other entities that merely co-occurred in the same session

### 2.2 Weak Reference

A **weak reference** is a navigational hint — a pointer that says "this artifact was relevant when this log was created." It does not assert ongoing dependency. If the target is renamed, superseded, or archived, the weak reference becomes a historical annotation, not a broken link.

**Weak references are used with the `related_to` semantic.**

**Weak references are appropriate for:**
- CSO documents referencing the WO, STRAT, or session context active at the time of writing
- MCP log-type entities referencing the session or project they were created in
- Any reference from a Tier L (immutable log) artifact to a Tier 1/2/3 artifact
- Any reference from a transient artifact (before it decays) to a persistent artifact

---

## Section 3 — The `related_to` Semantic

### 3.1 Definition

`related_to` is the canonical weak reference marker in the Delta Ecosystem. It means:

> "This artifact was associated with the referenced artifact at the time of its creation. No ongoing dependency is asserted. The referenced artifact's current state does not affect this artifact's validity."

### 3.2 Usage in CSO Documents

Within a CSO document, references to governance artifacts use the following pattern:

```
Related WO: related_to ANT-WO-{ID}-{VERSION}
Related STRAT: related_to GMN-STRAT-{ID}-{VERSION}
Related MCP Session Context: related_to [session entity name if applicable]
```

The `related_to` prefix signals to any agent reading the CSO that these are historical annotations, not active authority links.

### 3.3 Usage in MCP Relations

When creating a relation in the MCP memory graph from a log-type entity to a governance entity, use `related_to` as the relation type:

```json
{
  "from": "session_20260509_ant_wo_003",
  "to": "routing_pattern_supabase_edge",
  "relationType": "related_to"
}
```

This contrasts with strong relation types (`derived_from`, `constrains`, `requires`) which assert ongoing dependency.

### 3.4 What `related_to` Does NOT Mean

- It does not assert that the referenced artifact is still valid
- It does not assert that the referenced artifact governs the current session
- It does not create an obligation to update the log if the referenced artifact changes
- It does not give the log artifact any authority derived from the referenced artifact

---

## Section 4 — MCP Graph Lean Doctrine

Over-engineering the MCP graph creates the same problem it was designed to solve: high query cost, ambiguous results, and maintenance burden. These rules keep the graph lean and fast.

### 4.1 Relation Sparsity Rule

Only create a relation between two entities if the relation represents a **direct, load-bearing dependency** that an agent would need to navigate at session bootstrap or during active decision-making. Relations that merely document historical co-occurrence or organizational grouping must not be created.

**Create a relation when:**
- An entity's validity depends on another entity (e.g., an `implementation_lesson` that `derived_from` a specific `routing_pattern`)
- An agent navigating to one entity needs to be aware of the other to make a correct decision
- The relation would change an agent's behavior if it were absent

**Do not create a relation when:**
- Two entities were mentioned in the same session (co-occurrence is not dependency)
- The relation merely reflects project organization ("this entity belongs to project X")
- The relation would only ever be traversed in retrospective audit, not in active decision-making

### 4.2 Log Entity Isolation Rule

Immutable log entities (CSO-derived session entities, if persisted) must not be connected to the main governance entity graph via strong relations. They are reference archives, not authority nodes.

**Correct:** A log entity uses `related_to` to reference governance entities it was created alongside.
**Incorrect:** A governance entity uses `requires` or `derived_from` to reference a log entity.

The governance graph flows downward (Constitution → Protocol → Rules → Decisions). Logs sit outside this flow. They observe it; they do not participate in it.

### 4.3 Relation Lifecycle Parity Rule

A relation between two entities must not outlive the validity of either entity. When an entity enters authority decay (per DELTA-LIFECYCLE-RETENTION.md Section 4), all strong relations from or to that entity must be reviewed. Relations to decayed entities must be either removed or converted to `related_to` weak references.

This prevents the graph from accumulating stale strong dependencies that mislead agents during session bootstrap.

### 4.4 Maximum Relation Depth

When querying the MCP graph for session bootstrap context, agents must not traverse more than **2 hops** from the query entry point for operational decisions. Deep graph traversal at bootstrap is a symptom of over-engineering — it means the graph topology has replaced what should be direct document reads.

If a decision requires traversing more than 2 hops, the correct action is to escalate to reading the relevant governance document directly via the Registry, not to extend the traversal depth.

---

## Section 5 — CSO Reference Standards

The following standards apply to all CSO documents when referencing other artifacts.

### 5.1 Document References

All document references in a CSO use `related_to` semantics:

```
## Session Context

- Working WO: related_to [WO document name]
- Governing STRAT: related_to [STRAT document name]
- Active CDC-IMPL: related_to [IMPL document name]
```

### 5.2 MCP Entity References

When a CSO Section 9 candidate references an existing MCP entity (e.g., a new observation being added to an existing entity), the reference is written as:

```
Target entity: [entity_name]
Relation: add_observation_to
```

This is a write instruction, not a dependency declaration. It does not create a persistent relation between the CSO and the MCP entity.

### 5.3 Cross-CSO References

One CSO must never reference another CSO as an authority source. CSOs are immutable logs — they may be read for historical context but may not chain authority. If information from a prior CSO is relevant to the current session, the correct action is to locate the formal governance document or MCP entity that absorbed that information, and reference that instead.

**Correct:** "The routing pattern confirmed in prior sessions is persisted as MCP entity `routing_pattern_supabase_edge` — consult that entity."
**Incorrect:** "Per ANT-CSO-003-202604281037, the routing pattern is X." ← references a log as authority

---

## Section 5B — Audit Record Reference Semantics

Audit records (`audit_records` in `progress.json`) participate in the reference model as follows:

### 5B.1 Audit Record → CSO Reference

An audit record may reference a CSO via the `cso_reference` field:

```
delta audit record --wo ANT-WO-008-v0.1.md --actor GPT --conditional --cso CSO-WO-008-v0.1.md
```

This creates a **weak `related_to` reference** from the audit record to the CSO. The CSO provides context for the verdict but does not affect the verdict's validity. If the CSO is later superseded, the audit record's verdict stands unchanged — the `cso_reference` becomes a historical annotation.

### 5B.2 CSO → Audit Record Reference

When `--cso` is specified on an audit record, the audit_id is auto-linked to the CSO's `linked_audit_records` array. This is also a weak reference — the CSO links to its associated audit records for traceability, not for authority.

### 5B.3 Audit Record → Artifact Reference

An audit record's `artifact_path` field is a **strong reference** — the artifact must exist for the audit record to be meaningful. However, the audit record does not create a dependency from the artifact to the audit record. The artifact's governance standing is independent of its audit records.

### 5B.4 Audit Record as Reference Target

Lock gates (`delta strat lock`, `delta wo lock`, `delta str lock`) consult audit records as reference targets — they read `satisfies_lock_gate` to determine if the gate is unlocked. This is a read-time check, not a persistent relation. The lock gate does not create a reference from the document to the audit record.

### 5B.5 CSO in Audit: Not an Actor

CSO is never the `actor` in an audit record. CSO is a document, not a verdict issuer. The only valid `actor` values are: `Director`, `GPT`, `PPX`, `ANT`, `CDC`.

---

## Section 6 — Prohibited Reference Patterns

| Pattern | Why Prohibited |
|---|---|
| Strong relation from log entity to governance entity | Logs must not participate in the governance authority graph |
| CSO referencing another CSO as authority | Log-to-log authority chains create unverifiable dependency trails |
| MCP relation created for co-occurrence (same session, same project) | Relation entropy — co-occurrence is not dependency |
| Document reference in a log without `related_to` marker | Implies authority dependency that does not exist |
| Graph traversal beyond 2 hops for bootstrap decisions | Symptom of over-engineering — escalate to direct document read |
| Relation to a decayed entity without converting to `related_to` | Stale strong dependency misleads future agents |
| Governance entity created that `requires` a log entity | Inverts the correct governance flow direction |

---

*This document is subordinate to the Delta Constitution and the operational governance protocol. For constitutional invariants, refer to the Delta Constitution. For operational workflow standards, refer to the operational governance protocol.*

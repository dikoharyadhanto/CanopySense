# Delta Constitutional Sync Doctrine

## §1 — Purpose & The Constitutional Drift Problem

MCP constitutional memory is populated from governance documents — the Constitution, Protocol, and doctrine files. Over time, governance documents can be amended while MCP memory entities remain unchanged. This creates a divergence between what the memory graph claims as invariant and what the governing documents actually say.

This is **constitutional drift**: agents making governance decisions based on stale memory observations that no longer accurately reflect the authoritative source.

Constitutional drift is silent by default. An agent that does not check its memory against the current document will confidently operate from a superseded rule. The damage is not immediate — it accumulates across sessions until a decision is made that contradicts current governance.

This doctrine defines:
- When synchronization must occur (§2)
- How staleness is detected (§3)
- How outdated memory is safely invalidated (§4)
- The `delta sync constitution` command interface (§5)
- How governance conflicts are detected and escalated (§6)

---

## §2 — Sync Trigger Conditions

### §2.1 — Mandatory Triggers

Synchronization is obligatory when any of the following occur. No agent discretion applies.

| Trigger | Scope | Source |
| ------- | ----- | ------ |
| **Constitutional amendment** | Full constitutional memory re-validation | Constitution Article VIII — any amendment recorded in the amendment log triggers re-validation of all invariants sourced from the amended articles |
| **Major STRAT version transition** | All Operational Memory entities sourced from prior STRAT | GMN-RULE.md Lifecycle & Artifact Governance — `strat_locked = true` on new major version requires re-validation |
| **Governance document update at bootstrap** | Alert only — Director decides scope | If any governance document has a modified timestamp newer than the last sync checkpoint in `progress.json`, CLI surfaces a sync alert at `delta session bootstrap` |
| **Director explicit sync** | Director-declared scope | `delta sync constitution` invoked directly |

### §2.2 — Conditional Triggers

Synchronization is recommended. Director decides whether to invoke.

| Trigger | Condition |
| ------- | --------- |
| **Agent-reported discrepancy** | During execution, an agent observes a memory invariant contradicting a loaded governance document. Flagged in CSO §9. Director reviews and decides whether to invoke sync. |
| **Pre-write consistency check** | Before writing a new constitutional invariant, the Director approval gate (Memory Doctrine §4) includes a check for existing invariants covering the same domain. Point-in-time check, not a full sync. |

### §2.3 — Anti-Triggers

Sync is NOT triggered by:
- Operational memory updates (project lessons, routing patterns) — different memory tier
- Protocol-level Director Override — operational instrument, not constitutional
- CDC implementation events
- Routine session bootstrap with no governance document changes

---

## §3 — Staleness Detection Logic

An invariant is **stale** when any of the following conditions is true. Staleness is binary — no partial-stale state exists.

| Staleness Condition | Detection Method |
| ------------------- | ---------------- |
| **Source document amended since invariant was written** | Compare invariant `created_at` timestamp against amendment log entry timestamp for the invariant's source article/section |
| **Invariant text contradicts current source text** | Direct text comparison: invariant claim vs current text of the resolved source section |
| **Source document version superseded** | Invariant references a document version that is now `SUPERSEDED` in `progress.json` `document_states` |
| **Amendment scope covers invariant domain** | Amendment log declares a governance domain that subsumes the invariant's classification domain |
| **Invariant references an invalidated entity** | Invariant relation targets an entity that has itself been hard-invalidated |

### §3.1 — Stale ≠ Incorrect

A stale invariant may still be factually correct after an amendment. Staleness means the invariant has not been re-validated since its source changed — not that it is wrong. This distinction governs the invalidation mode chosen in §4.

### §3.2 — Conflict vs Staleness

| State | Meaning | Urgency |
| ----- | ------- | ------- |
| **Stale** | Not re-validated since source changed — may or may not still be correct | High — re-validate before next use |
| **Conflict** | Actively contradicts current source text | Critical — must not be used; escalate immediately |

Both conditions are detected by `delta sync constitution`. Conflicts require immediate escalation (§6). Stale invariants require re-validation (§4).

---

## §4 — Memory Invalidation Protocol

Invalidation is the process of retiring a stale or conflicted constitutional memory invariant. Invalidation **never deletes** — MCP observations are append-only. Supersession is the only valid mechanism.

### §4.1 — Two Invalidation Modes

**Soft Invalidation** (default for stale, pending re-validation):

Append a supersession observation to the entity:
```
"Soft-invalidated: stale as of {ISO8601}. Pending re-validation against {document} {article/section}. Do not use for governance decisions until re-validated."
```
The entity remains in the graph but is marked stale. Agents must not rely on a soft-invalidated invariant for governance decisions — fall back to current document text. Used when Director review is pending.

**Hard Invalidation** (for confirmed stale or conflicted, replacement ready):

1. Director approves the re-validated replacement invariant text
2. Write the replacement observation via Memory Doctrine §4 approval gate
3. Append an explicit supersession record to the old entity:
```
"Hard-invalidated: superseded by re-validated observation {index} written {ISO8601}. Source: {document} {article/section} as amended {date}."
```
The original observation is preserved as audit record. Only the supersession observation is new.

### §4.2 — Invalidation Protocol Steps

```
Sync Report identifies stale/conflicted invariant(s)
        ↓
Director reviews Sync Report
        ↓
Director decision per invariant:
  ├── Re-validate (text still correct after amendment) → Hard Invalidation + new write
  ├── Flag pending (cannot re-validate yet) → Soft Invalidation
  └── Conflict requiring amendment revision → Constitution Article VIII process
        ↓
Invalidation event recorded in CSO §9 (mandatory)
        ↓
If hard invalidation: new invariant follows Memory Doctrine §4 approval gate
```

### §4.3 — Safety Rules

1. Invalidation may never delete MCP entities or observations — append-only graph
2. Hard invalidation requires Director approval gate identical to new constitutional write (Memory Doctrine §4)
3. Soft invalidation does not require full Director approval — Director review of Sync Report is sufficient
4. A soft-invalidated invariant must not be cited as authoritative by any agent
5. The invalidation event (both modes) must be recorded in CSO §9 before session close

---

## §5 — `delta sync constitution` Command Interface

This section specifies the conceptual interface for implementation by ANT/CDC in Phase 6.

### §5.1 — Command Signature

```
delta sync constitution [--scope=full|articles|operational] [--dry-run]
```

**Flags:**

| Flag | Default | Behavior |
| ---- | ------- | -------- |
| `--scope=full` | yes | Validate all constitutional memory invariants |
| `--scope=articles` | no | Validate only invariants sourced from Constitution articles |
| `--scope=operational` | no | Re-validate Operational Memory entities against current STRAT |
| `--dry-run` | no | Produce Sync Report only — no invalidation writes permitted |

`--dry-run` is always safe. It is the recommended first invocation when sync has not been run recently.

### §5.2 — Execution Sequence

1. Load all MCP entities of type `constitutional_invariant` from memory graph
2. For each invariant: resolve `source_document` and `source_section` fields
3. Load current text of the resolved source section from filesystem
4. Apply staleness detection logic (§3) to each invariant
5. Classify each invariant: `valid`, `stale`, or `conflict`
6. Produce Sync Report (§5.3)
7. If `--dry-run`: output report, terminate — no writes
8. If not `--dry-run`: present Sync Report to Director → await review before any invalidation write

### §5.3 — Sync Report Format

```
DELTA CONSTITUTIONAL SYNC REPORT
Generated:  {ISO8601}
Scope:      {full | articles | operational}
Triggered:  {amendment | strat_transition | bootstrap_alert | director_explicit}

SUMMARY
  Total invariants scanned:  N
  Valid:                     N
  Stale:                     N
  Conflict:                  N

STALE INVARIANTS
  [{entity_name}]
    Source:               {document} {section}
    Staleness condition:  {condition from §3}
    Last validated:       {ISO8601}
    Recommended action:   soft_invalidate | hard_invalidate_with_revalidation

CONFLICTS
  [{entity_name}]
    Source:               {document} {section}
    Invariant claims:     "{invariant_text}"
    Current source says:  "{current_text}"
    Recommended action:   hard_invalidate_with_revalidation + Director review

VALID INVARIANTS
  [{entity_name}] — valid as of {ISO8601}
```

### §5.4 — Related Sync Commands

**`delta sync memory`** — Operational Memory variant. Same sequence but targets `operational` tier entities. Lower approval barrier: operational memory does not require Director approval for routine re-validation, only for new writes.

**`delta sync registry`** — Validates `DELTA-REGISTRY.json` against current filesystem state: document existence, schema conformance, trigger vocabulary compliance. Fully automated — no Director approval required for the validation itself.

### §5.5 — Sync Checkpoint

After every successful `delta sync constitution` run (not dry-run), the CLI writes a sync checkpoint to `progress.json`:

```json
{
  "last_constitutional_sync": "{ISO8601}",
  "last_sync_result": "clean | stale_found | conflict_found",
  "last_sync_scope": "full | articles | operational"
}
```

This checkpoint is the reference point for bootstrap staleness detection (§2.1 mandatory trigger 3).

---

## §6 — Governance-Conflict Detection and Escalation Flow

A governance conflict is a condition more severe than staleness: the memory invariant actively contradicts current governance document text — not merely unvalidated since an amendment, but factually wrong relative to the current authoritative source.

### §6.1 — Detection Paths

**Path A — Sync-discovered conflict:**
`delta sync constitution` text comparison identifies a contradiction. Classified as `conflict` in Sync Report. Automatically escalated to Director review before any session proceeds with the conflicted domain.

**Path B — Agent-discovered conflict:**
During a session, an agent loads a governance document and observes that its current text contradicts a memory invariant. The agent must:
1. Not proceed with the conflicted governance decision
2. Apply the **current document text** as authoritative — memory is a convenience layer, not the source of truth
3. Flag the conflict explicitly in CSO §9 with: entity name, source document, section, invariant text, current document text, and agent's session context
4. Surface the conflict to Director at session close — not silently resolve it

### §6.2 — Escalation Flow

```
Conflict detected (Path A or Path B)
           ↓
Agent applies current document text for session behavior
           ↓
Conflict flagged in CSO §9 (mandatory — silent resolution is a governance violation)
           ↓
Director reviews at session close
           ↓
Director determines root cause:
  ├── Memory is wrong (document was correctly amended, memory not updated)
  │     → Hard invalidation + re-validated invariant write (Memory Doctrine §4)
  │
  ├── Document was incorrectly amended (amendment introduced an error)
  │     → Amendment revision under Constitution Article VIII
  │     → Memory invariant may be correct — re-validate after revision
  │
  └── Edge case requiring temporary deviation
        → Temporary Experimental Authorization (Constitution Article VIII)
        → Soft invalidation of conflicted invariant until resolution
           ↓
Conflict resolution recorded in CSO §9 + amendment log if applicable
           ↓
delta sync constitution to confirm clean state after resolution
```

### §6.3 — Prohibition

An agent must never:
- Choose memory over the current governance document without Director involvement
- Silently discard a conflict observed during execution
- Self-resolve a governance conflict by deciding which source is "more correct"

Memory serves agents. Governance documents govern agents. When they conflict, the document governs — always — and the conflict must be surfaced.

### §6.4 — Constitution Article VIII Connection

Constitution Article VIII's governance-conflict clause establishes that a document found to be in governance conflict (internally contradictory or contradicting a higher-authority document) loses authoritative standing until resolved. This doctrine's conflict escalation flow is the operational implementation of that clause:

- If the **memory** is the conflicted source → invalidation resolves it
- If the **document** is the conflicted source → amendment revision resolves it
- Either way, the constitutional chain of authority is restored before the affected domain is used for governance decisions

---

## §7 — Relationship to Other Doctrine

| Doctrine | Relationship |
| -------- | ------------ |
| **Memory Architecture Doctrine** (`DELTA-MEMORY-DOCTRINE.md`) | Defines what qualifies as a constitutional invariant, the 5 qualification criteria, and the Director approval gate for writes. Sync Doctrine governs the lifecycle of invariants *after* they are written. |
| **Lifecycle Retention Doctrine** (`DELTA-LIFECYCLE-RETENTION.md`) | Defines lifecycle of all ecosystem artifacts. Sync Doctrine is the constitutional-memory-specific lifecycle extension — invalidation is the decay mechanism for constitutional invariants. |
| **CLI Architecture** (`DELTA-CLI-ARCHITECTURE.md`) | `delta sync *` commands defined in §8.3. Sync Doctrine provides the governance contract those commands enforce. |
| **Constitution Article VIII** | Amendment doctrine, TEA, and governance-conflict clause. Sync Doctrine's conflict escalation flow (§6.2) is the operational implementation of Article VIII's conflict resolution path. |
| **Transient Cognition Doctrine** (`DELTA-TRANSIENT-COGNITION.md`) | Sync Report outputs and CSO §9 conflict flags follow the transient cognition promotion pathway before any memory write. Sync Reports are transient — they must not be persisted directly to MCP without CSO §9 promotion. |

---

## §8 — Enforcement

1. Mandatory sync triggers are non-negotiable — constitutional amendment always triggers re-validation
2. Stale invariants must not be cited as authoritative — agents fall back to current document text
3. Conflicted invariants must be surfaced immediately — silent resolution is a governance violation
4. Invalidation is append-only — no entity or observation deletion is permitted under any circumstance
5. Hard invalidation requires Director approval gate identical to new constitutional write
6. `--dry-run` mode produces no writes — it is always safe to invoke
7. Sync Report findings (stale or conflict) must be recorded in CSO §9 before session close
8. Sync checkpoint is written to `progress.json` after every non-dry-run sync completion
9. Bootstrap alert for governance document changes does not block session — it is informational; Director decides whether to invoke sync before proceeding

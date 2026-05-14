# Delta CLI Architecture

## §1 — Purpose & Positioning

The Delta CLI is **mandatory AI operational middleware**. Its purpose is not to make prompt construction more convenient — it is to make governance enforcement deterministic.

The architectural distinction is absolute:

- **Prompt** = AI-compatible natural language expansion of an operation (implementation detail, generated at runtime, never stored persistently)
- **Operation** = governance abstraction (deterministic, routable, composable, defined in the Operation Registry)
- **CLI** = the enforcement layer that routes Director intent to the correct operation, validates preconditions, and records execution events to runtime state

The CLI sits between Director intent and AI execution. Without it, governance depends on agent discretion. With it, governance is enforced structurally.

Three evolution levels define the CLI's maturity trajectory:

| Level | Name | Behavior |
| ----- | --------- | -------- |
| 1 | **Alias** | `delta ant plan` expands into role activation + context injection sequence |
| 2 | **Semantic** | `delta wo new` auto-detects latest STRAT, validates dependencies, injects template, initializes runtime state |
| 3 | **Intent** | Director states goal; runtime infers role, operation, mode, and outputs automatically |

**Current design target:** Level 1 implementation with Level 2 semantics for WO and session operations. Level 3 is an architectural aspiration, not a Phase 4 deliverable.

---

## §2 — Execution Boundary Model

The CLI governs three distinct concerns:

**1. Whether to do it** — enforced by workflow gating (§6). The CLI checks preconditions before any operation is handed to an agent.

**2. What to do** — defined by the Operation Registry (`DELTA-OPERATION-REGISTRY.json`). Each CLI command maps to exactly one `operation_id`.

**3. How to do it** — generated at runtime by the AI agent. Never stored in the Operation Registry. The agent constructs the conversation from:
- The resolved operation definition
- The current runtime state (`progress.json`)
- The active role's rule file
- The governance documents resolved via the Semantic Registry (`DELTA-REGISTRY.json`)

**Enforcement Rule:** If an operation definition in the registry contains a prose field intended to be passed directly to an AI model as conversation text, that is a design violation. The CLI governs operations, not conversations.

---

## §3 — Mandatory Enforcement Doctrine

The following operation categories require CLI invocation. Ad-hoc prompt substitution is forbidden for these:

| Category | CLI Domain | Reason |
| -------- | ---------- | ------ |
| Work Order creation, advancement, supersession | `wo` | Workflow gate enforcement |
| Strategy document lifecycle | `strat` | Approval gate enforcement |
| Implementation lifecycle | `impl` | WO dependency validation |
| Memory writes (Constitutional tier) | `sync` | Director approval gate |
| CSO §9 promotion | `session` | Transient cognition boundary |
| Constitutional amendment or TEA declaration | `sync` | Constitution Article VIII |
| Session bootstrap and close | `session` | Runtime state initialization |
| Director Override declarations | `override` | Traceability requirement |

### No Silent Bypass

Agents cannot circumvent the CLI by constructing ad-hoc prompts for operations that have registered CLI definitions. If the Operation Registry defines an operation for the task at hand, the CLI must be invoked. Silent bypass is treated as a governance violation equivalent to a role boundary violation.

---

## §4 — Runtime vs Markdown Authority Boundary

This is an explicit architectural statement with no exceptions:

| Layer | Content | Authority |
| ----- | ------- | --------- |
| **Markdown governance documents** | Role rules, doctrine, protocol, Constitution | **Semantic truth** — defines what *should* be |
| **Runtime state (`progress.json`)** | Current workflow state, document states, override records, gate transitions | **Operational truth** — defines what *is* right now |

### Governing Principle

When markdown and runtime state conflict:

- **Runtime state governs current execution** — what the CLI will permit in this session
- **Markdown documents govern future behavior** — what the CLI will enforce after the next session bootstrap

### Corollary

An agent cannot pass a gate by citing a markdown document that describes the gate as open. The runtime state IS the gate. Changing the gate requires either:
- (a) Advancing the workflow to the correct state through normal execution
- (b) A Director Override declaration that creates a runtime override record (`delta override declare`)

**Example:** `progress.json` shows WO-002 as `IN_PROGRESS`. ANT-RULE.md says to proceed to next WO when current is complete. The CLI blocks `delta wo new` until WO-002 transitions to `COMPLETE` in `progress.json`. The rule file's statement is semantic — it describes intended behavior. The runtime state enforces it operationally.

---

## §5 — Director Override Doctrine

### 5.1 — Scope

Director Override applies at the **Protocol level** — it permits deviation from DELTA_PROTOCOL.md operational requirements. This is distinct from:

| Override Type | When | Instrument | Authority Level |
| ------------- | ---- | ---------- | --------------- |
| **Director Override** | Protocol-level operational friction | `delta override declare` | Protocol |
| **Temporary Experimental Authorization (TEA)** | Constitutional-level deviation | Constitution Article VIII process | Constitutional |
| **Amendment** | Permanent doctrine change | Constitution Article VIII process | Constitutional |

Director Override is an operational safety valve, not a governance escape hatch. It cannot replace a required TEA.

### 5.2 — Declaration Requirement

All Director Overrides must be explicitly declared via the CLI:

```
delta override declare \
  --scope=<scope_value> \
  --reason="<rationale>" \
  --expires=<session|condition|ISO8601>
```

**Closed scope vocabulary:**

| Scope Value | What It Bypasses |
| ----------- | ---------------- |
| `wo_gate` | WO lifecycle gate — permits new WO while prior is not COMPLETE |
| `strat_gate` | STRAT approval gate — permits WO creation without APPROVED STRAT |
| `document_order` | Permits out-of-sequence document creation |
| `agent_boundary` | Permits cross-role document access (Director-only, rare) |

### 5.3 — Runtime Record

Declaration creates an override record in `progress.json` with:

```json
{
  "override_id": "<auto-generated>",
  "scope": "<scope_value>",
  "reason": "<rationale>",
  "declared_at": "<ISO8601>",
  "expires": "<session | condition_string | ISO8601>",
  "declared_by": "director",
  "status": "active"
}
```

Override records are never deleted. They are the traceability mechanism. Status transitions from `active` to `expired` or `revoked`.

### 5.4 — Override Boundaries

Director Override cannot:

- Circumvent Constitutional-level requirements (those require TEA — Constitution Article VIII)
- Retroactively suppress or delete audit records
- Grant an agent elevated permissions beyond its role definition
- Persist beyond declared expiry without a new declaration
- Replace the Director Override in DELTA_PROTOCOL.md's Overview section — that is a semantic acknowledgment; this is the runtime enforcement mechanism

---

## §6 — Workflow Gating Enforcement

### 6.1 — WO Lifecycle States

```
PENDING → IN_PROGRESS → COMPLETE
               ↓              ↓
            BLOCKED      SUPERSEDED
               ↓
         IN_PROGRESS (after resolution)
```

| State | Meaning | Valid Next States |
| ----- | ------- | ----------------- |
| `PENDING` | WO created, execution not started | `IN_PROGRESS` |
| `IN_PROGRESS` | CDC executing | `COMPLETE`, `BLOCKED`, `SUPERSEDED` |
| `BLOCKED` | Execution halted, resolution required | `IN_PROGRESS`, `SUPERSEDED` |
| `COMPLETE` | WO successfully delivered and verified | `SUPERSEDED` |
| `SUPERSEDED` | Replaced by newer WO version | — (terminal) |

### 6.2 — Gate Rules

**Gate 1 — New WO creation (`delta wo new`):**
Prior WO for the same project must be in `COMPLETE` or `SUPERSEDED` state. If prior WO is `IN_PROGRESS` or `BLOCKED`, `delta wo new` is rejected. Bypass requires `delta override declare --scope=wo_gate`.

**Gate 2 — CDC execution start (`delta impl start`):**
Active WO must be in `IN_PROGRESS` state. A `PENDING` WO must be advanced by ANT first (`delta wo advance`). This ensures ANT has reviewed and approved before CDC begins.

**Gate 3 — Session bootstrap (`delta session bootstrap`):**
CLI reads `progress.json` and surfaces alerts for any `BLOCKED` or stale `IN_PROGRESS` WOs (stale = `last_updated` older than 7 days). Alerts are informational — they do not block bootstrap, but they require acknowledgment.

**Gate 4 — STRAT lock (`delta strat lock`):**
STRAT must be in `COMPLETE` state before lock. Lock gate checks `audit_records` for satisfied verdicts from all required approvers per audit policy (Director + GPT + PPX for STRAT). A verdict satisfies the gate if it is `APPROVED`, or `CONDITIONAL_APPROVAL` with `conditions_status` of `RESOLVED` or `WAIVED_BY_DIRECTOR`. Unresolved `REJECTED` or `CONDITIONAL_APPROVAL` with `OPEN` conditions blocks the lock. CSO is not a lock gate requirement. Bypass via `delta override declare --scope audit_gate`. Locked STRAT cannot be superseded except via `delta strat pivot` (HARD invalidation flow).

**Gate 5 — WO lock (`delta wo lock`):**
WO must be `COMPLETE` and the active STRAT must be locked. Lock gate checks `audit_records` for Director verdict (minimum) per audit policy. Additional approvers may be required by policy or risk level. Same bypass path as Gate 4.

**Gate 6 — STR lock (`delta str lock`):**
STR must be `COMPLETE`. Lock gate checks `audit_records` for Director verdict (minimum). Same rules as WO lock.

### 6.3 — Gate Bypass

```
delta override declare --scope=wo_gate --reason="<rationale>" --expires=session
delta override declare --scope=audit_gate --reason="<rationale>" --expires=session
```

Override scopes: `wo_gate`, `strat_gate`, `audit_gate`, `document_order`, `agent_boundary`, `project_closed`.

After declaration, the CLI permits the gated operation for the declared scope and expiry. All bypass events are logged as gate transition records in `progress.json`.

---

## §7 — Delta Operation Semantics

### 7.1 — Three-Level Model

**Level 1 — Alias**

`delta ant plan` resolves to: load ANT-RULE.md + load active STRAT + load active WO + assert role context. The operation definition specifies which documents to load and in what order. The AI agent receives the loaded context and constructs the conversation from it. No prompt text is stored in the operation definition.

**Level 2 — Semantic**

`delta wo new` resolves to: check Gate 1 → detect latest approved STRAT from `document_states` → inject WO template → create WO entry in `progress.json` with state `PENDING` → hand off to ANT. The operation is state-aware — it reads runtime state and resolves inputs without Director specifying them.

**Level 3 — Intent** (aspirational)

Director states: `delta intent "prepare next implementation cycle for auth module"`. The CLI infers: role=ANT, domain=wo, action=new, mode=STRICT, required inputs=[active STRAT, prior WALK], produces=WO draft. Full semantic understanding of project state and goal. This level requires a runtime reasoner, not just a routing engine.

### 7.2 — Operation-Prompt Separation Principle

| What | Where It Lives | Format |
| ---- | -------------- | ------ |
| Operation definition | `DELTA-OPERATION-REGISTRY.json` | Structured JSON |
| Prompt content | Never stored persistently | Generated at runtime from operation + loaded context |
| Execution record | `progress.json` | Structured JSON |
| Session transcript | CSO (if preserved at session close) | Markdown |

**Anti-pattern:** An operation definition field named `prompt_template` containing prose like "You are ANT. Your task is to..." — this is forbidden. If such a field exists in an operation definition, it is a design violation. Prompts are generated; operations are defined.

---

## §8 — CLI Command Surface

### 8.1 — Pattern

```
delta {domain} {action} [--flags]
```

Rules:
- `domain` and `action` are single lowercase words — no hyphens, no underscores in the token
- Flags use `--key=value` format
- Every command maps to exactly one `operation_id` in the Operation Registry
- No command exists without a corresponding operation definition

### 8.2 — Domain Taxonomy

| Domain | Scope | Primary Role |
| ------ | ----- | ------------ |
| `project` | Project initialization, identity, and closure | Director |
| `wo` | Work Order lifecycle | ANT |
| `strat` | Strategy document lifecycle | GMN |
| `impl` | Implementation lifecycle | CDC |
| `session` | Session bootstrap and close | All |
| `override` | Director Override management | Director |
| `sync` | Constitutional and memory sync | Director |
| `audit` | Conversational audit triggers | GPT, PPX |
| `registry` | Semantic Registry validation and update | Director |

### 8.3 — Core Command Set

**`delta wo` — Work Order domain**
```
delta wo new              # Create new WO (Gate 1 checked)
delta wo advance          # Transition WO: PENDING → IN_PROGRESS
delta wo status           # Display current WO state and metadata
delta wo complete         # Transition WO: IN_PROGRESS → COMPLETE
delta wo supersede        # Replace WO with new version (transitions to SUPERSEDED)
delta wo list             # List all WOs and lifecycle states
```

**`delta strat` — Strategy domain**
```
delta strat new           # Begin STRAT formulation (loads DI, creates entry in progress.json)
delta strat status        # Show STRAT approval state
delta strat lock          # Lock STRAT at v1.0 after GPT + PPX approval
delta strat pivot         # Initiate HARD invalidation flow (STRAT_INVALIDATION)
```

**`delta impl` — Implementation domain**
```
delta impl start          # Begin CDC implementation (Gate 2 checked)
delta impl walkthrough    # Submit walkthrough plan to ANT for review
delta impl complete       # Mark implementation complete, advance WO state
```

**`delta session` — Session domain**
```
delta session bootstrap   # Load runtime state + resolve active governance documents
delta session cso         # Generate CSO document for session close
delta session close       # Finalize session, flush ephemeral state, update progress.json
```

**`delta override` — Override domain**
```
delta override declare    # Declare Director Override (requires --scope, --reason, --expires)
delta override list       # Show all overrides (active and historical)
delta override revoke     # Revoke an active override by override_id
```

**`delta sync` — Sync domain**
```
delta sync constitution   # Validate MCP constitutional memory against Constitution document
delta sync registry       # Rebuild/validate DELTA-REGISTRY.json for violations
delta sync memory         # Re-validate Operational Memory entities against active STRAT
```

**`delta project` — Project domain**
```
delta project start       # Initialize new project or resume closed project
                          # --name=<name> --id=<id> --type=<lite|full> [--path=<dir>]
delta project end         # Close project; preserves all state for resume
                          # [--path=<project_root>]
```

`delta project start` detects existing `project.json`:
- If absent → initialize: scaffold `Delta/` layer + root bridge files + `project.json`
- If present and `status=closed` → resume: set `status=active`, clear `closed_at`
- If present and `status=active` → no-op with notification

`--type=lite` creates: `Delta/` + `00_Rules/`, `01_Strategy/`, `02_Blueprint/`, `03_Build/`, `07_Logs/`
`--type=full` creates: all of the above + `04_Skills/`, `05_References/`, `06_Knowledge/`, `08_Test/`, `99_Docs/`

`delta project end` writes `status=closed` and `closed_at` to `project.json`. CLI gates that check project status will block new WOs and session operations on a closed project (override: `delta override declare --scope=project_closed`).

**`delta audit` — Audit domain**
```
delta audit record        # Record an audit verdict against an artifact
delta audit list          # List audit records, optionally filtered
delta audit status        # Show audit summary for a specific artifact
delta audit resolve       # Resolve a CONDITIONAL_APPROVAL (OPEN → RESOLVED)
delta audit waive         # Director waives conditions (OPEN → WAIVED_BY_DIRECTOR)
delta audit session       # Display full session state for Director review
```

**`delta cso` — CSO domain**
```
delta cso new             # Create a new CSO linked to an artifact
delta cso complete        # Mark CSO content as COMPLETE
delta cso link            # Link CSO to a target artifact
delta cso status          # Show CSO state and linked audit records
delta cso list            # List all CSOs
delta cso lock            # Lock CSO as immutable historical record
```

**`delta str` — STR domain**
```
delta str new             # Create a new STR document
delta str advance         # Transition STR: PENDING → IN_PROGRESS
delta str complete        # Transition STR: IN_PROGRESS → COMPLETE
delta str lock            # Lock STR after audit policy satisfied
delta str list            # List all STRs
```

**`delta registry` — Registry domain**
```
delta registry validate   # Check DELTA-REGISTRY.json against schema and entropy rules
delta registry add        # Propose new document entry (requires Director approval before write)
```

### 8.4 — Composability Rules

Operations compose by sequencing separate commands — not by creating compound aliases.

**Correct:** Two separate operations, each with its own CLI invocation:
```
delta wo supersede --wo-id=WO-002-v0.3
delta wo new
```

**Incorrect:** Compound alias bundling two operations:
```
delta wo supersede-and-new   # Forbidden
```

A compound alias that bundles multiple operations is forbidden. Each `delta {domain} {action}` maps to exactly one operation_id.

### 8.5 — Anti-Patterns

| Anti-Pattern | Problem | Correct Form |
| ------------ | ------- | ------------ |
| `delta create-new-work-order` | Bypasses domain taxonomy | `delta wo new` |
| `delta ant_formulate_wo` | Operation too specific, not reusable | `delta wo new` |
| `delta plan` | Ambiguous domain | `delta ant plan` or `delta strat new` |
| `delta wo new_for_feature_x` | Feature-specific alias violates composability | `delta wo new` (context comes from runtime state) |
| `delta everything` | Intent-level command before Level 3 CLI | Not valid until Level 3 implementation |

---

## §9 — Enforcement

1. All operations with registered CLI definitions must be invoked via the CLI — no ad-hoc prompt substitution for these categories
2. Workflow gating is enforced at the CLI boundary — agents cannot self-grant gate passage
3. Director Override requires a runtime declaration — markdown notes do not constitute a valid override
4. Operation definitions in the Operation Registry must not contain prompt text
5. All CLI operation invocations are logged as gate transition records in `progress.json`
6. Command surface must follow `delta {domain} {action}` — no compound tokens
7. New domains or actions require an Operation Registry entry before CLI use — no ad-hoc commands
8. CLI command surface document (this document §8) is the single source of truth for valid commands — the Operation Registry provides the machine-readable definition of each

---

## References

- Runtime metadata schema: `DELTA-RUNTIME-SCHEMA.md`
- Operation definitions: `DELTA-OPERATION-REGISTRY.json` (schema: `DELTA-OPERATION-REGISTRY-SCHEMA.md`)
- Semantic document routing: `DELTA-REGISTRY.json`
- Director Override protocol (semantic layer): `DELTA_PROTOCOL.md` Overview section
- Constitutional Override instruments: `DELTA_CONSTITUTION.md` Article VIII
- Workflow gating audit trail: `progress.json` (schema: `DELTA-RUNTIME-SCHEMA.md`)

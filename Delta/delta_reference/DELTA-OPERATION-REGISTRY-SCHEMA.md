# Delta Operation Registry Schema

## §1 — Purpose

The Operation Registry (`DELTA-OPERATION-REGISTRY.json`) is the machine-readable definition of all valid Delta CLI operations. It is the Single Source of Truth for what the CLI can do.

Each entry in the registry defines a governance contract for one operation. The contract specifies: who may invoke it, what inputs it requires, what it produces, under what mode it runs, and what gates it checks. The contract does not specify how the AI agent should construct its conversation — that is the agent's responsibility at runtime.

**Positioning in the 4-layer cognition stack:**
- Layer 4: Raw governance documents (DELTA_CONSTITUTION.md, DELTA_PROTOCOL.md, doctrine docs)
- Layer 3: Semantic Governance Registry (`DELTA-REGISTRY.json`) — document navigation
- Layer 2: MCP Memory — persistent entity knowledge
- Layer 1: Runtime metadata (`progress.json`) — current execution state
- **Operation Registry** sits at Layer 1 alongside runtime metadata — it is the definition layer for CLI execution

The Operation Registry governs CLI operations. The Semantic Governance Registry governs document navigation. They are distinct with distinct purposes.

---

## §2 — Operation Entry Schema

Each entry in `DELTA-OPERATION-REGISTRY.json` must conform to this schema:

```json
{
  "operation_id": "string",
  "domain": "string",
  "action": "string",
  "level": "alias | semantic | intent",
  "role": "string",
  "mode": "strict | any",
  "description": "string",
  "inputs": [
    {
      "name": "string",
      "source": "runtime_state | registry | filesystem | director_declaration",
      "required": true
    }
  ],
  "outputs": [
    {
      "name": "string",
      "type": "document | state_transition | log_entry | override_record"
    }
  ],
  "constraints": [
    {
      "type": "gate | role_boundary | constitution | protocol | audit_policy",
      "rule": "string"
    }
  ],
  "gating": {
    "pre_condition": "string | null",
    "post_condition": "string | null"
  }
}
```

### §2.1 — Field Definitions

| Field | Type | Description |
| ----- | ---- | ----------- |
| `operation_id` | string | Globally unique, stable snake_case identifier. Never renamed after assignment. |
| `domain` | string | CLI domain (from closed vocabulary §3.1) |
| `action` | string | CLI action word |
| `level` | enum | Evolution level of this operation (§3.2) |
| `role` | string | Role authorized to invoke (from closed vocabulary §3.3) |
| `mode` | string | Execution mode this operation requires (§3.4) |
| `description` | string | Single-sentence description of what the operation does. No prompt text. |
| `inputs` | array | Required inputs for the operation to execute |
| `outputs` | array | What the operation produces |
| `constraints` | array | Governance constraints enforced by the CLI before execution |
| `gating.pre_condition` | string or null | Assertion on runtime state that must be true before execution |
| `gating.post_condition` | string or null | Expected runtime state after execution completes |

### §2.2 — Stability Rules

- `operation_id` is permanent once assigned. Operations are deprecated (by adding `"deprecated": true`), never renamed or deleted.
- `domain` and `action` form the CLI command surface. Changes require a CLI architecture update.
- All fields are required unless explicitly marked optional in this schema.

---

## §3 — Closed Vocabularies

### §3.1 — Domain Values

| Value | Scope |
| ----- | ----- |
| `wo` | Work Order lifecycle |
| `strat` | Strategy document lifecycle |
| `impl` | Implementation lifecycle |
| `session` | Session bootstrap and close |
| `override` | Director Override management |
| `sync` | Constitutional and memory sync |
| `audit` | Audit record and verdict operations |
| `cso` | Cognitive State Object lifecycle |
| `str` | Software Test Report lifecycle |
| `registry` | Semantic Registry validation and update |

### §3.2 — Level Values

| Value | Meaning |
| ----- | ------- |
| `alias` | Command expands to a fixed context injection sequence (Level 1) |
| `semantic` | Command resolves inputs from runtime state automatically (Level 2) |
| `intent` | Command infers full operation sequence from goal statement (Level 3 — aspirational) |

### §3.3 — Role Values

| Value | Who May Invoke |
| ----- | -------------- |
| `ant` | ANT role only |
| `gmn` | GMN role only |
| `cdc` | CDC role only |
| `director` | Director only |
| `any` | Any role |

### §3.4 — Mode Values

| Value | Meaning |
| ----- | ------- |
| `strict` | Full STRICT Mode governance applies (the only execution mode) |
| `any` | Mode does not restrict this operation |

### §3.5 — Input Source Values

| Value | Meaning |
| ----- | ------- |
| `runtime_state` | Resolved from `progress.json` |
| `registry` | Resolved from `DELTA-REGISTRY.json` |
| `filesystem` | Read from project filesystem |
| `director_declaration` | Provided explicitly by Director at invocation |

### §3.6 — Output Type Values

| Value | Meaning |
| ----- | ------- |
| `document` | Creates or modifies a project document |
| `state_transition` | Updates `progress.json` workflow or document state |
| `log_entry` | Appends to `gate_transitions` or `logs_registry` in `progress.json` |
| `override_record` | Creates an override record in `progress.json` |

### §3.7 — Constraint Type Values

| Value | Meaning |
| ----- | ------- |
| `gate` | Workflow lifecycle gate — checks `progress.json` state |
| `role_boundary` | Enforces that the invoking agent matches `role` field |
| `constitution` | References a Constitutional requirement |
| `protocol` | References a DELTA_PROTOCOL.md requirement |
| `audit_policy` | Checks `audit_records` against required approvers for the artifact type |

---

## §4 — Example Entries

### Example 1 — `wo.new` (Level 2 — Semantic)

```json
{
  "operation_id": "wo_new",
  "domain": "wo",
  "action": "new",
  "level": "semantic",
  "role": "ant",
  "mode": "strict",
  "description": "Create a new Work Order after validating workflow gate and injecting the WO template.",
  "inputs": [
    {
      "name": "active_strat",
      "source": "runtime_state",
      "required": true
    },
    {
      "name": "wo_template",
      "source": "filesystem",
      "required": true
    }
  ],
  "outputs": [
    {
      "name": "wo_document",
      "type": "document"
    },
    {
      "name": "wo_state_entry",
      "type": "state_transition"
    },
    {
      "name": "gate_event",
      "type": "log_entry"
    }
  ],
  "constraints": [
    {
      "type": "gate",
      "rule": "active_wo_state must be null, COMPLETE, or SUPERSEDED"
    },
    {
      "type": "role_boundary",
      "rule": "invoking agent must be ANT"
    },
    {
      "type": "gate",
      "rule": "strat_locked must be true OR strat_gate override must be active"
    }
  ],
  "gating": {
    "pre_condition": "workflow_state.active_wo_state IN [null, COMPLETE, SUPERSEDED]",
    "post_condition": "workflow_state.active_wo_state = PENDING"
  }
}
```

### Example 2 — `override.declare` (Level 1 — Alias)

```json
{
  "operation_id": "override_declare",
  "domain": "override",
  "action": "declare",
  "level": "alias",
  "role": "director",
  "mode": "any",
  "description": "Record a Director Override for the specified governance scope.",
  "inputs": [
    {
      "name": "scope",
      "source": "director_declaration",
      "required": true
    },
    {
      "name": "reason",
      "source": "director_declaration",
      "required": true
    },
    {
      "name": "expires",
      "source": "director_declaration",
      "required": true
    }
  ],
  "outputs": [
    {
      "name": "override_record",
      "type": "override_record"
    },
    {
      "name": "gate_event",
      "type": "log_entry"
    }
  ],
  "constraints": [
    {
      "type": "role_boundary",
      "rule": "invoking agent must be Director"
    },
    {
      "type": "constitution",
      "rule": "override scope must be protocol-level; constitutional-level deviations require TEA (Article VIII)"
    }
  ],
  "gating": {
    "pre_condition": null,
    "post_condition": "override record created with status=active"
  }
}
```

### Example 3 — `session.bootstrap` (Level 2 — Semantic)

```json
{
  "operation_id": "session_bootstrap",
  "domain": "session",
  "action": "bootstrap",
  "level": "semantic",
  "role": "any",
  "mode": "any",
  "description": "Initialize session state by loading progress.json and resolving active governance documents.",
  "inputs": [
    {
      "name": "progress_json",
      "source": "filesystem",
      "required": false
    },
    {
      "name": "delta_registry",
      "source": "registry",
      "required": true
    }
  ],
  "outputs": [
    {
      "name": "session_state",
      "type": "state_transition"
    },
    {
      "name": "gate_event",
      "type": "log_entry"
    }
  ],
  "constraints": [
    {
      "type": "protocol",
      "rule": "if progress.json absent, create from initialization template"
    },
    {
      "type": "protocol",
      "rule": "surface alerts for BLOCKED or stale IN_PROGRESS WOs"
    }
  ],
  "gating": {
    "pre_condition": null,
    "post_condition": "session active, governance documents resolved"
  }
}
```

---

## §5 — Anti-Proliferation Rules

The Operation Registry must remain compact and domain-clear. The following rules prevent operation explosion:

**Rule 1 — One operation per CLI command.** Each `delta {domain} {action}` maps to exactly one `operation_id`. No two operations may share a domain+action pair.

**Rule 2 — No feature-specific operations.** Operations are generic governance units, not feature-specific aliases. `wo_new` is correct; `wo_new_for_auth_module` is forbidden. Context comes from runtime state, not operation names.

**Rule 3 — No prompt storage.** Operation `description` fields are single-sentence governance summaries. Prompt text is never stored in the registry.

**Rule 4 — No mode variants in operation IDs.** Operations that differ only by invocation context are the same operation. Context comes from runtime state and flags, not embedded in the operation token or action name.

**Rule 5 — Deprecation over deletion.** When an operation is retired, add `"deprecated": true` and `"deprecated_reason": "string"`. Never delete entries — operation_ids are stable identifiers that may appear in `gate_transitions` logs.

**Rule 6 — New domain requires Director approval.** Adding a new domain to the closed vocabulary requires Director review of the CLI Architecture document (§8 of `DELTA-CLI-ARCHITECTURE.md`) and an update to both this schema and the CLI architecture. Arbitrary domain additions are forbidden.

**Rule 7 — Level 3 operations are aspirational.** No operations may be assigned `level: "intent"` until Level 3 CLI implementation is complete. All current operations are `alias` or `semantic`.

---

## §6 — Registry File Structure

The runtime Operation Registry is stored as `DELTA-OPERATION-REGISTRY.json` in the project root.

```json
{
  "schema_version": "1.0.0",
  "operations": [
    { ... },
    { ... }
  ]
}
```

Top-level fields:

| Field | Type | Description |
| ----- | ---- | ----------- |
| `schema_version` | string | Schema version of this file |
| `operations` | array | Array of operation entries conforming to §2 |

---

## §7 — Relationship to CLI Architecture

The Operation Registry is the data layer. The CLI Architecture (`DELTA-CLI-ARCHITECTURE.md`) is the governance layer.

| Concern | Where Defined |
| ------- | ------------- |
| What operations exist and their contracts | Operation Registry (this schema) |
| How the CLI enforces gating | `DELTA-CLI-ARCHITECTURE.md` §6 |
| What the command surface looks like | `DELTA-CLI-ARCHITECTURE.md` §8 |
| What the runtime state looks like | `DELTA-RUNTIME-SCHEMA.md` |
| How to navigate governance documents | `DELTA-REGISTRY.json` |

An operation definition in the registry references governance constraints by type and rule string. It does not inline governance document content. The CLI resolves the full governance context at runtime by loading the relevant documents via the Semantic Registry.

---

## References

- CLI Architecture: `DELTA-CLI-ARCHITECTURE.md`
- Runtime state schema: `DELTA-RUNTIME-SCHEMA.md`
- Semantic document routing: `DELTA-REGISTRY.json` (schema: `DELTA-REGISTRY-DOCTRINE.md`)
- Director Override doctrine: `DELTA-CLI-ARCHITECTURE.md` §5
- Constitutional Override instruments: `DELTA_CONSTITUTION.md` Article VIII

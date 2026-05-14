# Delta Runtime Metadata Schema

## §1 — Purpose & Authority

This document defines the canonical schema for `progress.json` — the runtime state store for Delta project execution — and all associated runtime metadata structures.

**Authority Statement:** `progress.json` is the operational Single Source of Truth for current workflow state. It is the authoritative record of what is happening now. Markdown governance documents are semantic truth — they define what should happen. When they conflict, `progress.json` governs current CLI behavior. See `DELTA-CLI-ARCHITECTURE.md` §4 for the full runtime vs markdown authority boundary doctrine.

`progress.json` resides in the project root folder alongside `DELTA_PROTOCOL.md`.

---

## §2 — `progress.json` Top-Level Schema

```json
{
  "schema_version": "string",
  "project_id": "string",
  "project_name": "string",
  "last_updated": "ISO8601",
  "workflow_state": { },
  "document_states": { },
  "audit_records": [ ],
  "cso_states": { },
  "overrides": [ ],
  "gate_transitions": [ ],
  "logs_registry": [ ]
}
```

### Field Definitions

| Field | Type | Description |
| ----- | ---- | ----------- |
| `schema_version` | string | Schema version of this file (e.g., `"1.0.0"`) |
| `project_id` | string | Numeric project identifier (e.g., `"002"`) |
| `project_name` | string | Human-readable project name |
| `last_updated` | ISO8601 | Timestamp of last write to this file |
| `workflow_state` | object | Current execution state — see §3 |
| `document_states` | object (map) | Per-document lifecycle states — see §4 |
| `audit_records` | array | Append-only audit verdict records — see §8 |
| `cso_states` | object (map) | CSO lifecycle state tracking — see §9 |
| `overrides` | array | Director Override records — see §5 |
| `gate_transitions` | array | Gate event log — see §6 |
| `logs_registry` | array | Index of all CSOs and session logs — see §7 |

---

## §3 — `workflow_state` Schema

```json
{
  "current_phase": "string",
  "di_locked": false,
  "active_di": "string | null",
  "active_di_version": "string | null",
  "strat_locked": false,
  "active_strat": "string | null",
  "active_strat_version": "string | null",
  "active_wo": "string | null",
  "active_wo_state": "PENDING | IN_PROGRESS | BLOCKED | COMPLETE | LOCKED | SUPERSEDED | null",
  "pdc_locked": false,
  "active_pdc": "string | null"
}
```

### Field Definitions

| Field | Type | Description |
| ----- | ---- | ----------- |
| `current_phase` | string | Active project phase (e.g., `"planning"`, `"implementation"`) |
| `di_locked` | boolean | `true` when the active DI has been locked |
| `active_di` | string or null | Filename of the currently locked DI document |
| `active_di_version` | string or null | Version of the currently locked DI |
| `strat_locked` | boolean | `true` when STRAT has been locked |
| `active_strat` | string or null | Filename of the currently locked STRAT document |
| `active_strat_version` | string or null | Version of the currently locked STRAT |
| `active_wo` | string or null | Filename of the currently active Work Order |
| `active_wo_state` | enum or null | WO lifecycle state — see §3.1 |
| `pdc_locked` | boolean | `true` when the PDC has been locked (project closure sealed) |
| `active_pdc` | string or null | Filename of the locked PDC document |

All pointer fields (`active_di`, `active_strat`, `active_wo`, `active_pdc`) and their corresponding lock booleans are updated atomically with `document_states` in the same write.

### §3.1 — WO Lifecycle States

| State | Meaning | Valid Transitions |
| ----- | ------- | ----------------- |
| `PENDING` | WO created, execution not started | → `IN_PROGRESS` |
| `IN_PROGRESS` | CDC actively executing | → `COMPLETE`, `BLOCKED`, `SUPERSEDED` |
| `BLOCKED` | Execution halted, resolution required | → `IN_PROGRESS`, `SUPERSEDED` |
| `COMPLETE` | WO delivered and verified by ANT | → `LOCKED` |
| `LOCKED` | WO version-locked — IMPL/WALK creation gated on this state | — (terminal for this WO version; new WO version may be created) |
| `SUPERSEDED` | Replaced by a newer WO version | — (terminal) |

State transitions are written to both `workflow_state.active_wo_state` and a gate transition record (§6) in the same atomic write.

### §3.2 — Execution Mode Values

| Value | When Active |
| ----- | ----------- |
| `strict` | Always — full multi-agent document-driven governance. No other modes exist. |

Delta operates exclusively in STRICT Mode. The former Adaptive Mode and Fast Lane concepts have been permanently removed.

---

## §4 — `document_states` Schema

`document_states` is a map keyed by `document_id` (matching the `document_id` in `DELTA-REGISTRY.json`). Each entry tracks the current lifecycle state of that document.

```json
{
  "document_states": {
    "<document_id>": {
      "file": "string",
      "status": "DRAFT | PENDING | APPROVED | IN_PROGRESS | COMPLETE | SUPERSEDED | LOCKED",
      "version": "string",
      "last_updated": "ISO8601",
      "approved_by": ["string"],
      "integrity_state": "OK | MISSING_FILE | BROKEN_DEPENDENCY | UNRESOLVED_DEPENDENCY | null",
      "effective_status": "string | null"
    }
  }
}
```

### Field Definitions

| Field | Type | Description |
| ----- | ---- | ----------- |
| `file` | string | Relative file path from project root |
| `status` | enum | Formal lifecycle status — governance history; never rewritten by `delta refresh` |
| `version` | string | Current version string (e.g., `"v0.3"`, `"v1.0"`) |
| `last_updated` | ISO8601 | Timestamp of last status change |
| `approved_by` | string array | Auto-populated from audit records with APPROVED verdict; do not edit manually |
| `integrity_state` | enum or null | Filesystem/dependency validity written by `delta refresh` — `null` means refresh has not been run |
| `effective_status` | string or null | Computed usable status for gate checks — equals `status` when `integrity_state = OK`; gate commands use `effective_status` when present, falling back to `status` |

**Integrity field rule:** `integrity_state` and `effective_status` are written atomically by `delta refresh`. They do not modify `status` — lifecycle history is preserved. Gate commands call `getEffectiveStatus(entry)` which returns `effective_status || status`.

### §4.1 — Document Status Values

| Status | Meaning | Used by |
| ------ | ------- | ------- |
| `DRAFT` | Created but content not complete — pre-review state | PDC only |
| `PENDING` | Created, not yet under review | DI, STRAT, WO, STR, IMPL, WALK, DIR-STR |
| `APPROVED` | Approved by required reviewers | (legacy — superseded by `audit_records`) |
| `IN_PROGRESS` | Active execution target | WO, STR, DIR-STR |
| `COMPLETE` | Execution finished, verified — eligible for lock | All primary governance artifacts |
| `SUPERSEDED` | Replaced by newer version — no longer authoritative | WO |
| `LOCKED` | Version-sealed, immutable — lock is terminal for that artifact version | All primary governance artifacts |

**Note:** PDC uses `DRAFT` as its initial state (instead of `PENDING`) because PDC content is authored incrementally before the Section 15a checklist can be verified. All other primary governance artifacts start as `PENDING`.

### §4.2 — Integrity State Values

| `integrity_state` | `effective_status` | Meaning |
| ----------------- | ------------------ | ------- |
| `null` | (uses `status`) | `delta refresh` has not been run; gates fall back to raw `status` |
| `OK` | equals `status` | File exists on disk and all dependency chain requirements are met |
| `MISSING_FILE` | `BROKEN` | File recorded in `document_states` is absent from the filesystem |
| `BROKEN_DEPENDENCY` | `BLOCKED` | File exists but an upstream dependency (same version chain) is `MISSING_FILE` or `BROKEN_DEPENDENCY` |
| `UNRESOLVED_DEPENDENCY` | `BLOCKED` | Version cannot be determined for the upstream or this artifact — version field missing and filename contains no `-vX.Y` pattern; cascade is blocked rather than propagated globally |

**Cascade order:** DI → STRAT → WO → STR → IMPL/WALK → DIR-STR → PDC. Cascade is **strict version-matched**: a broken artifact at version vX only marks downstream entries of the same vX as `BROKEN_DEPENDENCY`. If the version of either the upstream or downstream artifact cannot be resolved (no `version` field, no `-vX.Y` in filename), the downstream entry is marked `UNRESOLVED_DEPENDENCY` instead.

**Recovery:** Run `delta refresh` again after restoring missing files or adding version metadata to recalculate; integrity state is fully recomputed on each run. To clear `UNRESOLVED_DEPENDENCY`, add a `version` field to the artifact entry in `progress.json` or rename the file to include `-vX.Y` before `.md`.

**CSO exception:** CSO lifecycle state lives in `cso_states`, not `document_states`. CSO is supporting context, not a primary gate artifact, and is not subject to `delta refresh` cascade.

---

## §5 — Override Record Schema

`overrides` is an array of override records. New records are appended; existing records are never deleted or modified (only `status` transitions are permitted).

```json
{
  "overrides": [
    {
      "override_id": "string",
      "scope": "wo_gate | strat_gate | document_order | agent_boundary",
      "reason": "string",
      "declared_at": "ISO8601",
      "expires": "session | <condition_string> | ISO8601",
      "declared_by": "director",
      "status": "active | expired | revoked",
      "revoked_at": "ISO8601 | null"
    }
  ]
}
```

### Field Definitions

| Field | Type | Description |
| ----- | ---- | ----------- |
| `override_id` | string | Auto-generated unique identifier (e.g., `"OVR-20260509-001"`) |
| `scope` | enum | What the override permits — closed vocabulary |
| `reason` | string | Director-provided rationale |
| `declared_at` | ISO8601 | Declaration timestamp |
| `expires` | string | Expiry condition: `"session"`, a condition string, or ISO8601 |
| `declared_by` | string | Always `"director"` |
| `status` | enum | `"active"`, `"expired"`, or `"revoked"` |
| `revoked_at` | ISO8601 or null | Set when status transitions to `"revoked"` |

### §5.1 — Scope Closed Vocabulary

| Scope | Effect |
| ----- | ------ |
| `wo_gate` | Permits `delta wo new` while prior WO is `IN_PROGRESS` |
| `strat_gate` | Permits WO creation without `LOCKED` STRAT |
| `document_order` | Permits out-of-sequence document creation |
| `agent_boundary` | Permits cross-role document access (rare, Director-only) |

---

## §6 — Gate Transition Record Schema

`gate_transitions` is an append-only log. Every CLI operation that checks or modifies a gate appends a record here.

```json
{
  "gate_transitions": [
    {
      "event_id": "string",
      "operation_id": "string",
      "domain": "string",
      "action": "string",
      "from_state": "string | null",
      "to_state": "string | null",
      "gate_result": "passed | blocked | bypassed",
      "timestamp": "ISO8601",
      "override_id": "string | null",
      "agent": "string"
    }
  ]
}
```

### Field Definitions

| Field | Type | Description |
| ----- | ---- | ----------- |
| `event_id` | string | Auto-generated unique identifier |
| `operation_id` | string | The operation that triggered this gate check |
| `domain` | string | CLI domain of the operation |
| `action` | string | CLI action of the operation |
| `from_state` | string or null | State before the transition |
| `to_state` | string or null | State after the transition (null if blocked) |
| `gate_result` | enum | `"passed"` (normal), `"blocked"` (gate rejected), `"bypassed"` (override active) |
| `timestamp` | ISO8601 | Event timestamp |
| `override_id` | string or null | Set to the active override_id when `gate_result = "bypassed"` |
| `agent` | string | Role identifier of the agent that invoked the operation |

---

## §7 — Logs Registry Schema

`logs_registry` is an index of all session-level logs (CSOs) and significant document creation events. It is not the documents themselves — it is a navigational index.

```json
{
  "logs_registry": [
    {
      "log_id": "string",
      "type": "CSO | WO | STR | IMPL | WALK | PDC",
      "file": "string",
      "session_date": "ISO8601",
      "agent": "string",
      "related_wo": "string | null",
      "status": "active | superseded | archived"
    }
  ]
}
```

### Field Definitions

| Field | Type | Description |
| ----- | ---- | ----------- |
| `log_id` | string | Unique identifier for this log entry |
| `type` | enum | Document type |
| `file` | string | Relative file path |
| `session_date` | ISO8601 | Date the document was created |
| `agent` | string | Creating agent role |
| `related_wo` | string or null | File name of the WO this log is associated with |
| `status` | enum | `"active"` (current), `"superseded"` (replaced), `"archived"` (moved to 99_Archive/) |

---

## §8 — `project.json` Schema

`project.json` is the **project identity file**. It lives at the project root (not inside `Delta/`). It is distinct from `progress.json` (workflow state). It records stable project identity and lifecycle status.

```json
{
  "schema_version": "1.0.0",
  "project_id": "string",
  "project_name": "string",
  "type": "lite | full",
  "status": "active | closed",
  "created_at": "ISO8601",
  "closed_at": "ISO8601 | null",
  "delta_path": "Delta/",
  "ecosystem_version": "string"
}
```

### Field Definitions

| Field | Type | Description |
| ----- | ---- | ----------- |
| `schema_version` | string | Schema version of this file |
| `project_id` | string | Numeric project identifier (e.g., `"002"`) |
| `project_name` | string | Human-readable project name |
| `type` | enum | `"lite"` or `"full"` — determines which Delta subfolders were scaffolded |
| `status` | enum | `"active"` — project is open; `"closed"` — project is closed but resumable |
| `created_at` | ISO8601 | Timestamp of initial `delta project start` |
| `closed_at` | ISO8601 or null | Timestamp of `delta project end`; null when active |
| `delta_path` | string | Relative path to the Delta governance layer (always `"Delta/"`) |
| `ecosystem_version` | string | Delta ecosystem version this project was initialized under |

### Status Transitions

| Transition | Operation | Effect |
| ---------- | --------- | ------ |
| null → `active` | `delta project start` (new) | Project created |
| `active` → `closed` | `delta project end` | `status=closed`, `closed_at` set |
| `closed` → `active` | `delta project start` (resume) | `status=active`, `closed_at` cleared |

---

## §9 — `progress.json` Initialization

When a new project is initialized via `delta session bootstrap` with no existing `progress.json`, the CLI creates an empty baseline:

```json
{
  "schema_version": "1.0.0",
  "project_id": "{PROJECT_ID}",
  "project_name": "{PROJECT_NAME}",
  "last_updated": "{ISO8601}",
  "workflow_state": {
    "current_phase": "strategy",
    "di_locked": false,
    "active_di": null,
    "active_di_version": null,
    "strat_locked": false,
    "active_strat": null,
    "active_strat_version": null,
    "active_wo": null,
    "active_wo_state": null,
    "pdc_locked": false,
    "active_pdc": null
  },
  "document_states": {},
  "overrides": [],
  "gate_transitions": [],
  "logs_registry": []
}
```

---

## §8 — `audit_records` Schema

`audit_records` is an append-only array of audit verdict records. Once written, audit records are immutable — only `conditions_status` may be updated via `delta audit resolve` or `delta audit waive`.

```json
{
  "audit_records": [
    {
      "audit_id": "AUD-20260508143012000-AB12CD",
      "artifact_path": "Delta/02_Blueprint/ANT-WO-008-v0.1.md",
      "artifact_type": "wo | strat | str | impl | walk | di",
      "actor": "Director | GPT | PPX | ANT | CDC",
      "verdict": "APPROVED | REJECTED | CONDITIONAL_APPROVAL",
      "conditions_status": "NONE | OPEN | RESOLVED | WAIVED_BY_DIRECTOR",
      "cso_reference": "string | null",
      "note": "string | null",
      "timestamp": "ISO8601",
      "satisfies_lock_gate": true
    }
  ]
}
```

### Field Definitions

| Field | Type | Description |
| ----- | ---- | ----------- |
| `audit_id` | string | Globally unique, auto-generated identifier (AUD- prefix) |
| `artifact_path` | string | Full relative path to the artifact under audit |
| `artifact_type` | enum | Type of artifact: `wo`, `strat`, `str`, `impl`, `walk`, `di` |
| `actor` | enum | Who issued the verdict: `Director`, `GPT`, `PPX`, `ANT`, `CDC` |
| `verdict` | enum | Verdict: `APPROVED`, `REJECTED`, or `CONDITIONAL_APPROVAL` |
| `conditions_status` | enum | For CONDITIONAL_APPROVAL: `NONE`, `OPEN`, `RESOLVED`, `WAIVED_BY_DIRECTOR` |
| `cso_reference` | string or null | Optional CSO filename linked to this audit record |
| `note` | string or null | Optional rationale or comment |
| `timestamp` | ISO8601 | When the verdict was recorded |
| `satisfies_lock_gate` | boolean | True if verdict is APPROVED, or CONDITIONAL_APPROVAL with RESOLVED/WAIVED_BY_DIRECTOR |

### Rules

1. Audit records are **append-only** — never deleted, never overwritten (except `conditions_status` transitions).
2. When an APPROVED verdict is recorded, the actor is auto-populated to the target document's `approved_by` array.
3. When `--cso` is specified, the audit_id is auto-linked to the CSO's `linked_audit_records`.
4. Lock gates (§10) read `satisfies_lock_gate` to determine if a verdict unlocks the gate.
5. CSO is never an `actor` — CSO is a document, not a verdict issuer.

---

## §9 — `cso_states` Schema

`cso_states` is a map keyed by CSO filename. Each entry tracks the lifecycle of a Cognitive State Object. CSOs are **optional supporting documents** — they are never a lock gate requirement.

```json
{
  "cso_states": {
    "CSO-WO-008-v0.1.md": {
      "cso_id": "CSO-WO-008-v0.1",
      "target_artifact": "Delta/02_Blueprint/ANT-WO-008-v0.1.md",
      "target_type": "wo | strat | str",
      "source": "conversation | meeting | migration | director_notes",
      "summary": "string | null",
      "captured_intent": "string | null",
      "key_decisions": ["string"],
      "open_questions": ["string"],
      "linked_audit_records": ["AUD-..."],
      "status": "DRAFT | COMPLETE | LOCKED | SUPERSEDED",
      "created_at": "ISO8601",
      "updated_at": "ISO8601"
    }
  }
}
```

### Field Definitions

| Field | Type | Description |
| ----- | ---- | ----------- |
| `cso_id` | string | CSO identifier (filename without `.md`) |
| `target_artifact` | string or null | Full path to linked artifact |
| `target_type` | enum or null | Type of linked artifact |
| `source` | enum | Origin: `conversation`, `meeting`, `migration`, `director_notes` |
| `summary` | string or null | Brief summary of CSO content |
| `captured_intent` | string or null | Explicit intent captured from conversation |
| `key_decisions` | string array | Key decisions documented in this CSO |
| `open_questions` | string array | Unresolved questions |
| `linked_audit_records` | string array | Audit IDs that reference this CSO (auto-populated) |
| `status` | enum | CSO lifecycle: `DRAFT` → `COMPLETE` → `LOCKED` / `SUPERSEDED` |
| `created_at` | ISO8601 | Creation timestamp |
| `updated_at` | ISO8601 | Last update timestamp |

### CSO Lifecycle States

| Status | Meaning | Transition |
| ------ | ------- | ---------- |
| `DRAFT` | Created, content being written | → `COMPLETE` or `LOCKED` |
| `COMPLETE` | Content finalized | → `LOCKED` |
| `LOCKED` | Immutable historical record | Terminal (no further transitions) |
| `SUPERSEDED` | Replaced by newer CSO | Terminal |

### Rules

1. CSO is a **supporting document** — it never blocks a lock gate. Lock succeeds with or without CSO.
2. CSO is never an audit `actor`. CSO references are stored in `cso_reference`, not in `actor`.
3. `linked_audit_records` is auto-populated when an audit record is created with `--cso`.
4. CSO content is immutable after `LOCKED` — locked CSOs are historical records only.

---

## §10 — Audit Policy & Lock Gates

Lock gates (`delta strat lock`, `delta wo lock`, `delta str lock`) consult `audit_records` against the artifact's audit policy (defined in CLI config) before allowing the transition.

### Default Audit Policy

| Artifact | Required Approvers | Notes |
| -------- | ------------------ | ----- |
| STRAT | Director, GPT, PPX | All three must have satisfied verdicts before lock |
| WO (low risk) | Director | GPT/PPX optional |
| WO (high risk) | Director | GPT/PPX recommended but not required |
| STR (low risk) | Director | GPT/PPX optional |

### Lock Gate Check Rules

A lock gate is satisfied when:
- All `required_approvers` have at least one audit record with `satisfies_lock_gate = true`
- No required approver has an unresolved `REJECTED` verdict
- No required approver has a `CONDITIONAL_APPROVAL` with `conditions_status = OPEN`

Bypass: `delta override declare --scope audit_gate --reason "..." --expires session`

CSO is **not checked** by lock gates — `cso_required` is always `false` in default policy.

---

## §11 — Runtime Authority Rules

1. `progress.json` is the single source of truth for current workflow state. No agent may infer workflow state from document names, file timestamps, or conversation history.
2. All state transitions must be written atomically — `workflow_state`, `document_states`, and the corresponding `gate_transitions` record must be updated in the same write.
3. `progress.json` is a project-level file — it does not belong to any agent. All agents read it; the CLI writes it.
4. Override records are append-only. Status fields (`status`, `revoked_at`) may be updated; all other fields are immutable after creation.
5. `gate_transitions` is append-only. No records are ever modified or deleted.
6. `logs_registry` entries may have their `status` field updated (e.g., from `"active"` to `"superseded"`), but other fields are immutable after creation.
7. If `progress.json` does not exist at session bootstrap, the CLI creates it with the initialization template (§8). Absence is not an error — it signals a new project.
8. If `progress.json` is present but has a different `schema_version` than the current CLI expects, the CLI surfaces a migration warning before proceeding.

---

## References

- CLI gating doctrine: `DELTA-CLI-ARCHITECTURE.md` §6
- Director Override doctrine: `DELTA-CLI-ARCHITECTURE.md` §5
- Runtime vs markdown authority boundary: `DELTA-CLI-ARCHITECTURE.md` §4
- WO lifecycle states: `DELTA-CLI-ARCHITECTURE.md` §6.1
- Operation definitions: `DELTA-OPERATION-REGISTRY.json` (schema: `DELTA-OPERATION-REGISTRY-SCHEMA.md`)

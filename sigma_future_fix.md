# Sigma Future Fix Notes

## Summary

Sigma is valuable for CanopySense because it enforces clear intent, planning, execution evidence, and Director approval gates. The governance model helps prevent scope drift and makes review findings easier to trace.

The main improvement area is not the concept. It is CLI and state-management ergonomics. Some flows are too easy to desynchronize or require mechanical state transitions that feel unnatural after evidence is already complete.

## What Works Well

- Gate discipline prevents coding before intent and plan are clear.
- Separate artifacts create a useful audit trail:
  - Intent Doc
  - Plan Doc
  - Execution Evidence
  - Roadmap
  - Closure Doc
- Role boundaries are helpful for large projects with backend, frontend, DB, pipeline, security, and deployment concerns.
- Test contracts make review more precise. Example: v1.10 caught the manager `full_name` invite issue and inactive-login token issue because the Plan Doc had explicit requirements.
- Director approval authority is clear and reduces accidental locking or scope changes.

## Main Pain Points

### 1. Active Artifact Ambiguity

When multiple Plan Doc drafts existed at once, the active plan shifted in a surprising way. This created risk of locking the wrong artifact.

Current workaround:

```bash
sigma plan activate --v v1.11
sigma plan lock
```

Better direction:

```bash
sigma plan lock --v v1.11
```

Version-targeted lock commands would reduce accidental state mistakes.

### 2. Rigid Execution Evidence State Transitions

Execution Evidence had complete reviewed evidence, but the CLI required:

```text
DRAFT -> BUILDING -> TESTING -> COMPLETED -> LOCKED
```

This is conceptually valid, but the CLI flow felt mechanical when the evidence was already complete.

Better direction:

```bash
sigma exec lock --finalize
```

This command could show a confirmation prompt and then safely advance through required states before locking.

### 3. Error Messages Need Exact Next Steps

Example issue:

```text
Active DEV-EXEC must be in COMPLETED state to lock. Run: sigma exec advance complete
```

But the current state was `DRAFT`, so `advance complete` failed.

Better error:

```text
Cannot lock DEV-EXEC v1.10.
Current state: DRAFT
Required path:
  sigma exec advance building
  sigma exec advance testing
  sigma exec advance complete
  sigma exec lock
```

### 4. Roadmap Lifecycle Needs Versions

Roadmap was marked `LOCKED`, but real project planning still required updates when v1.11, v1.12, and v1.13 were added.

Better direction:

```text
ROADMAP v1 LOCKED
ROADMAP v2 DRAFT
ROADMAP v2 LOCKED
```

This would preserve the meaning of locked artifacts while allowing formal roadmap revisions.

### 5. Parallel Draft Policy Should Be Explicit

The Sigma fix that blocks normal `plan new` when another DRAFT exists is good.

Recommended addition:

```bash
sigma plan new --parallel-draft
```

This should require explicit Director confirmation and clearly mark the risk:

- multiple drafts exist
- active draft must be selected before lock
- commands should prefer `--v` targeting

### 6. Lock Preflight Should Be Standard

Before any lock, Sigma should show a preflight summary:

```text
Artifact: Plan Doc v1.11
State: DRAFT
Intent Ref: v2
Stale Intent: no
Known Draft Conflicts: v1.12 exists
Gate Impact: Gate 2 will open

Type APPROVE to lock.
```

This reduces accidental locks and makes Director authority more concrete.

## Recommended Future Fixes

1. Add version-targeted lock commands:
   - `sigma plan lock --v v1.11`
   - `sigma exec lock --v v1.11`

2. Add finalize lock command for Execution Evidence:
   - `sigma exec lock --finalize`

3. Improve CLI error messages with full required transition paths.

4. Add formal Roadmap versioning:
   - `sigma roadmap new`
   - `sigma roadmap lock`
   - `sigma roadmap status`
   - `sigma roadmap list`

5. Keep draft conflict guard, but add explicit parallel draft mode:
   - `sigma plan new --parallel-draft`

6. Add lock preflight summaries for Plan Doc and Execution Evidence.

7. Add safer current-state diagnostics:
   - show active artifact
   - show all DRAFT artifacts
   - warn if active artifact is not the latest draft

8. Prefer command suggestions that include the artifact version.

## Overall Verdict

Sigma is worth keeping. It is especially useful for a project like CanopySense, where production readiness requires coordinated work across product scope, admin governance, backend APIs, database migrations, frontend UX, pipeline operations, security, and deployment.

The governance model is strong. The next improvement should focus on CLI ergonomics, explicit version targeting, better roadmap revision handling, and safer lock workflows.

# CDC-IMPL-004-v0.1 — Pre-Implementation Plan

> [!IMPORTANT]
> **Dependencies**: `ANT-WO-004-v0.1` (LOCKED). **Governing STRAT**: `GMN-STRAT-001-v1.0` (LOCKED). **STR**: `ANT-STR-004-v0.1` (PENDING). **Status**: PENDING ANT/Director approval — no code changes until approved.

## 1. Metadata

| Field | Value |
| :--- | :--- |
| **Project ID** | 001 |
| **Document Type** | Pre-Implementation Plan (IMPL) |
| **Version** | v0.1 |
| **Status** | PENDING — awaiting ANT/Director approval |
| **Lead Developer** | CDC |
| **Work Order Ref** | `ANT-WO-004-v0.1` |
| **STR Ref** | `ANT-STR-004-v0.1` |

---

## 1b. Environment & Stack

| Field | Value |
| :--- | :--- |
| **OS / Platform** | Linux (Fedora 43) |
| **Runtime / Language** | Node.js ≥ 18 (Delta CLI source); Python 3.x (CanopySense src/tests) |
| **Key Tools** | `node:test` (Delta CLI test runner), `npm test`, `docker compose`, `delta` CLI |
| **Environment** | Local dev; no real GEE/GCP/PostGIS credentials |

---

## 2. Task Interpretation & Approach

**What must be built**: WO-004 has two parts.

**Part A — CanopySense source/test migration repair**: Fix stale `03_Build` / `04_Test` path references left after the project-layer migration to `src/` and `tests/`. Success is: `run_test.py` fails only on real external prerequisites, not path drift; Docker Compose config resolves a Dockerfile that exists; no execution-affecting legacy paths remain in `src/` or `tests/`.

**Part B — Delta CLI governance repair (Delta master repo)**: Fix two root bugs in the Delta CLI source that caused the CanopySense governance drift, add regression tests, and add a safe admin command so the Director can prune the stale duplicate DI keys currently poisoning `delta refresh`. Success is: `delta sync registry` and `delta refresh` pass clean in CanopySense after Director runs the new prune command and reinstalls the CLI.

**Proposed approach**:
- **Part B first** — the governance bugs in Delta CLI are the upstream root cause. Fix source → test → reinstall → repair CanopySense state → then do Part A.
- In Delta CLI: silent-fallback strategy for `sync.js` (try Delta/ then project root) — no registry schema change needed, backward-compatible.
- In Delta CLI: reject-loud strategy for `--file` paths — fail with actionable error message rather than silently normalizing, preventing future state corruption.
- New `delta admin prune-stale` command: removes document_states keys that contain a `/` (indicating a path was accepted as a key instead of a bare filename), then verifies no key conflict exists before writing.
- v0.4 disk artifacts (ANT-STR-003-v0.4.md, CDC-IMPL-003-v0.4.md, CDC-WALK-003-v0.4.md): ESCALATION — no safe non-destructive CLI command exists to import them; Director decides whether to register, supersede, or archive.

**Rationale**: Fixing Delta CLI first ensures that after the repair, any future `delta di new`, `delta strat new`, etc. will never accept path strings as keys again. The silent-fallback for sync.js is the smallest possible change with no registry schema churn.

---

## 2b. Sequential Reasoning & Branching Analysis

**Execution order (cascade dependency)**:
1. Fix Delta CLI source (`sync.js`, `di.js`, `strat.js`, `wo.js`, `str.js`, `impl.js`, `walk.js`)
2. Add CLI regression tests (sync root-file resolution, --file path rejection)
3. Add `delta admin prune-stale` command
4. Run `npm test` — must pass clean
5. `npm install -g` (reinstall CLI) or equivalent local reinstall
6. Director runs `delta admin prune-stale` in CanopySense — removes the two bad DI keys
7. `delta refresh` in CanopySense → 0 issues
8. `delta sync registry` in CanopySense → 0 issues
9. Part A: fix CanopySense `src/` and `tests/` path references
10. Verify WO-004 success indicators

**Branch A (Chosen)**: Silent-fallback path resolution in `sync.js`.
- Pro: zero registry schema change; zero migration of existing DELTA-REGISTRY.json files; backward-compatible.
- Con: slightly less explicit than marking root files in the registry.

**Branch B (Fallback)**: Add `"location": "root" | "delta"` field to DELTA-REGISTRY.json entries.
- Would require updating all deployed DELTA-REGISTRY.json copies.
- Deferred — only viable if Branch A has unintended side-effects.

---

## 2c. Active Agent Skills

| Skill ID | Status | Rationale |
|---|---|---|
| (none) | — | WO §10: No skills authorized for this WO |

---

## 3. Authority Levels & Implementation Constraints

Inherited from `ANT-WO-004-v0.1` §6 and §7:

- **Level 1 (Non-Negotiable)**:
  - Do NOT manually edit `Delta/progress.json`, `project.json`, `Delta/DELTA-REGISTRY.json`, or `~/.delta/project_registry.json`.
  - Do NOT delete locked historical WOs or historical implementation evidence.
  - Do NOT commit secrets, service-account keys, real API keys, or contractor credentials.
  - CDC Action: Any of these would be a hard REJECT; escalate to Director.

- **Level 2 (Guided)**:
  - CDC may choose the exact shape of the admin command, the file path helper structure, and test harness details as long as success indicators remain measurable.
  - CDC Action: Reject-loud (error + exit 1) is chosen over silent normalization for --file — justify: silent normalization would hide user mistakes and create hard-to-debug state.

- **Level 3 (Preference)**:
  - Keep path constants centralized where practical; update comments near changed behavior.
  - Update user-facing runtime docs only where stale commands would cause script failure.

- **Level 4 (Freedom)**:
  - Refactoring internals of Docker packaging, test helpers, variable naming.

---

## 4. Technical Decision Log

| # | Decision | Chosen | Trade-off | Authority |
|---|---|---|---|---|
| D1 | sync.js bridge file resolution | Try `deltaDir` first; fall back to `projectRoot` | Heuristic, but correct for all known registry entries | L2 |
| D2 | --file path validation | Reject with error if `opts.file` contains `/` | Fail-loud prevents silent state corruption; user sees actionable message | L2 |
| D3 | Admin command for stale keys | `delta admin prune-stale` — removes keys with `/` in name, writes only on clean confirmation | Scoped to malformed keys only; does not touch valid keys | L2 |
| D4 | v0.4 artifact registration | ESCALATE — no safe CLI import path; Director decides | Preserves governance integrity; CDC records gap in WALK | L1 |
| D5 | `04_Test` → `tests/` in CanopySense | Replace execution-affecting runtime paths; leave historical comments clearly marked | Minimal change surface; keeps git history readable | L3 |
| D6 | `03_Build` → `src/` in CanopySense | Replace `sys.path.insert` and import-path references in test runner | Same as D5 | L3 |

---

## 5. Files to Create / Modify

### Part B — Delta CLI (`/home/dikoharyadhanto/Documents/Works/Projects/Delta/`)

| File | Action | Purpose | WO Requirement |
| :--- | :---: | :--- | :--- |
| `src/commands/sync.js` | MOD | Fallback to project root when bridge file not found in Delta/ | §4.2 item 3 |
| `src/commands/di.js` | MOD | Reject `--file` containing `/` with error + exit 1 | §4.2 item 1 (prevents future duplicates) |
| `src/commands/strat.js` | MOD | Same `--file` path rejection | §4.2 item 1 |
| `src/commands/wo.js` | MOD | Same `--file` path rejection | §4.2 item 1 |
| `src/commands/str.js` | MOD | Same `--file` path rejection | §4.2 item 1 |
| `src/commands/impl.js` | MOD | Same `--file` path rejection | §4.2 item 1 |
| `src/commands/walk.js` | MOD | Same `--file` path rejection | §4.2 item 1 |
| `src/commands/admin.js` | CREATE | `delta admin prune-stale` command | §4.2 item 1 (repair path) |
| `bin/delta.js` | MOD | Register `adminCmd` | wires up admin command |
| `test/sync.test.js` | CREATE | Regression: root bridge file found; doubled path rejected | §5 items 7–8 |
| `test/lifecycle.test.js` | CREATE | Regression: `--file` with `/` exits 1 across all lifecycle commands | §5 items 7–8 |

### Part A — CanopySense (`/home/dikoharyadhanto/Documents/Works/Projects/CanopySense/`)

| File | Action | Purpose | WO Requirement |
| :--- | :---: | :--- | :--- |
| `tests/docker-compose.yml` | MOD | `dockerfile: 04_Test/Dockerfile.patcher` → `dockerfile: tests/Dockerfile.patcher` | §4.1 item 3 |
| `tests/Dockerfile.patcher` | MOD | Copy paths: `04_Test/` → `tests/`, `03_Build/` → `src/` | §4.1 item 3 |
| `tests/run_test.py` | MOD | `sys.path.insert(0, str(_ROOT / "03_Build"))` → `str(_ROOT / "src")` | §4.1 item 2 |
| `src/patcher_local.py` | MOD | `_ENV_FILE` default: `04_Test/.env` → `tests/.env` | §4.1 item 4 |
| `src/engine_launcher.py` | MOD | `_OUTPUT_DIR`, `_ENV_FILE` defaults: `04_Test/...` → `tests/...` | §4.1 item 4 |
| `src/deploy/engine_launcher.py` | MOD | Same as above | §4.1 item 4 |
| `src/historical_backfill.py` | MOD | `_HISTORICAL_OUTPUT_DIR`, `_ENV_FILE` defaults: `04_Test/...` → `tests/...` | §4.1 item 4 |

---

## 6. Key Abstractions & Logic

### sync.js root-fallback logic (pseudo-code)

```
fpath = path.join(deltaDir, doc.file)
if NOT exists(fpath):
    rootPath = path.join(path.dirname(deltaDir), doc.file)
    if exists(rootPath):
        fpath = rootPath   // bridge file found at project root — OK
// if neither exists, fpath is still the original and existence check below reports the issue
if NOT exists(fpath):
    issues.push(...)
```

### --file path guard (applied to all lifecycle `new` commands)

```
if (opts.file && opts.file.includes('/')) {
  console.error(ERR: --file must be a bare filename, not a path. Got: <opts.file>)
  console.error(  Use: --file <path.basename(opts.file)>)
  process.exit(1)
}
```

### delta admin prune-stale logic

```
load progress
staleKeys = Object.keys(document_states).filter(k => k.includes('/'))
for each staleKey:
    check that a clean version of basename(staleKey) exists as a separate key
    print: will remove staleKey (file: stored_path)
if staleKeys.length === 0: print "no stale keys found"
else: print summary, remove stale keys, save progress
```

---

## 7. Dependency Changes

None. No new packages. All changes use existing Node.js built-ins and existing Delta CLI utilities.

---

## 8. Technical Debt & Residual Risks

- [ ] **v0.4 artifact registration** — `ANT-STR-003-v0.4.md`, `CDC-IMPL-003-v0.4.md`, `CDC-WALK-003-v0.4.md` exist on disk but have no CLI import command. CDC will document this as a Director escalation in WALK. Risk: these artifacts remain invisible to `delta list/status` until Director decides their fate.
- [ ] **tests/.env does not exist** — `patcher_local.py`, `engine_launcher.py`, `historical_backfill.py` all default to `tests/.env`. After the path fix, if `tests/.env` does not exist, the scripts will silently skip environment loading (same behavior as before with `04_Test/.env`). No runtime regression expected; behavior is identical.
- [ ] **`tests/generate_test_blocks.py` fixture** — WO-004 §5.3 requires this to either produce `tests/test_blocks.geojson` or fail with an actionable message. CDC will read the file and add/verify the actionable error path. No test fixture will be committed (no real shapefile available locally without external prerequisite).
- [ ] **`src/core_engine/map_previewer.py`** — has a docstring comment referencing `04_Test/result_output`. This is a documentation-only reference. CDC will assess whether it's execution-affecting; if comment-only, it will be left with a legacy note per WO §6.

---

## 9. IMPL Completeness Checklist

- [x] Task interpretation reflects ANT-WO-004 summary
- [x] Proposed approach well-reasoned and justified
- [x] All Level 1 constraints listed and understood
- [x] All Level 2 constraints listed with compliance justification
- [x] Technical decisions documented with trade-off analysis
- [x] Files to create/modify identified
- [x] No new dependencies
- [x] Risks identified: v0.4 artifacts escalated, .env absence documented
- [x] No Level 1 violations
- [x] Ready for ANT/Director review and approval

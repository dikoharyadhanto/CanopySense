# GMN-IGN-000-v1.0 (Claude Code Ignoring Rules)
> [!IMPORTANT]
> **Logic Dependencies**: Requires `GMN-PROJ`.
## 1. Metadata
| Field | Value |
| :--- | :--- |
| **Project ID** | 000 |
| **Document Type** | Exclusion/Ignore Config (IGN) |
| **Version** | v1.0 |
| **Status** | Active |
| **Architect** | Gemini (GMN) |

---

## 2. Instructions for Director
> **Deployment**: Copy the block below and save it as a file named **`.claudesignore`** in the project root directory. This will prevent Claude Code from scanning irrelevant data.

---

## 3. The `.claudesignore` Content:
```text
# --- AI Ecosystem Exclusions ---

# 1. Historical Data (The Most Critical)
99_Archive/
*/99_Archive/
**/*-v0.*.md
**/*-v1.*.md
# (Except the active version)

# 2. Strategic/Discussion Logs
01_Log/
*/01_Log/
**/*.sum.md

# 3. Supplemental & Personal Data
05_Reference/
99_Docs/

# 4. Global Configuration (Already read at session start)
00_Global_Rules/

# 4. Standard Technical Noise
.git/
node_modules/
.venv/
__pycache__/
dist/
build/
*.pyc
.DS_Store
.env
```

---

## 4. Behavioral Rule for CDC
> **Note to Antigravity**: If Claude Code attempts to reference an archived file, you must issue a **Strict Halt** and redirect them to the active source in `02_Blueprint/`.

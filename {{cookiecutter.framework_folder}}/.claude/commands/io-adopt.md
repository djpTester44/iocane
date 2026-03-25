---
name: io-adopt
description: Apply Iocane framework to an existing codebase with intelligent content migration and design extraction.
---

> **[CRITICAL] CONTEXT LOADING**
>
> 1. Load the planning rules: `view_file .claude/rules/planning.md`
> 2. Load the extraction tool: `.claude/scripts/extract_structure.py`

# WORKFLOW: ADOPT EXISTING REPOSITORY

**Objective:** Configure the Iocane harness for this project, then extract the structural skeleton and reverse-engineer the capabilities of the existing codebase to establish a foundational PRD.

**Context:**

* Scope: Brownfield repository integration. Harness files are assumed to be present (installed via `uvx` before this workflow runs).
* Output: configured harness (`pyproject.toml`, `CLAUDE.md`, `.iocane/`) + `plans/current-state.md` + draft `plans/PRD.md`.

**Procedure:**

### 1. HARNESS CONFIGURATION

#### 1a. Pre-flight gate

* **Check:** Verify `.claude/` exists in the repo root.
* **If missing:** Stop immediately. Output: "Harness not found. Run the iocane install command (`uvx ...`) to pull harness files before running `/io-adopt`." Do not proceed.
* **Check:** Verify `.claude/hooks/` contains `.sh` files.
* **Action:** Make all hooks executable: `bash -c "chmod +x .claude/hooks/*.sh"`

#### 1b. Detect project identity

* **Action:** Read the existing `pyproject.toml` (if present) to extract `[project].name` and `[project].description`.
* **Fallback:** If `pyproject.toml` is absent or fields are empty, read the first `#`-headed line of `README.md` for the project name, and the first non-header paragraph for the description.
* **Store:** Hold `PROJECT_NAME` and `PROJECT_DESCRIPTION` for use in steps 1c and 1d.

#### 1c. Merge pyproject.toml

* **If `pyproject.toml` is absent entirely:** Create it from `.claude/templates/pyproject.toml.template`, substituting `PROJECT_NAME` and `PROJECT_DESCRIPTION`. Skip the merge step.
* **If `pyproject.toml` exists:** Run the deterministic merge script:

  ```bash
  uv run .claude/scripts/merge_pyproject.py --write
  ```

  This script compares the existing file against harness-required config and applies only the missing pieces. It never removes or overwrites existing keys. List-type fields (`ruff select`, `ruff ignore`, dev packages) use union merge. Scalar divergences (e.g. project uses `line-length = 79`) are reported but left unchanged — surface these to the user for manual review after the workflow completes.

#### 1d. Write CLAUDE.md

* **Action:** Read `.claude/templates/CLAUDE.md.template`.
* **Action:** Substitute `__PROJECT_NAME__` with `PROJECT_NAME` and `__PROJECT_DESCRIPTION__` with `PROJECT_DESCRIPTION`.
* **If `CLAUDE.md` already exists:** Replace only the `## System Context` section content (lines between the heading and the first `---`). Preserve everything else.
* **If `CLAUDE.md` is absent:** Write the full template with substitutions applied.

#### 1e. Bootstrap directories

* **Action:** `mkdir -p .iocane plans plans/tasks`
* **Note:** Do not overwrite `.iocane/session-start-payload.json` if it already exists.

---

### 2. CURRENT STATE ANALYSIS (Token Protection)

* **Constraint:** You are strictly forbidden from reading full legacy source files in bulk, with two exceptions: (1) files under 200 lines may be read in full, and (2) files matching entrypoint patterns (`main.py`, `app.py`, `cli.py`, `__main__.py`, `manage.py`, `wsgi.py`, `asgi.py`, `server.py`) may be read in full regardless of length. All other files require `extract_structure.py` or targeted line-range reads.
* **Action:** Run `uv run python .claude/scripts/extract_structure.py <dir>` to map the existing classes, function signatures, and data structures.
* **Action:** Create `plans/current-state.md` using the template `.claude/templates/current-state.md`.
* **Goal:** Capture the raw capabilities and data structures of the legacy code efficiently.

#### Step 2a: CONFIG INVENTORY

* **Action:** Glob for `**/*.toml`, `**/*.yaml`, `**/*.yml`, `**/*.json`, `**/*.env*` excluding `.venv/`, `node_modules/`, `.git/`.
* **Action:** Add a `## Configuration Sources` section to `plans/current-state.md` listing each file with a one-line purpose description.

#### Step 2b: WIRING SNAPSHOT

* **Action:** Identify entrypoint files using the pattern list from the token protection constraint above (`main.py`, `app.py`, `cli.py`, `__main__.py`, `manage.py`, `wsgi.py`, `asgi.py`, `server.py`).
* **Action:** Read each entrypoint and catalog: (a) concrete class instantiations, (b) global/module-level mutable state, (c) service-locator patterns.
* **Action:** Add a `## Wiring Snapshot` section to `plans/current-state.md`.
* **Note:** This is descriptive inventory only — Protocols do not exist yet in brownfield repos.

### 3. REFACTOR PRD GENERATION

* **Action:** Read `.claude/templates/PRD.md`.
* **Action:** Create `plans/PRD.md` by mapping `plans/current-state.md` into the Iocane-compliant PRD format.
* **Goal:** Rephrase legacy capabilities as "Requirements" for the refactor.
* **Guidance:**
  * Map "Capabilities" -> "User Stories"
  * Map "Data Structures" -> "Domain Models"
  * Map "File Inventory" -> "Constraints"
* **Rule:** Set `**Clarified:** False` in the new PRD header.

### 4. HANDOFF

* **Stop:** Explicitly ask user to review `plans/PRD.md`.
* **Output:** "Harness configured and legacy extraction complete. Draft PRD created at `plans/PRD.md`. **REVIEW REQUIRED.** Do not proceed until this PRD is approved. Once approved, run `/io-clarify` to resolve ambiguities, followed by `/io-init` to generate the macro-architecture."

**Safety Rules:**

* Never delete existing legacy files without approval.
* Do not hallucinate requirements not found in the extracted code skeleton.
* Never overwrite existing `pyproject.toml` sections — append only.
* Never overwrite `.iocane/session-start-payload.json` if it already exists.

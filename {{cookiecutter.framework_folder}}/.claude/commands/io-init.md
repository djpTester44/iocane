---
name: io-init
description: Bootstrap the project structure and stub roadmap from a clarified PRD. Routes to /io-specify for full roadmap generation.
---

> **[CRITICAL] CONTEXT LOADING**
>
> 1. Load the planning rules: `view_file .claude/rules/planning.md`
> 2. Load the Architecture Template: `view_file .claude/templates/project-spec.md`

# WORKFLOW: IOCANE INITIALIZATION

**Objective:** Transform a strictly clarified `plans/PRD.md` into the initial project structure and a stub `plans/roadmap.md` ready for `/io-specify` to populate.

**Position in chain:**

```
/io-clarify -> [/io-init] -> /io-specify -> /io-architect -> /io-checkpoint -> /io-plan-batch -> /validate-tasks -> dispatch-agents.sh
```

---

## 1. STATE INITIALIZATION

Before proceeding to Step 2, output the following metadata to confirm the project boundaries:

- **PRD Clarification Status:** [Must be `True` to proceed]
- **Root Directory Strategy:** [e.g., Strict `src` layout]
- **Layer 1 (Foundation):** [Target path, e.g., `src/core`]
- **Layer 2 (Utility):** [Target path, e.g., `src/lib`]
- **Layer 3 (Domain):** [Target path, e.g., `src/domain`]
- **Layer 4 (Entrypoint):** [Target path, e.g., `src/main.py`]

---

## 2. PROCEDURE

### Step A: [CRITICAL] CLARIFICATION GATE

- **Action:** Read the document header of `plans/PRD.md`.
- **Check:** Locate the `**Clarified:**` field.
- **Rule:** If the field is missing, or set to `False`, you MUST immediately HALT.
- **Output:** "HALT: The PRD has not been clarified. Run `/io-clarify` first."

---

### Step B: ANALYZE & MAP LAYERS

- **Action:** Read `plans/PRD.md` to identify the tech stack and constraints.
- **Action:** Finalize the directory mapping for this specific project:
  - **Layer 1 (Foundation):** Config, Types, and Primitives (Target: `src/core`).
  - **Layer 2 (Utility):** Stateless helpers and external clients (Target: `src/lib`).
  - **Layer 3 (Domain):** Core business logic and orchestrators (Target: `src/domain`).
  - **Layer 4 (Entrypoint):** CLI, API, or Jobs (Target: `src/main.py`).

---

### Step C: SCAFFOLD PYPROJECT.TOML

- **Rule:** If `pyproject.toml` already exists, do not scaffold — instead run:

  ```bash
  uv run .claude/scripts/merge_pyproject.py --write
  ```

  This merges only the missing harness-required config (dev packages, ruff, pytest, mypy sections) without touching existing keys. Surface any reported divergences to the user. Then skip to Step C1.
- **Action:** Extract from `plans/PRD.md`:
  - Project name (snake_case)
  - One-line description
  - Python version (default `3.12` if not specified)
- **Action:** Derive `root_packages` from the layer map in Step B. Always include `interfaces`. Example: layers rooted at `src/` → root packages are `src` and `interfaces`.
- **Action:** Run:

```bash
bash .claude/scripts/scaffold-greenfield.sh \
  --name "PROJECT_NAME" \
  --description "PROJECT_DESCRIPTION" \
  --python "PYTHON_VERSION" \
  --root-packages "src,interfaces"
```

- **Output:** `pyproject.toml` written. Runtime dependencies (`[project].dependencies`) are left empty — the human adds them with `uv add` as the project develops.
- **Note:** `[[tool.importlinter.contracts]]` is intentionally absent at this stage. `/io-architect` appends it after the layer hierarchy is finalized.

---

### Step C1: SCAFFOLD CLAUDE.md

- **Rule:** If `CLAUDE.md` already exists, skip this step entirely.
- **Action:** The `scaffold-greenfield.sh` script (invoked in Step C) also writes `CLAUDE.md` from `.claude/templates/CLAUDE.md.template`, substituting:
  - `__PROJECT_NAME__` with the project name extracted from the PRD
  - `__PROJECT_DESCRIPTION__` with the one-line description extracted from the PRD
- **Output:** `CLAUDE.md` written with localized System Context.
- **Note:** If the template is missing, the script emits a warning and continues. The root `CLAUDE.md` can be written manually in that case.

---

### Step C2: CREATE PLANS/ DIRECTORY STRUCTURE

Create the following directory scaffolding if not already present:

```
plans/
  PRD.md          (already exists — do not modify)
  roadmap.md      (stub — created in Step D)
  backlog.yaml      (create empty with standard header)
  tasks/          (empty directory — populated by /io-plan-batch)
```

Do not create `plans/plan.yaml`. Checkpoint planning is handled by `/io-checkpoint` after contracts are locked. The `tasks/` directory is intentionally empty at this stage — `/io-plan-batch` populates it.

---

### Step D: GENERATE STUB ROADMAP (`plans/roadmap.md`)

- **Action:** Create `plans/roadmap.md` with the following stub structure.
- **Purpose:** The stub establishes the document identity and PRD traceability. `/io-specify` will populate the feature entries.

```markdown
# Roadmap

**PRD version:** [version or date from PRD header]
**Status:** Draft — pending /io-specify

---

## Features

[To be populated by /io-specify]

---

## Completion Map

| Feature | Status |
|---------|--------|
| (none yet) | — |
```

- **Rule:** Do not populate feature entries here. That is `/io-specify`'s job.

---

### Step E: CREATE EMPTY BACKLOG (`plans/backlog.yaml`)

- **Action:** If `plans/backlog.yaml` does not exist, create it with the standard header:

```markdown
# Backlog

Findings from /io-review and /gap-analysis. Append-only — never delete entries.
Items marked [x] are resolved. Items marked [ ] are active.

---
```

- **Rule:** If `plans/backlog.yaml` already exists (e.g., brownfield adoption), do not overwrite it.

---

### Step F: OUTPUT

```
BOOTSTRAP COMPLETE.

pyproject.toml scaffolded (runtime deps empty -- add with uv add).
CLAUDE.md localized with project identity.
plans/roadmap.md created (stub -- ready for /io-specify).
plans/backlog.yaml initialized.

Next step: Run /io-specify to generate the dependency-ordered feature roadmap from the clarified PRD.
```

---

## 3. CONSTRAINTS

- This workflow does NOT generate `plans/project-spec.md`. That is `/io-architect`'s output.
- This workflow does NOT generate `plans/plan.yaml` or any checkpoint plan. That is `/io-checkpoint`'s output.
- This workflow does NOT generate `interfaces/*.pyi` files.
- Do not reference or create `execution-handoff-bundle.md` — that artifact is retired.
- The stub `plans/roadmap.md` must not contain feature entries. `/io-specify` owns that content.
- Layer mapping output in Step B is informational only — no files are written for it here.

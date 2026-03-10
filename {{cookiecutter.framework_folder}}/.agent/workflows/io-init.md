---
description: Bootstrap the project structure and stub roadmap from a clarified PRD. Routes to /io-specify for full roadmap generation.
---

> **[CRITICAL] CONTEXT LOADING**
>
> 1. Load the planning rules: `view_file .agent/rules/planning.md`
> 2. Load the Architecture Template: `view_file .agent/templates/project-spec.md`

# WORKFLOW: IOCANE INITIALIZATION

**Objective:** Transform a strictly clarified `plans/PRD.md` into the initial project structure and a stub `plans/roadmap.md` ready for `/io-specify` to populate.

**Position in chain:**

```
/io-clarify -> [/io-init] -> /io-specify -> /io-architect -> /io-checkpoint -> /io-orchestrate
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

### Step C: CREATE PLANS/ DIRECTORY STRUCTURE

Create the following directory scaffolding if not already present:

```
plans/
  PRD.md          (already exists — do not modify)
  roadmap.md      (stub — created in Step D)
  backlog.md      (create empty with standard header)
  tasks/          (empty directory — populated by /io-orchestrate)
```

Do not create `plans/PLAN.md`. Checkpoint planning is handled by `/io-checkpoint` after contracts are locked. The `tasks/` directory is intentionally empty at this stage — `/io-orchestrate` populates it.

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

### Step E: CREATE EMPTY BACKLOG (`plans/backlog.md`)

- **Action:** If `plans/backlog.md` does not exist, create it with the standard header:

```markdown
# Backlog

Findings from /review and /gap-analysis. Append-only — never delete entries.
Items marked [x] are resolved. Items marked [ ] are active.

---
```

- **Rule:** If `plans/backlog.md` already exists (e.g., brownfield adoption), do not overwrite it.

---

### Step F: OUTPUT

```
BOOTSTRAP COMPLETE.

plans/roadmap.md created (stub — ready for /io-specify).
plans/backlog.md initialized.

Next step: Run /io-specify to generate the dependency-ordered feature roadmap from the clarified PRD.
```

---

## 3. CONSTRAINTS

- This workflow does NOT generate `plans/project-spec.md`. That is `/io-architect`'s output.
- This workflow does NOT generate `plans/plan.md` or any checkpoint plan. That is `/io-checkpoint`'s output.
- This workflow does NOT generate `interfaces/*.pyi` files.
- Do not reference or create `execution-handoff-bundle.md` — that artifact is retired.
- The stub `plans/roadmap.md` must not contain feature entries. `/io-specify` owns that content.
- Layer mapping output in Step B is informational only — no files are written for it here.

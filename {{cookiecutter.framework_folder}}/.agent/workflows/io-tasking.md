---
description: Generate atomic TDD tasks for the Loop strictly from the Meso-State handoff.
---

> **[CRITICAL] CONTEXT LOADING**
>
> 1. Load the planning rules: `view_file .agent/rules/planning.md`
> 2. Load the Handoff Bundle: `view_file plans/execution-handoff-bundle.md`
> 3. Load the Task Template: `view_file .agent/templates/tasks.json`

# WORKFLOW: IOCANE TASKING

**Objective:** Generate a disposable, granular `plans/tasks.json` strictly bounded by the current meso-state handoff.

## 1. STATE INITIALIZATION

Before proceeding to Step 2, you must output the following metadata to confirm your micro-queue boundaries:

- **Meso-State Goal:** [The Session Goal from the handoff bundle]
- **Allowed Context:** [List only the files from the Preload Targets]
- **Validation Strategy:** [e.g., Autonomous pytest/mypy via io-loop]

---

## 2. PROCEDURE

### Step A: [HARD GATE] SCOPE INGESTION

* **Action:** Read `plans/execution-handoff-bundle.md`.
- **Constraint:** You are strictly blinded to the macro `PLAN.md` and `project-spec.md`.
- **Rule:** Any task generated outside the `Allowed Scope` is a critical failure.

### Step B: GENERATE TASKS

* **Action:** Overwrite `plans/tasks.json` using the template.
- **Logic:** Map the goal into the 4-step TDD cycle: `setup`, `test`, `implement`, `refactor`.
- **Task Decomposition Rules:**
    1. **Atomic Granularity:** Break implementation into the smallest executable steps.
    2. **Context Locking:** The `context_files` array for EVERY task must be a strict subset of the `Preload Targets`.
    3. **Autonomous Tooling:** Ensure tasks rely on `uv run pytest` or `uv run mypy`.

### Step C: [HARD GATE] COMPLIANCE CHECK

* **Action:** Verify `plans/tasks.json` against **ALL** `[HARD]` rules in `.agent/rules/planning.md`.
- **Check:** Are tasks atomic? Is context locked? Is there an integration task if the critical path is modified?
- **[HARD] Rejection Gate:** If ANY task has an empty `context_files` array, REJECT the output and add files before proceeding.

---

## 3. [HARD] OUTPUT & STOP-GATE

* Output: "TASKS READY. Run `/io-loop` to execute."
* **[HARD] Tasking Stop-Gate:** You MUST STOP after writing `plans/tasks.json`. You are FORBIDDEN from writing implementation code (`.py` files). Explicit handoff to `/io-loop` is required.

---
description: Execute tasks autonomously using strict Red-Green-Refactor TDD and stateless logging.
---

> **[CRITICAL] CONTEXT LOADING**
> **LOAD ONLY:**
> 1. `plans/tasks.json`
> 2. The specific files listed in the current task's `context_files` list.
> 3. `.agent/scripts/log_progress.sh` (For execution)

# WORKFLOW: THE IOCANE LOOP

**Objective:** Execute the current task queue autonomously using the Red-Green-Refactor cycle, halting only for human intervention on cascading failures or architectural drift.

## 1. STATE INITIALIZATION
Before beginning Step 2, you must output the following state metadata to confirm your boundaries:
- **Active Task ID:** [e.g., CP_1.1]
- **Target File:** [The primary .py or .pyi file you are modifying]
- **Allowed Context:** [List the files from the `context_files` array for this task]

*Rule: If the files you need are not in your `context_files`, you are FORBIDDEN from reading them. You must stop and request a tasking update.*
*Rule: If files were modified by external tools (formatters, linters) between sessions, re-read them before editing. Never trust cached line numbers.*

---

## 2. PROCEDURE

### Step A: READ & LOCK
* Read `plans/tasks.json` to find the first task marked `"status": "pending"`.
* **Output:** "Executing Task: [ID] [Description]"

### Step B: AUTONOMOUS EXECUTION (State Machine)

* **IF (Type == setup):**
    * **Goal:** Create skeleton files, interfaces, or configurations.
    * **Action:** Generate the required files. Ensure they reside strictly within the `src/` boundary to pass future compliance checks.
    * **Gate:** Run `uv run mypy` on the modified files. If clean, proceed to Step C.

* **IF (Type == test):**
    * **Goal:** Write a failing test for the current capability.
    * **Action:** Generate or modify the test file.
    * **Gate:** Run `uv run pytest <test_file>`. It MUST FAIL (Red state). If it passes immediately, your test is invalid; rewrite it. Once it fails correctly, proceed to Step C.

* **IF (Type == implement):**
    * **Goal:** Write the minimum code required to pass the test.
    * **Action:** Modify the target implementation file.
    * **Gate:** Run `uv run pytest <test_file>`. If it fails, attempt up to 3 autonomous remediations. If it passes (Green state), run `uv run mypy <implementation_file>`. If both pass, proceed to Step C.

* **IF (Type == refactor):**
    * **Goal:** Clean up the implementation, ensuring SOLID principles and dependency injection compliance.
    * **Action:** If modifying a core (non-entrypoint) component, execute `uv run python .agent/scripts/check_di_compliance.py`.
    * **Gate:** Fix any linter, typing, or DI compliance errors. Once clean (Exit Code 0), proceed to Step C.

* **IF (Type == verify):**
    * **Goal:** Run a command and confirm expected output (e.g., E2E test, build script).
    * **Action:** Execute the specified command.
    * **Gate:** If successful, proceed to Step C. If it fails, attempt up to 3 remediations before escalating.

### Step C: STATE MANAGEMENT (Stateless Logging)
* **Action (JSON):** Update `plans/tasks.json` to mark the current task's status as `"complete"`.
* **Action (Bash):** Execute the logging script: `./.agent/scripts/log_progress.sh "<TASK_ID>" "COMPLETE" "<Notes>"`
* **Constraint:** Do not read or load `plans/progress.md` into your context window.

---

## 3. DRIFT & DEBT ESCALATION
If you utilize the `# noqa: DI` escape hatch, `check_di_compliance.py` will instantly fail the verify gate with Exit Code 1 unless an active ticket already exists in `PLAN.md`. Because your current state is blinded to `PLAN.md`, you **MUST HALT execution immediately**. 

Do not attempt autonomous remediation for an untracked `# noqa: DI` failure. Output a high-visibility warning:

**Output:** "CRITICAL DEBT DETECTED: [Explanation of the drift/debt]. Execution halted. You must manually add this to the Remediation Backlog in `plans/PLAN.md` with a `[REFACTOR]` or `[CLEANUP]` tag before I can proceed."

## 4. RECURSION
Automatically loop back to Step 1 and execute the next pending task.
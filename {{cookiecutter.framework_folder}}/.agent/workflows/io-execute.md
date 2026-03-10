---
description: Minimal sub-agent execution context. Receives one checkpoint task file and executes Red-Green-Refactor. Tier 3 — no plan mode, no cross-checkpoint awareness.
---

> **[NO PLAN MODE]**
> This workflow executes autonomously. No proposals. No human interaction.
> Escalate only on hard failure conditions defined below.

> **[CRITICAL] CONTEXT LOADING**
> Load ONLY the task file you were given.
> You have no access to plan.md, roadmap.md, project-spec.md, or other task files.
> Read the task file first. It contains everything you need.

# WORKFLOW: IO-EXECUTE

**Objective:** Execute one checkpoint's task file exactly as specified. Implement via Red-Green-Refactor against the provided Protocol contract. Write a status file on completion. Terminate.

**Invocation context:**
This workflow runs inside a git worktree (`$REPO_ROOT/.worktrees/[CP-ID]`) on branch `iocane/[CP-ID]`. The repository is a full checkout. You are isolated from all other concurrent sub-agents.

---

## 1. STATE INITIALIZATION

Before proceeding:

1. Run `uv run python .agent/scripts/generate_walkthrough_context.py` and parse the JSON output. This gives you the Protocol definitions, src structure, and layer map without reading any source files. Use it to orient yourself — do not load additional files beyond what your task file lists.

2. Output:

- **Checkpoint ID:** [CP-ID from task file]
- **Target files:** [write_targets listed in task file]
- **Protocol contract:** [interfaces/*.pyi file named in task file]
- **Gate command:** [exact gate command from task file]

---

## 2. PROCEDURE

### Step A: READ CONTRACT

- **Action:** Read the Protocol file listed under `## Contract` in your task file.
- **Goal:** Understand every method signature you are required to implement.
- **Rule:** You implement exactly what the Protocol defines. No additional public methods. No deviation from signatures.

---

### Step B: RED — WRITE FAILING TEST

- **Action:** Write the test file at the path listed in `## Write Targets`.
- **Rules:**
  - Test must import and instantiate the implementation class
  - Test must call at least one method defined in the Protocol
  - Test must assert a specific, meaningful outcome — not just "does not raise"
  - Test must FAIL before implementation exists
- **Gate:** Run `pytest [test_file_path]`
  - If test PASSES immediately → test is invalid. Rewrite it.
  - If test FAILS with `ImportError` or `ModuleNotFoundError` → create empty skeleton implementation file first, then re-run. This is acceptable.
  - If test FAILS with assertion error or `NotImplementedError` → correct RED state. Proceed.

---

### Step C: GREEN — WRITE MINIMUM IMPLEMENTATION

- **Action:** Write the implementation file at the path listed in `## Write Targets`.
- **Rules:**
  - Implement only what is needed to pass the test
  - Follow the Protocol signature exactly — method names, parameter types, return types
  - Use dependency injection: all collaborators received via `__init__`, never instantiated internally
  - No global state, no module-level side effects
  - `from __future__ import annotations` at top of every module
  - Protocol imports inside `if TYPE_CHECKING:` only
- **Gate:** Run `pytest [test_file_path]`
  - Must PASS. If fail: attempt remediation up to 3 times. If still failing after 3 attempts → escalate (see Section 3).

---

### Step D: GATE — RUN CHECKPOINT GATE COMMAND

- **Action:** Run the exact gate command from `## Gate command` in the task file.
- **This is the checkpoint's acceptance test.**
- Must PASS before proceeding to refactor.
- If fail after 3 attempts → escalate (see Section 3).

---

### Step E: CONNECTIVITY TESTS

- **Action:** If `## Connectivity Tests to Keep Green` lists any gate commands in the task file, run each one.
- **Rule:** If any previously passing connectivity test goes red, this is an escalation trigger. Do not attempt autonomous remediation. Escalate immediately (see Section 3).

---

### Step F: REFACTOR — DI AND COMPLIANCE

- **Action:** Run the following checks in order:

```bash
uv run python .agent/scripts/check_di_compliance.py
uv run mypy src/[implementation_path]
uv run ruff check --fix src/[implementation_path]
uv run lint-imports
```

- **Rules for each:**
  - `check_di_compliance.py`: Must exit 0. If a `# noqa: DI` suppression is required for a legitimate reason, this is an escalation trigger — do not add it silently. Escalate (see Section 3).
  - `mypy`: Must exit 0. Fix all type errors before proceeding.
  - `ruff`: Apply fixes. Must exit 0 after fixes.
  - `lint-imports`: Must exit 0. If a layer violation is detected, this is an escalation trigger. Escalate (see Section 3).

- **After all checks pass:** Re-run gate command to confirm refactoring did not break GREEN state.

---

### Step G: WRITE STATUS AND TERMINATE

**On success:**

```bash
echo "PASS" > ../../plans/tasks/[CP-ID].status
```

Output: "CP-[ID] COMPLETE. Gate passing. Status: PASS."

Terminate.

---

## 3. ESCALATION PROTOCOL

Escalation triggers — do NOT attempt autonomous remediation for these:

| Trigger | Action |
|---------|--------|
| Gate still failing after 3 attempts | Write FAIL status, terminate |
| Connectivity test goes red | Write FAIL status, terminate |
| `# noqa: DI` required but no backlog entry | Write FAIL status, terminate |
| Layer violation detected by `lint-imports` | Write FAIL status, terminate |
| Missing dependency (package not installed) | Write FAIL status, terminate |

**On any escalation trigger:**

```bash
echo "FAIL: [one line describing exact trigger and what failed]" > ../../plans/tasks/[CP-ID].status
```

Output: "CP-[ID] FAILED. Reason: [trigger]. Status written. Terminating."

Terminate.

The `PostToolUse` hook will detect the non-zero exit or FAIL status and append to `.iocane/escalation.log`. The orchestrator will surface this to the human at next session start.

---

## 4. CONSTRAINTS

- Read ONLY the files listed in your task file's `## Context Files` section plus the Protocol
- Write ONLY to files listed in `## Write Targets`
- No internet access, no package installation, no git operations (worktree is already set up)
- No awareness of other checkpoints, other task files, or the broader plan
- No `print()` statements in implementation — use `logging` or `structlog`
- No hardcoded secrets, API keys, or tokens
- No backslashes in file paths
- Forward slashes only, even on Windows
- Do not modify the Protocol `.pyi` file under any circumstances
- If the task file is malformed or missing required sections, write FAIL and terminate immediately

---
name: io-execute
description: Minimal sub-agent execution context. Receives one checkpoint task file and executes Red-Green-Refactor. Tier 3 — no plan mode, no cross-checkpoint awareness.
---

> **[NO PLAN MODE]**
> This workflow executes autonomously. No proposals. No human interaction.
> Escalate only on hard failure conditions defined below.

> **[CRITICAL] CONTEXT LOADING**
> Load ONLY the task file you were given.
> You have no access to plan.yaml, roadmap.md, project-spec.md, or other task files.
> Read the task file first. It contains everything you need.
>
> Implement via Red-Green-Refactor exactly as specified below.
> Context hygiene: Do not read files outside `context_files`. Speculative reads
> waste tokens against your fixed turn limit and risk acting on stale state.
> TDD: No implementation without a test. Untested code is invisible to the gate
> command -- a FAIL wastes the entire session. YAGNI -- no "just in case" helpers.
> Test structure: Tests mirror src/ directory structure under tests/. Shared
> fixtures go in tests/conftest.py (root) or tests/[subdir]/conftest.py (scoped).
> One test file per module, one test class per Protocol.

# WORKFLOW: IO-EXECUTE

**Objective:** Execute one checkpoint's task file exactly as specified. Implement via Red-Green-Refactor against the provided Protocol contract. Write a status file on completion. Terminate.

**Invocation context:**
This workflow runs inside a git worktree (`$REPO_ROOT/.worktrees/[CP-ID]`) on branch `iocane/[CP-ID]`. The repository is a full checkout. You are isolated from all other concurrent sub-agents.

---

## 1. STATE INITIALIZATION

Before proceeding:

1. Read your task file completely (YAML format). It contains the checkpoint ID, write targets, contract path, and gate command as structured fields. Do not load additional files beyond what the task file's `context_files` list specifies.

2. Check the `step_progress` field. Any step with `done: true` is already complete — skip it and resume from the first step with `done: false`. If all steps have `done: false`, start at Step B.

3. Output:

- **Checkpoint ID:** [CP-ID from task file]
- **Target files:** [write_targets listed in task file]
- **Protocol contract:** [interfaces/*.pyi file named in task file]
- **Gate command:** [exact gate command from task file]
- **Resuming from:** [first unchecked step, or B if none checked]

---

## 2. PROCEDURE

### Step A: READ CONTRACT

- **Action:** Read the Protocol file listed in the `contract` field of your task file.
- **Goal:** Understand every method signature you are required to implement.
- **Rule:** You implement exactly what the Protocol defines. No additional public methods. No deviation from signatures.

---

### Step B: RED — WRITE FAILING TEST

- **Action:** Read the test-writer skill at `.claude/skills/test-writer/SKILL.md`.
  Follow its triage gate against the Protocol contract from Step A:
  - Protocol methods with named states and transitions → Track A (read `references/track-a-fsm.md`)
  - Stateless contracts (input/output, validation, transformation) → Track B (read `references/track-b-contract.md`)
  - Mixed Protocol → separate test classes per track

  Execute Phases 1-3 from the routed track. Phase 1 extracts the model from the
  Protocol contract. Phase 2 designs the TC table. Phase 3 generates the test file
  at the path listed in `## Write Targets`.

- **Rules:**
  - Test must import and instantiate the implementation class
  - Test must call at least one method defined in the Protocol
  - Test must assert a specific, meaningful outcome — not just "does not raise"
  - Test must FAIL before implementation exists
- **Gate:** Run `pytest [test_file_path]`
  - If test PASSES immediately → test is invalid. Rewrite it.
  - If test FAILS with `ImportError` or `ModuleNotFoundError` → create empty skeleton implementation file first, then re-run. This is acceptable.
  - If test FAILS with assertion error or `NotImplementedError` → correct RED state. Proceed.
- **On completion:** Mark step B done via Bash tool:
  ```bash
  uv run python -c "
  import sys; sys.path.insert(0, '.claude/scripts')
  from task_parser import load_task, mark_step_done, save_task
  t = mark_step_done(load_task(sys.argv[1]), 'B')
  save_task(sys.argv[1], t)
  " plans/tasks/CP-XX.yaml
  ```

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
- **Gate:** Run `uv run rtk pytest [test_file_path]`
  - Must PASS. If fail: attempt remediation up to 3 times. If still failing after 3 attempts → escalate (see Section 3).
- **On completion:** Mark step C done via the same `mark_step_done` pattern as Step B (substitute `'C'` for the step prefix).

---

### Step D: GATE — RUN CHECKPOINT GATE COMMAND

- **Action:** Run the exact gate command from the `gate_command` field in the task file.
- **This is the checkpoint's acceptance test.**
- Must PASS before proceeding to refactor.
- If fail after 3 attempts → escalate (see Section 3).
- **On completion:** Mark step D done via the same `mark_step_done` pattern (substitute `'D'`).

---

### Step E: CONNECTIVITY TESTS

- **Action:** For each CT entry in the `connectivity_tests` list in the task file:
  1. Check whether the CT test file exists at the `file` path specified in the CT spec.
  2. If it does **not** exist, create it: write the test at that path using the `function`, `fixture_deps`, `contract_under_test`, and `assertion` fields from the CT spec. Both sides of the seam must use real implementations — no mocking either side. Create the `tests/connectivity/` directory if it does not exist.
  3. Run the gate command from the `gate` field.
- **Rule:** All CT gates must pass. Any failure is an escalation trigger. Do not attempt autonomous remediation. Escalate immediately (see Section 3).
- **If `connectivity_tests` is empty:** skip this step entirely.
- **On completion:** Mark step E done via the same `mark_step_done` pattern (substitute `'E'`).

---

### Step F: REFACTOR — DI AND COMPLIANCE

- **Action:** Run the following checks in order:

```bash
uv run python .claude/scripts/check_di_compliance.py --diff-only
uv run mypy src/[implementation_path]
uv run rtk ruff check --fix src/[implementation_path]
uv run rtk lint-imports
```

- **Rules for each:**
  - `check_di_compliance.py`: Must exit 0. If a `# noqa: DI` suppression is required for a legitimate reason, this is an escalation trigger — do not add it silently. Escalate (see Section 3).
  - `mypy`: Must exit 0. Fix all type errors before proceeding.
  - `ruff`: Apply fixes. Must exit 0 after fixes.
  - `lint-imports`: Must exit 0. If a layer violation is detected, this is an escalation trigger. Escalate (see Section 3).

- **After all checks pass:** Re-run gate command to confirm refactoring did not break GREEN state.
- **On completion:** Mark step F done via the same `mark_step_done` pattern (substitute `'F'`).

---

### Step F2: EXECUTION FINDINGS (optional)

- **Action:** If during Steps B-F you observed any of the following in adjacent code
  (code you READ but did not WRITE):
  - Bugs in dependency modules your implementation calls
  - Deprecation warnings from imported APIs
  - Missing default values or incomplete error handling in collaborators
  - Type annotation inaccuracies in Protocol files you consumed
  - Hardcoded values that should be configurable

  Write all findings at once via Bash tool calling `task_parser.set_execution_findings`:
  ```bash
  uv run python -c "
  import sys, json; sys.path.insert(0, '.claude/scripts')
  from task_parser import load_task, set_execution_findings, save_task
  from schemas import ExecutionFinding
  findings = [
      ExecutionFinding(adjacent_file='src/path/file.py', observation='[description]', severity='MEDIUM'),
  ]
  t = set_execution_findings(load_task(sys.argv[1]), findings)
  save_task(sys.argv[1], t)
  " plans/tasks/CP-XX.yaml
  ```

- **Rule:** Only report observations about code OUTSIDE your write targets.
- **Rule:** If you have no observations, skip this step entirely.
- **Rule:** Do not attempt to fix adjacent code. Record only.

---

### Step G: COMMIT, WRITE STATUS, AND TERMINATE

**On success:**

```bash
# Remove any plans/tasks/ output artifacts from other checkpoints before staging.
# These can appear via race conditions in parallel dispatch and must not be committed.
find plans/tasks/ -maxdepth 1 -name "CP-*.log" -o -name "CP-*.result.json" -o -name "CP-*.exit" -o -name "CP-*.status" 2>/dev/null | grep -v "plans/tasks/[CP-ID]\." | xargs rm -f 2>/dev/null || true
git add -A
git commit -m "CP-[CP-ID]: [one-line summary of what was implemented]"
bash "$IOCANE_REPO_ROOT/.claude/scripts/write-status.sh" [CP-ID] PASS
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
bash "$IOCANE_REPO_ROOT/.claude/scripts/write-status.sh" [CP-ID] "FAIL: [one line describing exact trigger and what failed]"
```

Output: "CP-[ID] FAILED. Reason: [trigger]. Status written. Terminating."

Terminate.

The `PostToolUse` hook will detect the non-zero exit or FAIL status and append to `.iocane/escalation.log`. The orchestrator will surface this to the human at next session start.

---

## 4. CONSTRAINTS

- Read ONLY the files listed in your task file's `context_files` field plus the Protocol
- Write ONLY to files listed in `write_targets`, plus the task file itself (for `step_progress` and `execution_findings` updates via `task_parser`)
- No internet access, no package installation, no git operations (worktree is already set up)
- No awareness of other checkpoints, other task files, or the broader plan
- No `print()` statements in implementation — use `logging` or `structlog`
- No hardcoded secrets, API keys, or tokens
- No backslashes in file paths
- Forward slashes only, even on Windows
- Do not modify the Protocol `.pyi` file under any circumstances
- If the task file is malformed YAML or missing required fields, write FAIL and terminate immediately

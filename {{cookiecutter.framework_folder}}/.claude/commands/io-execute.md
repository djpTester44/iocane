---
name: io-execute
description: Tier 3 generator. Receives one checkpoint task file with contract tests + connectivity tests pre-written. Writes impl + emergent impl tests. No plan mode, no cross-checkpoint awareness.
---

> **[NO PLAN MODE]**
> This workflow executes autonomously. No proposals. No human interaction.
> Escalate only on hard failure conditions defined below.

> **[CRITICAL] CONTEXT LOADING**
> Load your task file, plus the per-kind impl-test reference:
> 1. `plans/tasks/${CP_ID}.yaml` -- your task file (authoritative scope)
> 2. `.claude/skills/test-writer/references/impl-rules.md` -- emergent
>    impl-test conventions (TDD inside the implementation, under the contract)
>
> Contract tests under `tests/contracts/` and connectivity tests under
> `tests/connectivity/` were written upstream by Tier-1 Test Author and
> Tier-3a CT Author, respectively. They are **read-only** for you. Do
> NOT edit them. Do NOT author additional files in those directories.
>
> Context hygiene: Do not read files outside `context_files`. Speculative
> reads waste tokens against your fixed turn limit and risk acting on
> stale state. YAGNI -- no "just in case" helpers.
>
> Impl tests (separate from contract/connectivity tests) live under
> `tests/**` but NOT in `tests/contracts/` or `tests/connectivity/`.
> Suggested convention: `tests/test_<module>_impl.py`. These are
> emergent during implementation per CDD; load
> `.claude/skills/test-writer/references/impl-rules.md` before
> authoring any impl test.

# WORKFLOW: IO-EXECUTE

**Objective:** Execute one checkpoint's task file exactly as specified. Implement the Protocol against pre-existing contract + connectivity tests, authoring emergent impl tests as internal logic develops. Write a status file on completion. Terminate.

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

### Step B: RED -- EMERGENT IMPL TESTS (optional)

Contract tests at `tests/contracts/` and connectivity tests at
`tests/connectivity/` are **pre-existing and read-only**. Do NOT
re-author or modify them. The RED surface you may author here is
*impl tests* -- emergent tests for internal machinery underneath the
Protocol, per CDD (`.claude/references/cdd/cdt-vs-impl-testing.md`).

- **When:** if implementing the contract surfaces internal logic
  complex enough to warrant isolated verification (parsing helpers,
  caching with eviction, retry backoff, data transformations). If
  the impl is direct and the contract test already exercises the
  behavior observably, skip this step.

- **Action:** Read the test-writer skill at
  `.claude/skills/test-writer/SKILL.md` and the per-kind reference
  at `.claude/skills/test-writer/references/impl-rules.md`. Author
  impl tests under `tests/**` **except** `tests/contracts/` and
  `tests/connectivity/`. Suggested path:
  `tests/test_<module>_impl.py`.

- **Rules:**
  - Impl tests cite design intent (why this internal behavior is
    worth verifying), not contract clauses (INV-NNN). Clauses are
    the contract test's job.
  - Impl tests are allowed to break on refactor; contract tests are
    not. Keep the asymmetry.
  - Never replace a contract test or connectivity test with an impl
    test, even if they happen to exercise the same observable.
  - If a TDD cycle reveals the Protocol interface should differ,
    enter the AMEND-on-impl-gap path in Section 3 -- do NOT silently
    reshape the contract.

- **Gate:** Run the impl test(s) you authored and any relevant
  pre-existing contract + connectivity tests:
  ```bash
  uv run rtk pytest [impl_test_path] [tests/contracts/test_X.py] [tests/connectivity/test_Y.py]
  ```
  - Impl tests should FAIL before impl exists (skeleton-import is
    acceptable; see Step C).
  - Contract tests and connectivity tests will continue to fail
    until Step C -- that is expected.

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

### Step E: CONNECTIVITY TESTS -- RUN ONLY

Connectivity test files under `tests/connectivity/` were written by
the Tier-3a CT Author before this stage (per Phase 4). They are
**pre-existing and read-only** -- do NOT edit, do NOT create, and
do NOT duplicate their contents anywhere else.

- **Action:** For each CT entry in the `connectivity_tests` list in
  the task file, run the `gate` field exactly as written.
- **Rule:** All CT gates must pass. Any failure is an escalation
  trigger. Do not attempt autonomous remediation (re-authoring the
  CT body is forbidden -- it is owned by ct_author). Escalate
  immediately (see Section 3).
- **If `connectivity_tests` is empty:** skip this step entirely.
- **Note:** Only the `target_cp` receives CT entries in its task
  file. If this checkpoint appears only as a source in a CT, its
  task file will have `connectivity_tests: []`.
- **If a CT file is missing:** treat as PREFLIGHT_FAIL-family -- the
  dispatcher's preflight should have surfaced this before your
  session started. Do NOT create the file. Escalate via
  Section 3.
- **On completion:** Mark step E done via the same `mark_step_done`
  pattern (substitute `'E'`).

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
| CT file missing under `tests/connectivity/` | Write FAIL status, terminate (CT author stage misfired upstream) |
| `# noqa: DI` required but no backlog entry | Write FAIL status, terminate |
| Layer violation detected by `lint-imports` | Write FAIL status, terminate |
| Missing dependency (package not installed) | Write FAIL status, terminate |
| Protocol silent on a necessary precondition, return semantic, or collaborator | Emit AMEND signal, HALT (see AMEND path below) |

**On any FAIL-status escalation trigger:**

```bash
bash "$IOCANE_REPO_ROOT/.claude/scripts/write-status.sh" [CP-ID] "FAIL: [one line describing exact trigger and what failed]"
```

Output: "CP-[ID] FAILED. Reason: [trigger]. Status written. Terminating."

Terminate.

The `PostToolUse` hook will detect the non-zero exit or FAIL status and append to `.iocane/escalation.log`. The orchestrator will surface this to the human at next session start.

---

### AMEND-on-impl-gap path

Fires only when the Protocol contract is genuinely insufficient to
implement a behavior required by its declared invariants or tests --
not when the impl is difficult, only when the contract is silent on
something the impl MUST know:

- **Kinds** (use enum values from `AmendSignalKind` in
  `.claude/scripts/schemas.py`):
  - `missing_raises` -- a test or invariant names an exception not
    listed in the Protocol's `Raises:` clause.
  - `silent_return_semantics` -- the Protocol's return annotation is
    `None`/`Any` or its docstring says nothing about the shape the
    impl must produce.
  - `missing_precondition` -- a required precondition (non-empty
    input, caller-held lock, etc.) is not declared.
  - `undeclared_collaborator` -- the impl needs a collaborator not
    listed in the Protocol's `__init__` signature.
  - `symbol_gap` -- a type, exception, or fixture referenced by the
    invariant does not appear in `plans/symbols.yaml`.

**Action:**

1. Construct an `AmendSignalFile`
   (`.claude/scripts/schemas.py:723-771`):
   - `protocol:` -- full path to the Protocol that needs amendment
     (e.g., `interfaces/<stem>.pyi`).
   - `signals:` -- list of `AmendSignal` entries, one per gap, with
     `method`, `invariant_id` (may be empty string if the gap is
     impl-level rather than test-plan-level), `kind`, `description`,
     `suggested_amendment`.
   - `attempt:` -- leave at schema default (`1`);
     `handle_amend_signal.py` populates the final value on consume.

2. Write `.iocane/amend-signals/${CP_ID}.yaml`. Validate via:
   ```bash
   uv run python -c "
   import sys, yaml
   sys.path.insert(0, '.claude/scripts')
   from schemas import AmendSignalFile
   data = yaml.safe_load(open('.iocane/amend-signals/${CP_ID}.yaml'))
   AmendSignalFile.model_validate(data)
   "
   ```
   If validation fails, the signal cannot be emitted -- fall back
   to the FAIL-status escalation path above.

3. Write a `.status` file naming the HALT:
   ```bash
   bash "$IOCANE_REPO_ROOT/.claude/scripts/write-status.sh" [CP-ID] \
     "FAIL: impl-Protocol gap; AMEND signal emitted at .iocane/amend-signals/[CP-ID].yaml"
   ```

4. Terminate. Do NOT attempt impl. The architect consumes the signal
   via `handle_amend_signal.py --consume <CP-ID>` at the next
   `/io-architect` Section 4 AMEND MODE pass. The retry budget is
   bounded by `architect.amend_retries` (default 2); when exceeded,
   `--consume` exits 2 and appends a DESIGN backlog entry.

**Stem convention:** generator AMEND signals use `${CP_ID}.yaml`
(e.g., `CP-02.yaml`) to distinguish them from tester signals that
use `<protocol-stem>.yaml`. `handle_amend_signal.py` derives the
sidecar counter filename from the signal stem; the two namespaces
are disjoint by shape (`CP-\d+` vs identifier-like Protocol stems).

---

## 4. CONSTRAINTS

**Read scope:**

- Files listed in your task file's `context_files` field
- The Protocol `.pyi` named in your task file's `contract` field
- `tests/contracts/*.py` and `tests/connectivity/*.py` (pre-existing; read-only context for your impl)
- `plans/test-plan.yaml` (invariants that constrain impl beyond the Protocol signature)
- `plans/symbols.yaml` (exception classes, settings fields, fixture names your impl must use)

**Write scope:**

- Files listed in `write_targets` (typically `src/**/*.py` and impl-test paths)
- `tests/**/*.py` EXCEPT `tests/contracts/` and `tests/connectivity/` -- impl tests go under other directories (e.g., `tests/test_<module>_impl.py`)
- The task file itself (for `step_progress` and `execution_findings` updates via `task_parser`)
- `.iocane/amend-signals/${CP_ID}.yaml` on impl-Protocol-gap (see Section 3 AMEND path)

**Never-edit** (per Phase 4 D15 -- any write here triggers reset hooks and invalidates architect validation stamps during parallel dispatch):

- `interfaces/*.pyi` (architect-owned)
- `plans/*.yaml` (architect- or validation-owned)
- `tests/contracts/*` (Tier-1 Test Author-owned)
- `tests/connectivity/*` (Tier-3a CT Author-owned)

**Other constraints:**

- No internet access, no package installation, no git operations (worktree is already set up)
- No awareness of other checkpoints, other task files, or the broader plan
- No `print()` statements in implementation -- use `logging` or `structlog`
- No hardcoded secrets, API keys, or tokens
- No backslashes in file paths -- forward slashes only, even on Windows
- If the task file is malformed YAML or missing required fields, write FAIL and terminate immediately

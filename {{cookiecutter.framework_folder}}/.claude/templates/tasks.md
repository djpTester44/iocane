# Task: CP-[NN] — [Checkpoint Name]

**Checkpoint ID:** CP-[NN]
**Feature:** F-[NN] — [Feature name from roadmap.md]
**Workflow:** io-execute

> You are a sub-agent executing a single checkpoint in an isolated git worktree.
> You have no access to plan.md, roadmap.md, project-spec.md, or other task files.
> Read this file completely before taking any action.
> Implement via Red-Green-Refactor exactly as specified below.
>
> Context hygiene: Do not read files outside Context Files. Speculative reads
> waste tokens against your fixed turn limit and risk acting on stale state.
>
> TDD: No implementation without a test. Untested code is invisible to the gate
> command -- a FAIL wastes the entire session. YAGNI -- no "just in case" helpers.
>
> Test structure: Tests mirror src/ directory structure under tests/. Shared
> fixtures go in tests/conftest.py (root) or tests/[subdir]/conftest.py (scoped).
> One test file per module, one test class per Protocol.

---

## Objective

[One sentence — what is built and verifiably complete when this checkpoint passes its gate command.]

## Acceptance Criteria

- [Criterion 1 — observable, testable. e.g., `[ProtocolName].method_name` returns a `[ReturnType]` satisfying `[invariant]`.]
- [Criterion 2]
- [Criterion 3]

---

## Contract

Protocol file you are implementing against:

```
interfaces/[protocol].pyi
```

Implement every method defined in this Protocol. No additional public methods. No deviation from signatures.

---

## Write Targets

You may ONLY write to these files:

- `src/[path]/[module].py` — implementation
- `tests/[path]/test_[module].py` — unit tests

Do not write to any other file.

---

## Context Files (read-only)

Load these before writing anything:

- `interfaces/[protocol].pyi` — binding contract
- `plans/project-spec.md` — CRC card for [ComponentName] only (lines [N]–[N])

Do not load any other file from the repository.

---

## Gate Command

```
uv run rtk pytest tests/[path]/test_[module].py
```

This must pass before you write the status file. If it does not pass after 3 remediation attempts, write FAIL and terminate.

---

## Connectivity Tests to Keep Green

Run each of these after your gate passes. If any go red, write FAIL and terminate immediately — do not attempt remediation.

```
uv run rtk pytest tests/connectivity/test_[cp_a]_[cp_nn].py::[function_name]
```

---

## Refactor Commands

After the gate passes, run these — scoped to your write targets only:

```bash
uv run ruff check src/[path]/
uv run mypy src/[path]/
```

Do NOT run linters against `.` (the whole repo) or against any path outside your write targets.

---

## Source (remediation checkpoints only)

For remediation checkpoints, the source backlog item is referenced by its BL-ID:

```
Source: plans/backlog.md BL-NNN
```

To read the source item context: `grep 'BL-NNN' plans/backlog.md` — read downward from the ID line.

---

## Execution Notes

[Any checkpoint-specific guidance the sub-agent needs that is not captured in the contract or acceptance criteria. e.g., "The collaborator is injected via __init__ as `store: StateStoreProtocol`. Do not instantiate it internally." Leave blank if none.]

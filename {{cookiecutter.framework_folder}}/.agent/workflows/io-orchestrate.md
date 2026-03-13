---
description: Dispatch sub-agents for the current batch. Thin alias for dispatch-agents.sh. Tier 2 — no plan mode.
---

> **[NO PLAN MODE]**
> This workflow is fully autonomous. No proposals, no human approval steps.
> Task files must already exist in `plans/tasks/` (written by `/io-plan-batch`) before this workflow runs.

# WORKFLOW: IO-ORCHESTRATE

**Objective:** Dispatch sub-agents for all pending checkpoints in `plans/tasks/` via isolated git worktrees. This workflow is a thin alias for `uv run rtk bash .claude/scripts/dispatch-agents.sh`.

**Position in chain:**

```
/io-plan-batch -> [/io-orchestrate] -> (sub-agents run) -> /io-review
```

---

## 1. PROCEDURE

### Step A: ESCALATION GATE

Check whether `.iocane/escalation.flag` exists.

If it exists:

```
ESCALATION FLAG DETECTED.

A previous sub-agent run triggered an escalation.
Review .iocane/escalation.log before dispatching a new batch.
Clear the flag file after review: rm .iocane/escalation.flag

Dispatch is blocked until the flag is cleared.
```

HALT.

If no flag: proceed to Step B.

---

### Step B: TASK FILES PRESENT

Check that at least one `plans/tasks/CP-XX.md` file exists with no matching `CP-XX.status` file.

If no pending task files exist:

```
No pending task files found in plans/tasks/.
Run /io-plan-batch to compose and write a batch before dispatching.
```

HALT.

---

### Step C: DISPATCH

Run:

```bash
uv run rtk bash .claude/scripts/dispatch-agents.sh
```

This script owns the full dispatch lifecycle: parallel limit enforcement, worktree setup, headless `claude -p` invocation, result collection, and worktree cleanup. Do not re-implement any of that logic here.

---

### Step D: REPORT

After the script exits, report the outcome:

- If exit 0: all checkpoints passed. Prompt the user to run `/io-review`.
- If exit non-zero: one or more checkpoints failed. Direct the user to `plans/tasks/*.log` and `.iocane/escalation.log` for details.

---

## 2. CONSTRAINTS

- Does not generate task files — that is `/io-plan-batch`'s responsibility.
- Does not modify `plan.md`, `roadmap.md`, `project-spec.md`, or any `.pyi` file.
- Does not re-implement dispatch logic — delegates entirely to `dispatch-agents.sh`.
- Configuration (parallel limit, model) is read from `.claude/iocane.config.yaml` by `dispatch-agents.sh` — do not pass these as arguments.

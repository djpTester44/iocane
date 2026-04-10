---
name: io-plan-batch
description: Compose a dispatch batch from plans/plan.yaml. Sits between /io-checkpoint and dispatch-agents.sh in the orchestration chain.
---

# /io-plan-batch

## Purpose

Compose a dispatch batch from `plans/plan.yaml`. Sits between `/io-checkpoint` and `dispatch-agents.sh` in the orchestration chain.

```
/io-checkpoint -> /io-plan-batch -> /validate-tasks -> bash .claude/scripts/dispatch-agents.sh
```

Owns: dependency resolution, parallelization safety, task file generation, confidence scoring, and human approval gate.

Does **not** own: agent dispatch (that is `dispatch-agents.sh`).

---

## Steps

### Step 0 — [HARD GATE] PLAN VALIDATION

Run `bash .claude/scripts/pre-invoke-io-plan-batch.sh`.

If it exits non-zero, HALT immediately with the error message returned by the script. Do not proceed to Step A or any subsequent step.

---

### Step A — Read Configuration

Read `.claude/iocane.config.yaml` and extract `parallel.limit`. This is the maximum number of checkpoints that may be included in a single batch. If the file is missing, default `parallel.limit` to `1` and warn. Create `plans/tasks/` if it does not exist.

### Step B — Identify Unblocked Checkpoints

**B1-B3 — Load plan and resolve unblocked checkpoints:**
Use plan_parser to load the plan and query checkpoint state:

```bash
uv run python -c "
import sys, json
sys.path.insert(0, '.claude/scripts')
from plan_parser import load_plan, completed_checkpoints, unblocked_checkpoints, remediation_checkpoints, pending_checkpoints
plan = load_plan('plans/plan.yaml')
comp = [cp.id for cp in completed_checkpoints(plan)]
unblocked = unblocked_checkpoints(plan)
remed_pending = [cp for cp in remediation_checkpoints(plan) if cp.id in {u.id for u in unblocked}]
candidates = remed_pending if remed_pending else unblocked
result = {'completed': comp, 'candidates': [{'id': cp.id, 'title': cp.title, 'depends_on': cp.depends_on, 'write_targets': cp.write_targets, 'remediates': cp.remediates, 'source_bl': cp.source_bl} for cp in candidates]}
print(json.dumps(result, indent=2))
"
```

This replaces all grep/regex extraction. The `unblocked_checkpoints` function handles dependency resolution (B3).

**Remediation gate:** If any unblocked remediation CPs exist (checkpoint has `remediates` set), restrict the candidate list exclusively to those. Roadmap checkpoints are excluded from this batch. Remediation items MUST be cleared before the plan advances to roadmap checkpoints.

- If one or more remediation CPs are unblocked: restrict the candidate list exclusively
  to those unblocked remediation CPs. Roadmap checkpoints are excluded from this batch
  entirely. Remediation items MUST be cleared before the plan advances to roadmap
  checkpoints.
- If all pending remediation CPs are themselves blocked (their dependencies are not yet
  complete): fall through to roadmap candidates as normal. The remediation gate does not
  apply when no remediation CP can actually run.

Produce the candidate list ordered by checkpoint sequence within the selected pool
(remediation or roadmap).

### Step C — [HARD GATE] Parallelization Safety Check

Run `uv run python .claude/scripts/check_write_target_overlap.py CP-XX CP-YY ...` with all candidate CP-IDs. If exit code is non-zero, remove the colliding CPs (lower-priority first, by sequence number) and re-run until clean.

Beyond write-target overlap, invoke `/symbol-tracer` with `--imports-only` on the key symbols from all candidate checkpoints to detect hidden cross-references.

Apply `parallel.limit` cap: take only the first N checkpoints that pass the disjoint check, where N = `parallel.limit`.

### Step D — Generate Draft Task Files (in memory only)

Run `generate_task.py` to produce schema-valid task files deterministically from `plan.yaml` + `seams.yaml`. Do **not** write to disk at this step -- use stdout mode for review.

```bash
uv run python .claude/scripts/generate_task.py --batch CP-XX CP-YY --plan plans/plan.yaml --seams plans/seams.yaml
```

The script derives 14 of 17 TaskFile fields mechanically (id, title, feature, workflow, objective, contract, write_targets, context_files, gate_command, connectivity_tests, refactor_commands, source, seam_context, step_progress). The remaining 3 require agent review:

- `acceptance_criteria` -- passthrough from `plan.yaml`. If the script warns "acceptance_criteria empty" for a CP, synthesize 2-3 criteria from description/scope before proceeding.
- `execution_notes` -- always `None` from the script. Add checkpoint-specific guidance if needed.
- `refactor_commands` -- auto-generated as `uv run rtk ruff check --fix` + `uv run rtk mypy` per `.py` write target. Adjust if non-standard tooling is required.

If the script exits 1 for any CP, inspect the error (missing contract, unresolvable feature chain) and fix the plan before retrying.

### Step E — [HARD GATE] Score Confidence Rubric

Score the batch against the following criteria:

| Criterion | Description |
|-----------|-------------|
| Dependency correctness | For each CP in the batch: every entry in its `Depends on` list is either archived PASS (`plans/archive/CP-XX/CP-XX.status`) or is a predecessor in the current batch's execution order. No circular dependencies within the batch. No CP depends on a FAIL-archived checkpoint without a reset. |
| Parallelization safety | Run `uv run python .claude/scripts/check_write_target_overlap.py` with all batch CP-IDs. Must exit 0. If exit 1, the batch has collisions -- revise composition before proceeding. |
| Batch size sanity | Batch respects `parallel.limit` and is coherent given project state |

Produce an overall confidence score (0–100%).

Note: Task file content validation is owned by /validate-tasks, invoked after this workflow completes.

If score < 85%: revise the batch composition and re-score. Repeat up to 3 iterations total. If score does not reach 85% after 3 iterations, halt and present the failure reason to the user.

### Step F — [HUMAN GATE] Present Batch Summary for Human Approval

Present the following to the user:

```
## /io-plan-batch — Batch Summary

Confidence Score: XX%

Batch composition (N of LIMIT slots used):
- CP-XX: <title> — <brief rationale for inclusion>
- CP-YY: <title> — <brief rationale for inclusion>

Parallelization: [SAFE / SEQUENTIAL — reason]

Excluded checkpoints (and why):
- CP-ZZ: <reason — blocked dependency / write conflict / limit reached>

Task file previews available on request.

---
Accept / Modify / Reject?

- Accept: task files will be written to plans/tasks/. You are then responsible for running bash .claude/scripts/dispatch-agents.sh to dispatch agents.
- Modify: describe changes in natural language. A new /io-plan-batch run will incorporate your modifications.
- Reject: a new /io-plan-batch run will start from scratch.
```

**Do not proceed until the user responds.**

### Step G — Handle Response

**Accept:**
Write all draft task files to `plans/tasks/CP-XX.yaml` using the Write tool. The PostToolUse YAML validation hook automatically validates each file against the `TaskFile` schema on write -- no manual validation call needed. Confirm each file written. Remind the user to invoke `/validate-tasks`, then `bash .claude/scripts/dispatch-agents.sh` to dispatch agents.

**Modify:**
Acknowledge the requested modifications. Do not write any task files. Re-run from Step B incorporating the user's natural language modifications as constraints.

**Reject:**
Do not write any task files. Re-run from Step B from scratch.

---

## Output

On acceptance, for each checkpoint in the batch:

- `plans/tasks/CP-XX.yaml` written to disk

No other files are written or modified by this workflow.

---

## What This Workflow Does Not Do

- Does not dispatch agents
- Does not invoke `dispatch-agents.sh`
- Does not modify `plan.yaml`
- Does not update `.status` files

---

## Related

- `/io-checkpoint` — upstream; produces `plan.yaml`
- `/validate-plan` — must pass before this workflow runs
- `/validate-tasks` — validation gate between task file generation and dispatch
- `/task-recovery` — remediates MECHANICAL validation findings
- `bash .claude/scripts/dispatch-agents.sh` — downstream; reads `plans/tasks/` and dispatches agents
- `.claude/iocane.config.yaml` — configuration (parallel limit)

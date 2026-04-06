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
uv run rtk python -c "
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

**Context gathering:** Before constructing task files, load seams once via `seam_parser.load_seams('plans/seams.yaml')`. For each checkpoint in the batch, identify the components in its write targets and use `find_by_component()` to extract their seam entries, then project via `to_seam_entry()` (fields: `receives_di`, `key_failure_modes`, `external_terminal`). `to_seam_entry()` automatically excludes `backlog_refs` and `layer` -- backlog remediation is a separate workflow concern. Hold this data in memory for embedding below.

For each checkpoint in the confirmed batch, construct the full `CP-XX.yaml` task file content following the `TaskFile` schema defined in `.claude/scripts/schemas.py`. Do **not** write to disk at this step. Checkpoint data was already loaded via plan_parser in Step B — do not re-read `plan.yaml`.

For connectivity tests, use plan_parser to query CTs for each checkpoint:
```bash
uv run rtk python -c "
import sys, json
sys.path.insert(0, '.claude/scripts')
from plan_parser import load_plan, connectivity_tests_for_cp
plan = load_plan('plans/plan.yaml')
cts = connectivity_tests_for_cp(plan, 'CP-XX')
for ct in cts:
    print(json.dumps(ct.model_dump(mode='json', exclude_none=True), indent=2))
"
```

Each task file is a YAML document conforming to the `TaskFile` schema (`.claude/scripts/schemas.py`). Use `.claude/templates/tasks.yaml` as the structural reference. Required fields:

- `id`, `title`, `feature`, `workflow` (always "io-execute")
- `objective` and `acceptance_criteria` (from the checkpoint section read in B2)
- `contract` — the `.pyi` interface file path
- `write_targets` — including CT test file paths (see connectivity_tests below)
- `context_files` — read-only files the sub-agent needs
- `gate_command` — the pytest command to pass
- `seam_context` -- for each component in this checkpoint's write targets, embed its seam entry from `plans/seams.yaml` via `to_seam_entry()` (fields: `receives_di`, `key_failure_modes`, `external_terminal` only). Sub-agents must not read `plans/seams.yaml` directly; this field is their only seam reference. If a component has no entry in `plans/seams.yaml`, note it as `component: "[Name] -- Not yet populated"`.
- For remediation checkpoints (identified by a `remediates` field): set `source` to `"plans/backlog.yaml BL-NNN"`, where `BL-NNN` is read from the checkpoint's `source_bl` list.
- `connectivity_tests` — use `connectivity_tests_for_cp(plan, cp_id)` to find all CTs where this checkpoint appears as `target_cp` or in `source_cps`. For each matching CT, include a `TaskConnectivityTest` entry (test_id, function, file, fixture_deps, contract_under_test, assertion, gate). Omit `source_cps`/`target_cp` (those are plan-level topology fields). The CT test file path from the `file` field must also be added to `write_targets` so the sub-agent is authorized to create it. If no CTs target this checkpoint, set `connectivity_tests: []`.
- `refactor_commands` — ruff/mypy commands scoped to write targets
- `execution_notes` — any checkpoint-specific guidance (null if none)
- `execution_findings: []` — always present, initially empty
- `step_progress` — the canonical 6-step list (B through G), all `done: false`:
  ```yaml
  step_progress:
    - step: "B: Red -- write failing test"
      done: false
    - step: "C: Green -- minimum implementation"
      done: false
    - step: "D: Gate -- run checkpoint gate"
      done: false
    - step: "E: Connectivity tests"
      done: false
    - step: "F: Refactor -- DI and compliance"
      done: false
    - step: "G: Commit and write status"
      done: false
  ```

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

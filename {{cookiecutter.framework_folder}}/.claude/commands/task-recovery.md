---
name: task-recovery
description: Regenerate task files for CPs with MECHANICAL validation findings. Reads plans/validation-reports/task-validation-report.yaml, applies findings as negative constraints, and writes corrected task files after human approval.
---

# /task-recovery

## Purpose

Accepts MECHANICAL findings from `plans/validation-reports/task-validation-report.yaml`, regenerates only the affected CPs' task files with those findings injected as negative constraints, and writes the corrected files after human approval.

Does not modify `plan.yaml` or any other source-of-truth artifact. No coupling back to `/validate-tasks` — this command does not invoke it.

Chain position note: Called by `/validate-tasks` when MECHANICAL findings are present. After writing approved task files, the user re-runs `/validate-tasks`.

---

## Steps

### Step 0 — [HARD GATE]

Check that `plans/validation-reports/task-validation-report.yaml` exists AND contains at least one finding with `severity: MECHANICAL` in the latest pass entry.

If either condition is not met: halt with message "No MECHANICAL findings in validation report. Nothing to recover."

Do not proceed to Step 1 until both conditions are confirmed.

---

### Context Loading

Before proceeding, load the following artifacts:

- `plans/validation-reports/task-validation-report.yaml` — parse the **latest pass entry** (the last entry in the `passes` list) for MECHANICAL findings
- `plans/plan.yaml` — line-bounded reads of checkpoint sections for affected CP-IDs only (write targets, objective, acceptance criteria, gate command, seam context needed). Do not read sections for unaffected CPs.
- `plans/component-contracts.toml` — file registry
- `plans/seams.yaml` -- seam entries for affected components (via `seam_parser.load_seams()`)
- `plans/archive/CP-*/CP-*.status` — completed checkpoint status files

---

### Step 1 — Parse MECHANICAL Findings

Parse the latest pass entry from the validation report. Extract:

- Affected CP-IDs (all CPs that have at least one MECHANICAL finding)
- For each affected CP: the list of flags, their `detail` fields, and any `exclusions` arrays (present on ACTUAL_STATE_ASSERTION findings)

Hold this data in memory.

---

### Step 2 — Load Checkpoint Sections

For each affected CP-ID, use plan_parser to extract checkpoint data and connectivity tests:

```bash
uv run python -c "
import sys, json
sys.path.insert(0, '.claude/scripts')
from plan_parser import load_plan, find_checkpoint, connectivity_tests_for_cp
plan = load_plan('plans/plan.yaml')
cp = find_checkpoint(plan, 'CP-XX')
cts = connectivity_tests_for_cp(plan, 'CP-XX')
print(json.dumps({'cp': cp.model_dump(mode='json', exclude_none=True), 'cts': [ct.model_dump(mode='json', exclude_none=True) for ct in cts]}, indent=2))
"
```

Extract: description (objective), write targets, gate command, and matching CT specs.

Do not read sections for unaffected CPs.

---

### Step 3 — Regenerate Task Files

Regenerate the task file for each affected CP as YAML conforming to the `TaskFile` schema from `.claude/scripts/schemas.py`, using the same construction logic as `/io-plan-batch` Step D, with findings injected as negative constraints.

Apply each flag as follows:

- **WRITE_TARGET_ADDITION:** Remove the extra path from `declared_write_targets`. Use `plan.yaml` as the authoritative source.
- **WRITE_TARGET_OMISSION:** Add the missing path to `declared_write_targets` from `plan.yaml`.
- **CT_PATH_UNLISTED:** Add the CT file path (from the CT spec's `file:` field in `plan.yaml` where this CP is the `target_cp`) to `declared_write_targets`. This flag only applies to target_cp task files — source CPs must not have CT file paths in their write targets.
- **CONTEXT_FILE_IN_WRITE_TARGETS:** Move the file from `declared_write_targets` to the `context_files` list.
- **GATE_COMMAND_STALE:** Replace the `gate_command` field with the exact gate command from `plan.yaml` for this CP.
- **ACTUAL_STATE_ASSERTION (MECHANICAL):** Scope the `acceptance_criteria` to exclude the files listed in the finding's `exclusions` array. For each excluded file, add a note: "Note: [file] is owned by [owner] and is at ACTUAL state for this checkpoint. Do not assert TARGET state on it."
- **SEAM_ENTRY_MISSING:** Use `seam_parser.find_by_component(seams, name)` to read the component's seam entry from `plans/seams.yaml`, then project via the standalone function `seam_parser.to_seam_entry(comp)` and embed it in `seam_context` (fields: `receives_di`, `key_failure_modes`, `external_terminal` only).
- **FAILURE_MODE_UNCOVERED:** Extract the uncovered `key_failure_modes` entry text from the task file's `seam_context`. Synthesize an acceptance criterion from the failure mode description: "[ExceptionType] is raised when [condition]" (derived directly from the failure mode text, e.g., "RuntimeError when solver finds no feasible solution" becomes "RuntimeError is raised when the solver finds no feasible solution"). Insert into the task file's `acceptance_criteria` list.
- **SCHEMA_INVALID:** Regenerate the entire task file from scratch using `plan.yaml` as the sole source of truth (same construction logic as `/io-plan-batch` Step D). The original file's content is structurally broken and cannot be patched field-by-field.

Do NOT write to disk at this step. Hold regenerated content in memory.

---

### Step 4 — [HUMAN GATE] Present for Approval

Present each regenerated task file diff (what changed versus the original) to the user for review.

Format:

```
## /task-recovery — Regenerated Task Files

Affected CPs: CP-XX, CP-YY

### CP-XX changes:
- [List of changes made, one line per finding addressed]

[Full regenerated task file content for review]

---
Accept / Modify / Reject?
- Accept: YAML task files will be written to plans/tasks/. Re-run /validate-tasks after.
- Modify: describe changes. This step will be re-presented with your modifications.
- Reject: no files written. Return to user for manual intervention.
```

Do not proceed until the user responds.

---

### Step 5 — Write Approved Task Files

On Accept: write each approved task file to `plans/tasks/CP-XX.yaml` via Write tool. The PostToolUse YAML validation hook enforces schema correctness automatically. Confirm each file written.

On Modify: acknowledge the requested modifications. Do not write any files. Re-present Step 4 with the modifications applied.

On Reject: do not write any files. Return control to the user for manual intervention.

---

### Step 6 — Delete Stale Sentinels

For each CP whose task file was regenerated: delete `plans/tasks/CP-XX.task.validation` if it exists. This forces `/validate-tasks` to re-check the regenerated file on the next run.

---

### Step 7 — Remind User

Output: "Task files regenerated. Re-run /validate-tasks to validate before dispatch."

---

## Constraints

- Does not modify `plan.yaml`, `component-contracts.toml`, `seams.yaml`, or other source-of-truth artifacts
- Human approval gate (Step 4) is mandatory before any file is written
- Does not invoke `/validate-tasks` — no circular dependency
- Deletes stale `.task.validation` sentinels so `/validate-tasks` re-checks regenerated files
- Only processes MECHANICAL findings — DESIGN findings are not routable here

---

## Related

- `/validate-tasks` — upstream; produces the validation report and invokes this command
- `/io-plan-batch` — Step D defines the task file construction logic this command replicates
- `plans/validation-reports/task-validation-report.yaml` — input: MECHANICAL findings
- `plans/tasks/CP-XX.yaml` — output: regenerated task files (validated against `TaskFile` schema from `.claude/scripts/schemas.py`)

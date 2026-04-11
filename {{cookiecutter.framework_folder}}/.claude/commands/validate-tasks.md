---
name: validate-tasks
description: Validate generated task files against plan.yaml and component-contracts.yaml before agent dispatch. Sits between /io-plan-batch and dispatch-agents.sh.
---

# /validate-tasks

## Purpose

Validate all task files in `plans/tasks/` against source-of-truth artifacts before sub-agents are dispatched. Finds authoring errors that cannot be fixed deterministically (DESIGN) and ones that can (MECHANICAL). Routes MECHANICAL findings to `/task-recovery` and escalates DESIGN findings to the user immediately.

```
/io-checkpoint -> /validate-plan -> /io-plan-batch -> [/validate-tasks] -> dispatch-agents.sh
                                                              |
                                             MECHANICAL       |   DESIGN
                                             findings         |   findings
                                                 |            |       |
                                                 v            |       v
                                          /task-recovery      |   escalate
                                                 |            |   to user
                                                 +------------+
```

Does **not** edit task files. Remediation is owned by `/task-recovery`.

---

## Step 0 — [HARD GATE] Pre-invoke Script

Run `bash .claude/scripts/pre-invoke-validate-tasks.sh`.

If it exits non-zero, HALT immediately with the error message from the script. Do not proceed.

---

## Step 0.5 -- Schema Validation

For each `plans/tasks/CP-*.yaml` file, run:

    uv run python -c "import sys; sys.path.insert(0, '.claude/scripts'); from task_parser import load_task; load_task('TASK_FILE_PATH')"

For each file that throws `ValidationError` or `ValueError`:

- Record a `SCHEMA_INVALID` finding with the error message as `detail`
- Continue checking remaining files (do not halt on first failure)

Files that fail schema validation are **excluded from semantic checks** (Checks 1-5). They cannot be parsed into `TaskFile`, so semantic checks would produce cascading false positives.

Files that pass schema validation proceed to Context Loading and Checks 1-5 as normal.

---

## Context Loading

Load in a single phase — no re-reads during check execution:

- `plans/plan.yaml` — line-bounded reads of checkpoint sections per CP-ID (write targets, `Depends on` chains)
- `plans/component-contracts.yaml` — component-to-file mapping
- `plans/tasks/CP-*.yaml` — all task files in the current batch
- `plans/archive/CP-*/CP-*.status` — completed checkpoint status (glob, then read each)
- `plans/seams.yaml` -- seam entries for completeness check (via `seam_parser.load_seams()`)

**Token budget estimate:** ~3000–6000 tokens. Read only the sections for CP-IDs present in `plans/tasks/`.

---

## Five Checks

Run all five checks on every task file before classifying severity.

### Check 1 — WRITE_TARGET_FIDELITY

The task file's `write_targets` field must exactly match the write targets declared in `plans/plan.yaml` for that CP-ID.

- Compare task file write targets against `plan.yaml` one-for-one.
- **WRITE_TARGET_ADDITION:** Task file lists a path not in `plan.yaml` (CT paths exempt — see below).
- **WRITE_TARGET_OMISSION:** `plan.yaml` lists a path absent from the task file.
- **CT_PATH_UNLISTED:** A connectivity test's `file:` path from `plan.yaml` where this CP is the `target_cp` is not in the task file's write targets. Only the `target_cp` of a CT is required to list the CT file path (per io-plan-batch Step D). Source CPs must NOT have CT file paths in their write targets.
- **CONTEXT_FILE_IN_WRITE_TARGETS:** A file appears in both write targets and the task file's context/reference section (read-only files must not be declared as write targets).

CT file paths derived from the CT spec's `file:` field in `plan.yaml` where this CP is the `target_cp` are exempt from WRITE_TARGET_ADDITION. If a source-only CP's task file lists a CT file path, flag it as WRITE_TARGET_ADDITION (not exempt).

### Check 2 — GATE_COMMAND_VALIDITY

The task file's gate command must reference only files that exist or will exist as write targets of this checkpoint or a predecessor archived PASS.

- **GATE_COMMAND_STALE:** The gate command references a file path that differs from what `plan.yaml` specifies for this CP.
- **GATE_REFERENCES_NONEXISTENT:** The gate command references a file not in write targets and not in any archived-PASS checkpoint's write targets. No known source of truth for this path.
- **GATE_DEPENDS_ON_BLOCKED:** The gate command depends on output from an upstream CP that is neither archived PASS nor an earlier sequence position in the current batch.

### Check 3 — ACTUAL_TARGET_SCOPE

Acceptance criteria must not assert TARGET state (post-implementation behavior) on files still at ACTUAL state (not yet written by this CP or any archived-PASS predecessor).

Apply the computability test from `.claude/references/task-state-assertion-routing.md`:

1. Build the file-to-checkpoint map from `plan.yaml` write targets.
2. Compute the transitive reachable set: archived PASS checkpoints + this CP's own write targets.
3. Scan acceptance criteria for explicit file paths and broad directory patterns.
4. For each referenced path outside the reachable set: determine whether the full exclusion set is derivable from `plan.yaml` + `component-contracts.yaml`.

- **ACTUAL_STATE_ASSERTION (exclusions computable):** Criterion asserts TARGET state on an unreachable file, and the full exclusion set is derivable from plan.yaml + component-contracts.yaml. → MECHANICAL. Include computed exclusions in the finding detail.
- **ACTUAL_STATE_ASSERTION (exclusions have gaps):** Criterion asserts TARGET state on an unreachable file, but the exclusion set contains paths absent from `component-contracts.yaml` or unresolvable dependency links. → DESIGN.
- **ACTUAL_STATE_UNCERTAIN:** An acceptance criterion's scope is ambiguous (e.g., implicit "all components" language without a file list). Log count, do not halt.
- **ACCEPTANCE_CRITERION_UNTESTABLE:** An acceptance criterion cannot be verified by any deterministic command or file check. Log count, do not halt.

### Check 4 — SEAM_CONTEXT_COMPLETENESS

Every `src/` component in the checkpoint's write targets must have a seam entry in the task file's `seam_context` field.

- **SEAM_ENTRY_MISSING:** A component from write targets has no entry in the task file's `seam_context` field.
- **SEAM_ENTRY_STALE:** The task file's seam data diverges from `plans/seams.yaml` (field values differ). Use `seam_parser.find_by_component(seams, name)` and the standalone function `seam_parser.to_seam_entry(comp)` for comparison. Log count, surface in summary. Not a blocking finding.
- **SEAM_SOURCE_FABRICATED:** The task file contains a seam entry for a component that has no entry in `plans/seams.yaml`, or field values (`receives_di`, `key_failure_modes`, `external_terminal`) do not match. -> DESIGN.
- **FAILURE_MODE_UNCOVERED:** A `key_failure_modes` entry in the task file's `seam_context` has no corresponding entry in `acceptance_criteria`. The comparison is textual: the exception type and condition description from the failure mode must appear (in substance, not verbatim) in at least one acceptance criterion. If an acceptance criterion contains `[DEFERRED: justification]` for the failure mode, the check passes for that entry. -> MECHANICAL (the failure mode text provides sufficient information for `/task-recovery` to synthesize the missing criterion).

### Check 5 — WRITE_TARGET_OVERLAP

Cross-task check: no file path may appear in more than one task file's `write_targets`.

This check operates on the assembled task files (not `plan.yaml`), so it catches overlaps introduced by CT path injection. Since CT files are injected only into the `target_cp`'s write targets (per `/io-plan-batch` Step D), a CT file should appear in exactly one task file. A collision here indicates either a misassigned `target_cp` or a manual error.

For each task file, collect its `write_targets`. Build a map of `file_path -> list[CP-ID]`. Any path claimed by two or more CPs is a collision.

- **WRITE_TARGET_OVERLAP:** A file path appears in the `write_targets` of two or more task files. The `detail` field must name the file and all claiming CPs. Emit one finding per colliding file, with `task_file` set to the first CP-ID alphabetically.

Severity is always DESIGN: the checkpoint decomposition has overlapping scope. Automated recovery cannot decide which CP should own the file -- that requires re-planning.

---

## Flag Taxonomy

| Flag | Check | Severity | Routing |
|------|-------|----------|---------|
| `WRITE_TARGET_ADDITION` | WRITE_TARGET_FIDELITY | MECHANICAL | /task-recovery |
| `WRITE_TARGET_OMISSION` | WRITE_TARGET_FIDELITY | MECHANICAL | /task-recovery |
| `CT_PATH_UNLISTED` | WRITE_TARGET_FIDELITY | MECHANICAL | /task-recovery (target_cp only) |
| `CONTEXT_FILE_IN_WRITE_TARGETS` | WRITE_TARGET_FIDELITY | MECHANICAL | /task-recovery |
| `GATE_COMMAND_STALE` | GATE_COMMAND_VALIDITY | MECHANICAL | /task-recovery |
| `GATE_REFERENCES_NONEXISTENT` | GATE_COMMAND_VALIDITY | DESIGN | Escalate |
| `GATE_DEPENDS_ON_BLOCKED` | GATE_COMMAND_VALIDITY | DESIGN | Escalate (unless upstream archived PASS) |
| `ACTUAL_STATE_ASSERTION` (exclusions computable) | ACTUAL_TARGET_SCOPE | MECHANICAL | /task-recovery with computed exclusions |
| `ACTUAL_STATE_ASSERTION` (exclusions have gaps) | ACTUAL_TARGET_SCOPE | DESIGN | Escalate |
| `ACTUAL_STATE_UNCERTAIN` | ACTUAL_TARGET_SCOPE | OBSERVATION | Log, surface count in summary |
| `SEAM_ENTRY_MISSING` | SEAM_CONTEXT_COMPLETENESS | MECHANICAL | /task-recovery |
| `SEAM_ENTRY_STALE` | SEAM_CONTEXT_COMPLETENESS | OBSERVATION | Log, surface count in summary |
| `SEAM_SOURCE_FABRICATED` | SEAM_CONTEXT_COMPLETENESS | DESIGN | Escalate |
| `FAILURE_MODE_UNCOVERED` | SEAM_CONTEXT_COMPLETENESS | MECHANICAL | /task-recovery |
| `ACCEPTANCE_CRITERION_UNTESTABLE` | ACTUAL_TARGET_SCOPE | OBSERVATION | Log, surface count in summary |
| `WRITE_TARGET_OVERLAP` | WRITE_TARGET_OVERLAP | DESIGN | Escalate |
| `SCHEMA_INVALID` | SCHEMA_VALIDATION | MECHANICAL | /task-recovery |

---

## Execution Flow

```
Step 0: [HARD GATE] bash .claude/scripts/pre-invoke-validate-tasks.sh
Step 0.5: Schema validation — run load_task() on each CP-*.yaml.
          SCHEMA_INVALID files are excluded from Steps 1-2.
Step 1: Load context (plan.yaml sections, component-contracts.yaml, task files,
        archive status, seams.yaml)
Step 2: Run all five checks on all task files
Step 3: Classify findings by severity using the flag taxonomy.
        For ACTUAL_STATE_ASSERTION: apply computability test
        (references/actual-target-heuristic.md) to determine MECHANICAL vs DESIGN.
Step 4: Stagnation check — read the previous pass from
        plans/validation-reports/task-validation-report.yaml (if it exists).
        If any finding (same flag + same task file) persisted unchanged from the previous
        pass, escalate its severity to DESIGN.
Step 5: [HALT GATE] If any DESIGN findings exist:
        - Append a FAIL pass entry to
          plans/validation-reports/task-validation-report.yaml
        - Present each DESIGN finding to the user: task file, flag, detail.
        - Do NOT enter the recovery loop. Halt and await user action.
Step 6: If only MECHANICAL findings remain:
        - Append a FAIL pass entry to the validation report
        - Invoke /task-recovery (it reads the report for MECHANICAL findings)
        - /task-recovery regenerates affected task files with a human approval gate
        - After /task-recovery writes approved task files, re-run from Step 1
        - Max cycles: read validation.tasks.max_regen_cycles from
          .claude/iocane.config.yaml (default: 3)
        - If cycles exhausted without PASS: escalate remaining findings to DESIGN
          and halt (Step 5 path)
Step 7: If all task files pass all five checks:
        - Write a .task.validation sentinel per task file:
            plans/tasks/CP-XX.task.validation
          Content: PASS <YYYY-MM-DDTHH:MM:SS> pass-N
          (N = 1-indexed pass number from the validation report)
        - Append a PASS entry to plans/validation-reports/task-validation-report.yaml
        - If any OBSERVATION findings were logged, surface the count:
          "N observations logged — review plans/validation-reports/task-validation-report.yaml
          before dispatch"
        - Remind the user: bash .claude/scripts/dispatch-agents.sh
```

---

## Sentinel Files

Each validated task file receives a sentinel at `plans/tasks/CP-XX.task.validation`.

**Format:** `PASS YYYY-MM-DDTHH:MM:SS pass-N`

**Design rationale:**

- Consistent with the existing `.status` file pattern
- No markdown string matching or formatting dependency
- `dispatch-agents.sh` checks `[ -f "$TASKS_DIR/$CP_ID.task.validation" ]`
- `/task-recovery` deletes the sentinel for regenerated CPs, forcing re-validation

Sentinel files are ephemeral local state — not committed to git. The validation report is the committed audit trail.

---

## Validation Report

Written to `plans/validation-reports/task-validation-report.yaml`. Schema: `.claude/templates/task-validation-report.yaml`.

**Lifecycle:** Passes are appended within a cycle (validate-tasks → task-recovery → validate-tasks). When `/io-plan-batch` creates a new batch, the report is overwritten (fresh start per batch). `dispatch-agents.sh` commits the final report as an audit checkpoint before dispatch.

---

## Constraints

- Does NOT edit task files
- Does NOT edit `plan.yaml`, `project-spec.md`, or `component-contracts.yaml`
- Remediation owned by `/task-recovery`
- DESIGN findings escalate immediately — never enter the recovery loop
- Same finding persisting across two consecutive passes → escalate to DESIGN
- Max regen cycles governed by `validation.tasks.max_regen_cycles` in `iocane.config.yaml`

---

## Related

- `/io-plan-batch` — upstream; produces task files
- `/task-recovery` — downstream on MECHANICAL findings; regenerates affected task files
- `bash .claude/scripts/dispatch-agents.sh` — downstream on PASS; dispatches agents
- `.claude/references/task-state-assertion-routing.md` — computability test for ACTUAL_TARGET_SCOPE
- `.claude/templates/task-validation-report.yaml` — validation report schema
- `.claude/iocane.config.yaml` — `validation.tasks.max_regen_cycles`

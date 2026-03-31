---
name: validate-tasks
description: Validate generated task files against plan.md and component-contracts.toml before agent dispatch. Sits between /io-plan-batch and dispatch-agents.sh.
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

## Context Loading

Load in a single phase — no re-reads during check execution:

- `plans/plan.md` — line-bounded reads of checkpoint sections per CP-ID (write targets, `Depends on` chains)
- `plans/component-contracts.toml` — component-to-file mapping
- `plans/tasks/CP-*.md` — all task files in the current batch
- `plans/archive/CP-*/CP-*.status` — completed checkpoint status (glob, then read each)
- `plans/seams.md` — seam entries for completeness check

**Token budget estimate:** ~3000–6000 tokens. Read only the sections for CP-IDs present in `plans/tasks/`.

---

## Four Checks

Run all four checks on every task file before classifying severity.

### Check 1 — WRITE_TARGET_FIDELITY

The task file's `## Declared Write Targets` must exactly match the write targets declared in `plans/plan.md` for that CP-ID.

- Compare task file write targets against `plan.md` one-for-one.
- **WRITE_TARGET_ADDITION:** Task file lists a path not in `plan.md` (CT paths exempt — see below).
- **WRITE_TARGET_OMISSION:** `plan.md` lists a path absent from the task file.
- **CT_PATH_UNLISTED:** A connectivity test's `file:` path from `plan.md` is not in the task file's write targets (CT paths must be present per io-plan-batch Step D).
- **CONTEXT_FILE_IN_WRITE_TARGETS:** A file appears in both write targets and the task file's context/reference section (read-only files must not be declared as write targets).

CT file paths derived from the CT spec's `file:` field in `plan.md` are exempt from WRITE_TARGET_ADDITION.

### Check 2 — GATE_COMMAND_VALIDITY

The task file's gate command must reference only files that exist or will exist as write targets of this checkpoint or a predecessor archived PASS.

- **GATE_COMMAND_STALE:** The gate command references a file path that differs from what `plan.md` specifies for this CP.
- **GATE_REFERENCES_NONEXISTENT:** The gate command references a file not in write targets and not in any archived-PASS checkpoint's write targets. No known source of truth for this path.
- **GATE_DEPENDS_ON_BLOCKED:** The gate command depends on output from an upstream CP that is neither archived PASS nor an earlier sequence position in the current batch.

### Check 3 — ACTUAL_TARGET_SCOPE

Acceptance criteria must not assert TARGET state (post-implementation behavior) on files still at ACTUAL state (not yet written by this CP or any archived-PASS predecessor).

Apply the computability test from `references/actual-target-heuristic.md`:

1. Build the file-to-checkpoint map from `plan.md` write targets.
2. Compute the transitive reachable set: archived PASS checkpoints + this CP's own write targets.
3. Scan acceptance criteria for explicit file paths and broad directory patterns.
4. For each referenced path outside the reachable set: determine whether the full exclusion set is derivable from `plan.md` + `component-contracts.toml`.

- **ACTUAL_STATE_ASSERTION (exclusions computable):** Criterion asserts TARGET state on an unreachable file, and the full exclusion set is derivable from plan.md + component-contracts.toml. → MECHANICAL. Include computed exclusions in the finding detail.
- **ACTUAL_STATE_ASSERTION (exclusions have gaps):** Criterion asserts TARGET state on an unreachable file, but the exclusion set contains paths absent from `component-contracts.toml` or unresolvable dependency links. → DESIGN.
- **ACTUAL_STATE_UNCERTAIN:** An acceptance criterion's scope is ambiguous (e.g., implicit "all components" language without a file list). Log count, do not halt.
- **ACCEPTANCE_CRITERION_UNTESTABLE:** An acceptance criterion cannot be verified by any deterministic command or file check. Log count, do not halt.

### Check 4 — SEAM_CONTEXT_COMPLETENESS

Every `src/` component in the checkpoint's write targets must have a seam entry in the task file's `## Seam Context` section.

- **SEAM_ENTRY_MISSING:** A component from write targets has no entry in the task file's `## Seam Context` section.
- **SEAM_ENTRY_STALE:** The task file's seam data diverges from `plans/seams.md` (field values differ). Log count, surface in summary. Not a blocking finding.
- **SEAM_SOURCE_FABRICATED:** The task file contains a seam entry for a component that has no entry in `plans/seams.md`, or field values (`Receives (DI)`, `Key failure modes`, `External terminal`) do not match any `plans/seams.md` entry. → DESIGN.

---

## Flag Taxonomy

| Flag | Check | Severity | Routing |
|------|-------|----------|---------|
| `WRITE_TARGET_ADDITION` | WRITE_TARGET_FIDELITY | MECHANICAL | /task-recovery |
| `WRITE_TARGET_OMISSION` | WRITE_TARGET_FIDELITY | MECHANICAL | /task-recovery |
| `CT_PATH_UNLISTED` | WRITE_TARGET_FIDELITY | MECHANICAL | /task-recovery |
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
| `ACCEPTANCE_CRITERION_UNTESTABLE` | ACTUAL_TARGET_SCOPE | OBSERVATION | Log, surface count in summary |

---

## Execution Flow

```
Step 0: [HARD GATE] bash .claude/scripts/pre-invoke-validate-tasks.sh
Step 1: Load context (plan.md sections, component-contracts.toml, task files,
        archive status, seams.md)
Step 2: Run all four checks on all task files
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
Step 7: If all task files pass all four checks:
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
- Does NOT edit `plan.md`, `project-spec.md`, or `component-contracts.toml`
- Remediation owned by `/task-recovery`
- DESIGN findings escalate immediately — never enter the recovery loop
- Same finding persisting across two consecutive passes → escalate to DESIGN
- Max regen cycles governed by `validation.tasks.max_regen_cycles` in `iocane.config.yaml`

---

## Related

- `/io-plan-batch` — upstream; produces task files
- `/task-recovery` — downstream on MECHANICAL findings; regenerates affected task files
- `bash .claude/scripts/dispatch-agents.sh` — downstream on PASS; dispatches agents
- `references/actual-target-heuristic.md` — computability test for ACTUAL_TARGET_SCOPE
- `.claude/templates/task-validation-report.yaml` — validation report schema
- `.claude/iocane.config.yaml` — `validation.tasks.max_regen_cycles`

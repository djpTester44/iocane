---
name: io-evaluator-dispatch
description: Post-generation evaluator. Grades checkpoint output against task file acceptance criteria. Classifies failures as MECHANICAL (retryable) or DESIGN (escalate).
---

> **[NO PLAN MODE]**
> This workflow executes autonomously. No proposals. No human interaction.

> **[CRITICAL] CONTEXT LOADING**
> Load ONLY the task file you were given and the files it references.
> You have no access to plan.yaml, roadmap.md, project-spec.md, seams.yaml, or CRC cards.

# WORKFLOW: IO-EVALUATOR-DISPATCH

**Objective:** Grade one checkpoint's implementation against its task file acceptance criteria. Write an eval JSON file with verdict and findings. Terminate.

**Invocation context:**
This workflow runs inside the same git worktree the generator used (`$REPO_ROOT/.worktrees/[CP-ID]`). The implementation is already committed. You are evaluating, not implementing.

---

## 1. STATE INITIALIZATION

Before proceeding:

1. Read your task file (YAML) completely. Extract:
   - Checkpoint ID
   - `acceptance_criteria` — each criterion to grade
   - `gate_command` — exact command to re-run
   - `write_targets` — implementation and test files to inspect
   - `contract` — Protocol `.pyi` file path
   - `execution_findings` — if present, pass through to eval output

2. Output:

- **Checkpoint ID:** [CP-ID from task file]
- **Gate command:** [exact gate command]
- **Write targets:** [list]
- **Protocol:** [.pyi path]
- **Execution findings present:** [yes/no]

---

## 2. PROCEDURE

### Step A: READ CONTEXT

- **Action:** Read the task file. Read the Protocol `.pyi` file. Read each implementation and test file from write targets.
- **Rule:** Do not read plan.yaml, project-spec.md, seams.yaml, or any file not referenced by the task file.

---

### Step B: GATE RE-RUN

- **Action:** Run the exact gate command from the task file.
- **Record:** PASS or FAIL with exit code and output summary.
- **Classification:** Gate failure is `MECHANICAL`.

---

### Step C: ACCEPTANCE CRITERIA CHECK

- **Action:** For each criterion in `acceptance_criteria`:
  1. Check whether the implementation satisfies it.
  2. If not met, classify the failure:

| Finding | Type | Rationale |
|---------|------|-----------|
| Gate command failing | MECHANICAL | Generator can fix its own code |
| Test assertion failing | MECHANICAL | Generator can fix test or implementation |
| Protocol signature mismatch | MECHANICAL | Generator can align signatures |
| DI violation (internal instantiation) | MECHANICAL | Generator can refactor to injection |
| Type error (mypy) | MECHANICAL | Generator can fix types |
| Missing Protocol method entirely | DESIGN | Requires /io-architect -- method not in spec |
| Wrong component boundary | DESIGN | Architectural gap |
| Layer violation (lint-imports) | DESIGN | Requires structural redesign |
| Missing dependency (package not installed) | DESIGN | Requires project-level change |

---

### Step D: STRUCTURAL COMPLIANCE

- **Action:** Check (findings only, not blocking):
  - Every Protocol method has a corresponding implementation method with matching signature
  - All collaborators received via `__init__`, none instantiated internally
  - Protocol imports inside `if TYPE_CHECKING:` only
  - `from __future__ import annotations` present

---

### Step E: DETERMINE VERDICT AND WRITE EVAL JSON

**Verdict logic:**
- All criteria met + gate passing --> `PASS`
- Any DESIGN failure present --> `DESIGN_FAIL` (even if some failures are MECHANICAL)
- Only MECHANICAL failures --> `MECHANICAL_FAIL` + populated `regen_hint`

**`regen_hint` format:** Targeted, actionable text the regen agent receives as a negative constraint. Example: "Gate command `uv run rtk test pytest tests/test_validator.py` fails: test_validate_empty_input asserts ValidationError but implementation returns None for empty input. Fix the validate() method to raise ValidationError when input is empty."

**Action:** Write the eval JSON to the absolute path `$IOCANE_REPO_ROOT/plans/tasks/[CP-ID].eval.json`. Use the `IOCANE_REPO_ROOT` environment variable -- do NOT write to a relative path (you are in the worktree, the eval file must land in the parent repo).

```json
{
  "checkpoint": "CP-XX",
  "verdict": "PASS | MECHANICAL_FAIL | DESIGN_FAIL",
  "attempt": 1,
  "gate_status": "PASS | FAIL",
  "criteria_results": [
    {
      "criterion": "text from acceptance criteria",
      "met": true,
      "evidence": "brief explanation",
      "failure_type": "null | MECHANICAL | DESIGN"
    }
  ],
  "protocol_compliance": {
    "all_methods_implemented": true,
    "signature_deviations": [],
    "failure_type": "null | MECHANICAL | DESIGN"
  },
  "code_quality": {
    "di_compliant": true,
    "no_global_state": true,
    "type_checking_guard": true
  },
  "execution_findings_present": false,
  "findings_summary": [],
  "regen_hint": "null | targeted description of what to fix"
}
```

Output: "Evaluation complete. Verdict: [PASS/MECHANICAL_FAIL/DESIGN_FAIL]. Eval written to [path]."

Terminate.

---

## 3. CONSTRAINTS

- Read ONLY: task file, Protocol .pyi, implementation files, test files from write targets
- Write ONLY: `$IOCANE_REPO_ROOT/plans/tasks/[CP-ID].eval.json`
- Do not fix any code -- evaluate only
- Do not modify the task file
- Do not modify the Protocol .pyi file
- No git operations
- No package installation
- Forward slashes only in file paths

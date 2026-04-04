---
name: io-review
description: Per-checkpoint behavioral review and connectivity verification. Findings route to backlog.md.
---

> **[NO PLAN MODE]**
> Read-only analysis. No file writes except `plans/seams.md` (Step F) and via /review-capture at the end.

> **[CRITICAL] CONTEXT LOADING**
>
> 1. Load planning rules: `view_file .claude/rules/planning.md`
> 2. Load the component registry: `view_file plans/component-contracts.toml`
> 3. Load the checkpoint being reviewed from `plans/plan.md`
> 4. Load CRC cards for checkpoint components from `plans/project-spec.md`
> 5. Load relevant Protocol contracts from `interfaces/*.pyi`
> 6. Load the Integration Seams reference: `view_file plans/seams.md`
> 7. Load the task file: `view_file plans/tasks/[CP-ID].md` -- check for `## Execution Findings` and `## Evaluator Result`

# WORKFLOW: REVIEW

**Objective:** Verify that a completed checkpoint's implementation matches its CRC behavioral contract and that all connectivity tests at its seams are green.

**Scope:** Single checkpoint. Do not review components outside the current checkpoint's boundaries.

**Position in chain:**

```
(sub-agents complete) -> [/io-review] -> dispatch-agents.sh (next batch) | /gap-analysis (full system)
```

---

## 1. STATE INITIALIZATION

Before proceeding, output:

- **Checkpoint under review:** [CP-ID and name]
- **Components in scope:** [list from plan.md]
- **Protocols in scope:** [list from plan.md]
- **Gate command status:** [PASS / FAIL — run gate command to verify]
- **Connectivity tests in scope:** [list CT-IDs at this checkpoint's seams]

---

## 2. PROCEDURE

### Step A: GATE VERIFICATION

- **Action:** Run the checkpoint's gate command from `plans/plan.md`.
- **Rule:** If gate is not passing, the checkpoint is not complete. Stop.
- **Output:** "GATE: [PASS/FAIL] — [gate command]"

---

### Step B: CONNECTIVITY TEST VERIFICATION

- **Action:** For each connectivity test listed in `plans/plan.md` at this checkpoint's output seams:
  1. Check whether the CT test file exists on disk at the `file:` path in the CT spec.
  2. If it exists: run the gate command and report PASS or FAIL.
  3. If it does **not** exist: report as `MISSING`. A missing CT file is a HIGH-severity finding — the sub-agent failed to create it during `/io-execute` Step E. Record in the findings report and route to backlog.
- **Rule:** Every connectivity test must be green (and present) before this checkpoint is considered approved.
- **Output:** For each CT: `CT-[NNN]: [PASS/FAIL/MISSING] -- [test file::function]`

---

### Step B2: EXECUTION FINDINGS AND EVAL TRIAGE

- **Action:** Check whether the task file (`plans/tasks/[CP-ID].md`) contains
  `## Execution Findings`.
- **If present:**
  1. For each finding row, assess:
     - Is the observation accurate? (Spot-check the adjacent file.)
     - Did the agent work around the issue appropriately?
     - Does this warrant a backlog entry?
  2. Classify each as:
     - `CONFIRMED` -- real issue, route to backlog via Step I
     - `WORKAROUND_OK` -- agent handled it acceptably, note but no action
     - `FALSE_POSITIVE` -- agent misidentified, discard
  3. `CONFIRMED` findings become MEDIUM-severity entries in Step H with tag `[ADJACENT]`.
- **If absent:** No execution findings. Proceed.

- **Action:** Check whether `plans/tasks/[CP-ID].eval.json` exists.
- **If verdict is `EVAL_SKIPPED`:** The automated evaluator did not run (crash or timeout).
  Apply extra scrutiny in Steps D-G. Note in Step H findings: "Automated evaluator skipped -- manual review substituted."
- **If verdict is `PASS`:** Note eval passed. Proceed normally.
- **If eval.json absent:** Checkpoint predates evaluator pipeline. Proceed normally.

---

### Step C: LOAD BEHAVIORAL ANCHORS

- **Action:** Read the CRC card for each component in scope from `plans/project-spec.md`.
- **Action:** Read the Protocol contract for each component from `interfaces/*.pyi`.
- **Goal:** Establish the behavioral intent before reading implementation.

---

### Step D: STRUCTURAL PRE-SCAN

For each implementation file in the checkpoint's write targets:

- Run `uv run python .claude/scripts/extract_structure.py <file>` — map public surface area
- Run `bash .claude/scripts/run-compliance.sh <write_targets>` — ruff, mypy, lint-imports, bandit, DI check
- Invoke `/symbol-tracer` with `--summary` on the checkpoint's Protocol symbols — verify Protocol is consumed
- **Registry check:** For each write target under `src/`, verify the file path (or its parent component) appears in `plans/component-contracts.toml` under `[components]`. A `src/` file whose component is absent from the TOML registry is a HIGH finding: `UNREGISTERED_WRITE_TARGET` — route to `/io-architect` before the checkpoint can be considered approved. `tests/` files and tooling files outside `src/` are exempt.
- **[HARD] Location check:** For each write target that is a `.py` file, verify it resides under `src/` or `tests/`. A `.py` file outside these directories is a HIGH finding: `MISPLACED_RUNTIME_MODULE`. The `interfaces/` directory must contain only `.pyi` stub files; any `.py` file there is a violation. Record in findings and route to backlog -- do not defer to Step E.

Flag any violations. Do not fix — record for findings.

---

### Step E: BEHAVIORAL REVIEW

For each component in scope, verify:

- **CRC Responsibilities:** Does the implementation fulfill every responsibility listed in the CRC card? Flag any responsibility with no corresponding implementation.
- **CRC Must-Nots:** Does the implementation violate any explicit constraint in the CRC card?
- **Protocol compliance:** Does every public method match its Protocol signature exactly? Flag any signature deviation.
- **Collaborators:** Are all collaborators received via `__init__`? Flag any that are instantiated internally.
- **Sequence diagrams:** If a sequence diagram exists in `project-spec.md` for this component's flows, does the implementation follow it?
- **Side effects:** Are there any observable side effects not described in the CRC?

---

### Step F: SEAMS SYNC

For each component in scope, compare the actual `__init__` signature in `src/` against the component's entry in `plans/seams.md`.

**Check each field for drift:**

- **Receives (DI):** Compare `__init__` parameters against the `Receives (DI)` field. Flag any parameter added, removed, renamed, or re-typed since the last `/io-architect` run.
- **External terminal:** Scan the implementation for direct client instantiation (e.g., `httpx.AsyncClient()`, `boto3.client()`, `create_async_engine()`) that is not reflected in the `External terminal` field.
- **Key failure modes:** Compare raised exception types in the implementation against the `Key failure modes` field. Flag any new exception type not listed, or any listed exception no longer raised.

**Actions:**

- If drift is detected: update `plans/seams.md` in place for each affected component. Record each change as a LOW-severity finding in Step H ("Seams drift — updated `plans/seams.md`").
- If a component in scope has no entry in `plans/seams.md` at all: create the entry using the same field schema. Record as MEDIUM-severity ("Missing seam entry — created in `plans/seams.md`").
- Do **not** modify the `Backlog refs` field — that is populated by `/review-capture` only.
- Do **not** update seam entries for components outside the current checkpoint's scope.

---

### Step G: CORRECTNESS REVIEW

- Logic errors, edge cases not covered by tests
- Error handling — are failure modes handled or silently swallowed?
- Type correctness beyond what mypy catches (semantic type misuse)
- Test quality — do tests assert meaningful behavior, or just "does not raise"?

---

### Step H: OUTPUT FINDINGS

Generate a findings report:

```markdown
## Review: [CP-ID] — [Checkpoint Name]

### Summary
[One paragraph overall assessment]

### Gate Status
- Gate: PASS/FAIL
- Connectivity tests: [N/N passing]

### Findings

| Severity | Location | Issue | Recommendation |
|----------|----------|-------|----------------|
| HIGH | `src/[path]:[line]` | [issue] | [fix] |
| MEDIUM | ... | ... | ... |

### Strengths
- [What was done well]

### Action Items
- [ ] [Specific fix needed]
```

**Severity guide:**

- HIGH: Unanchored behavior (contradicts CRC), broken connectivity test, DI violation, layer violation
- MEDIUM: Should fix -- affects maintainability or contract completeness
- ADJACENT (MEDIUM): Bug or gap in code outside checkpoint scope, reported by execution agent
- LOW: Nice to fix -- minor improvement
- INFO: Observation only

---

### Step I: ROUTE FINDINGS

- **Action:** Run `/review-capture` to classify and log all HIGH and MEDIUM findings to `plans/review-output.md` (staging file).
- **Rule:** Findings not captured in staging are invisible to subsequent workflows. This step is mandatory if any HIGH or MEDIUM findings exist. Findings flow from staging to `plans/backlog.md` via `/io-backlog-triage`.

---

### Step J: REVIEW COMPLETE — FINDING ROUTING

Completion is already registered in `plan.md` by `dispatch-agents.sh` at merge time. This step routes review findings and cleans up task artifacts.

**Single CP — present to the human:**

```
REVIEW COMPLETE: [CP-ID]

Findings: [N HIGH], [N MEDIUM], [N LOW]

Options:
1. No actionable findings — archive task artifacts and proceed
2. Route findings to backlog for remediation
3. Escalate to /io-architect — finding reveals a design gap
```

**Batch (multiple CPs from completed wave) — present to the human:**

```
REVIEW COMPLETE: Wave [N]

| CP    | HIGH | MEDIUM | LOW | Routing                      |
|-------|------|--------|-----|------------------------------|
| CP-XX | 0    | 2      | 1   | Route 2 MEDIUM to backlog    |
| CP-YY | 0    | 0      | 1   | No actionable findings       |
| CP-ZZ | 0    | 0      | 0   | No actionable findings       |

Recommended:
- Route findings for [CPs with actionable findings] via /review-capture
- Archive task artifacts: bash .claude/scripts/archive-approved.sh [all CP-IDs]
```

- **Human decides.** Do not auto-approve.
- **If option 1 selected (or batch archive recommended):** Run `bash .claude/scripts/archive-approved.sh [CP-ID ...]` — this moves task artifacts to `plans/archive/[CP-ID]/`, and for remediation checkpoints automatically marks all corresponding backlog items as `[x]` with a `Remediated:` annotation.
- **If option 2 selected:** Run `/review-capture` to route findings to `plans/backlog.md`. Findings become new work items (remediation checkpoints), not re-execution of the original CP.

---

## 3. CONSTRAINTS

- Scope is strictly limited to the current checkpoint's components
- Do not review components from other checkpoints even if they appear in the same files
- Do not make fixes — output findings only (exception: `plans/seams.md` is updated in Step F to stay in sync with implementation)
- Do not route findings to `plans/plan.md` — backlog goes to `plans/backlog.md` only
- No git operations

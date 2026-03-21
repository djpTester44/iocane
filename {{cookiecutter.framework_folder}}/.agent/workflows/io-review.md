---
description: Per-checkpoint behavioral review and connectivity verification. Findings route to backlog.md.
---

> **[NO PLAN MODE]**
> Read-only analysis. No file writes except `plans/seams.md` (Step F) and via /review-capture at the end.

> **[CRITICAL] CONTEXT LOADING**
>
> 1. Load planning rules: `view_file .agent/rules/planning.md`
> 2. Load the checkpoint being reviewed from `plans/plan.md`
> 3. Load CRC cards for checkpoint components from `plans/project-spec.md`
> 4. Load relevant Protocol contracts from `interfaces/*.pyi`
> 5. Load the Integration Seams reference: `view_file plans/seams.md`

# WORKFLOW: REVIEW

**Objective:** Verify that a completed checkpoint's implementation matches its CRC behavioral contract and that all connectivity tests at its seams are green.

**Scope:** Single checkpoint. Do not review components outside the current checkpoint's boundaries.

**Position in chain:**

```
(sub-agents complete) -> [/io-review] -> /io-orchestrate (next batch) | /gap-analysis (full system)
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

### Step C: LOAD BEHAVIORAL ANCHORS

- **Action:** Read the CRC card for each component in scope from `plans/project-spec.md`.
- **Action:** Read the Protocol contract for each component from `interfaces/*.pyi`.
- **Goal:** Establish the behavioral intent before reading implementation.

---

### Step D: STRUCTURAL PRE-SCAN

For each implementation file in the checkpoint's write targets:

- Run `uv run python .agent/scripts/extract_structure.py <file>` — map public surface area
- Run `uv run rtk lint-imports` — verify layer compliance
- Run `uv run python .agent/scripts/check_di_compliance.py` — verify DI compliance
- Run `uv run rtk mypy <file>` — verify type correctness
- Run `uv run python .claude/skills/symbol-tracer/scripts/symbol_tracer.py --symbol "<Symbol1>,<Symbol2>" --root src/ --summary` — verify Protocol is consumed
- **Interface Registry check:** For each write target under `src/`, verify the file path (or its parent component) appears in the Interface Registry of `plans/project-spec.md`. A `src/` file absent from the registry is a HIGH finding: `UNREGISTERED_WRITE_TARGET` — route to `/io-architect` before the checkpoint can be considered approved. `tests/` files and tooling files outside `src/` are exempt.

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
- MEDIUM: Should fix — affects maintainability or contract completeness
- LOW: Nice to fix — minor improvement
- INFO: Observation only

---

### Step I: ROUTE FINDINGS

- **Action:** Run `/review-capture` to classify and log all HIGH and MEDIUM findings to `plans/review-output.md` (staging file).
- **Rule:** Findings not captured in staging are invisible to subsequent workflows. This step is mandatory if any HIGH or MEDIUM findings exist. Findings flow from staging to `plans/backlog.md` via `/io-backlog-triage`.

---

### Step J: CHECKPOINT APPROVAL DECISION

Present to the human:

```
REVIEW COMPLETE: [CP-ID]

Gate: PASS/FAIL
Connectivity tests: [N/N]
Findings: [N HIGH], [N MEDIUM], [N LOW]

Options:
1. Approve checkpoint — proceed to /io-orchestrate for next batch
2. Route findings to backlog — re-execute checkpoint after remediation
3. Escalate to /io-architect — finding reveals a design gap
```

- **Human decides.** Do not auto-approve.
- **If option 1 selected:** Run `bash .claude/scripts/archive-approved.sh [CP-ID]` — this flips the status in `plan.md` to `[x] complete`, moves task artifacts to `plans/archive/[CP-ID]/`, and for remediation checkpoints automatically marks all corresponding backlog items as `[x]` with a `Remediated:` annotation.

---

## 3. CONSTRAINTS

- Scope is strictly limited to the current checkpoint's components
- Do not review components from other checkpoints even if they appear in the same files
- Do not make fixes — output findings only (exception: `plans/seams.md` is updated in Step F to stay in sync with implementation)
- Do not route findings to `plans/plan.md` — backlog goes to `plans/backlog.md` only
- No git operations

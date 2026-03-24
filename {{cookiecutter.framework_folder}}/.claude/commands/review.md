---
name: review
description: Per-checkpoint behavioral review and connectivity verification. Findings route to backlog.md.
---

> **[NO PLAN MODE]**
> Read-only analysis. No file writes except via /review-capture at the end.

> **[CRITICAL] CONTEXT LOADING**
>
> 1. Load planning rules: `view_file .claude/rules/planning.md`
> 2. Load the checkpoint being reviewed from `plans/plan.md`
> 3. Load CRC cards for checkpoint components from `plans/project-spec.md`
> 4. Load relevant Protocol contracts from `interfaces/*.pyi`

# WORKFLOW: REVIEW

**Objective:** Verify that a completed checkpoint's implementation matches its CRC behavioral contract and that all connectivity tests at its seams are green.

**Scope:** Single checkpoint. Do not review components outside the current checkpoint's boundaries.

**Position in chain:**

```
(sub-agents complete) -> [/review] -> /io-orchestrate (next batch) | /gap-analysis (full system)
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

- **Action:** For each connectivity test listed in `plans/plan.md` at this checkpoint's output seams, run the gate command.
- **Rule:** Every connectivity test must be green before this checkpoint is considered approved.
- **Output:** For each CT: "CT-[NNN]: [PASS/FAIL] — [test file::function]"

---

### Step C: LOAD BEHAVIORAL ANCHORS

- **Action:** Read the CRC card for each component in scope from `plans/project-spec.md`.
- **Action:** Read the Protocol contract for each component from `interfaces/*.pyi`.
- **Goal:** Establish the behavioral intent before reading implementation.

---

### Step D: STRUCTURAL PRE-SCAN

For each implementation file in the checkpoint's write targets:

- Run `uv run python .claude/scripts/extract_structure.py <file>` — map public surface area
- Run `uv run rtk lint-imports` — verify layer compliance
- Run `uv run python .claude/scripts/check_di_compliance.py` — verify DI compliance
- Run `uv run mypy <file>` — verify type correctness

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

### Step F: CORRECTNESS REVIEW

- Logic errors, edge cases not covered by tests
- Error handling — are failure modes handled or silently swallowed?
- Type correctness beyond what mypy catches (semantic type misuse)
- Test quality — do tests assert meaningful behavior, or just "does not raise"?

---

### Step G: OUTPUT FINDINGS

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

### Step H: ROUTE FINDINGS

- **Action:** Run `/review-capture` to classify and log all HIGH and MEDIUM findings to `plans/backlog.md`.
- **Rule:** Findings not captured in `backlog.md` are invisible to subsequent workflows. This step is mandatory if any HIGH or MEDIUM findings exist.

---

### Step I: CHECKPOINT APPROVAL DECISION

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

---

## 3. CONSTRAINTS

- Scope is strictly limited to the current checkpoint's components
- Do not review components from other checkpoints even if they appear in the same files
- Do not make fixes — output findings only
- Do not route findings to `plans/plan.md` — backlog goes to `plans/backlog.md` only
- No git operations

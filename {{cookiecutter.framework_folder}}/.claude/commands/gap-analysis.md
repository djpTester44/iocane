---
name: gap-analysis
description: Full-system integration correctness analysis after all checkpoints complete. Findings route to backlog.yaml.
---

> **[NO PLAN MODE]**
> Read-only analysis. No file writes except via /review-capture at the end.

> **[CRITICAL] CONTEXT LOADING**
>
> 1. Load planning rules: `view_file .claude/rules/planning.md`
> 2. Load the component registry: `view_file plans/component-contracts.toml`
> 3. Load the Architecture Spec: `view_file plans/project-spec.md`
> 4. Load all contracts: `view_file interfaces/*.pyi`

# WORKFLOW: GAP ANALYSIS

**Objective:** Verify integration correctness across the entire codebase after all checkpoints in a feature (or full project) are complete. Confirm all contracts are satisfied, all connectivity tests are green, and no architectural drift has occurred.

**Scope:** Full system — all components in the Interface Registry.

**Position in chain:**

```
/io-review (all checkpoints) -> [/gap-analysis] -> /doc-sync
```

---

## 1. STATE INITIALIZATION

Before proceeding, output:

- **Scope:** [Feature F-XX / Full project]
- **Checkpoints covered:** [list from plan.yaml with PASS/FAIL status]
- **Interface Registry entries:** [N components]
- **Connectivity tests defined:** [N total in plan.yaml]

---

## 2. PROCEDURE

### Step A: ALL-GATES VERIFICATION

- **Action:** For every checkpoint in `plans/plan.yaml`, verify `tasks/[CP-ID].status` is `PASS`.
- **Action:** Run every connectivity test gate command listed in `plans/plan.yaml`.
- **Output:** Full pass/fail table.

If any checkpoint gate or connectivity test is failing, output a warning and continue — do not halt. Surface all failures in the findings report.

---

### Step B: CONTRACT SATISFACTION AUDIT

For every entry in `plans/component-contracts.toml` (use the `file` field for the component->implementation mapping):

- **Action:** Run `uv run python .claude/scripts/extract_structure.py <implementation_file>` to map the public surface area.

- **Check:** Does the implementation surface match the Protocol signature exactly?
  - Missing methods → HIGH finding
  - Signature mismatch (wrong types, wrong return) → HIGH finding
  - Extra public methods not in Protocol → MEDIUM finding (scope creep)

- **Check:** Run `uv run python .claude/scripts/extract_structure.py` to verify CRC-to-Protocol alignment.

---

### Step C: COMPLIANCE AUDIT

- **Action:** Run `bash .claude/scripts/run-compliance.sh src/` — ruff, mypy, lint-imports, bandit, DI check.
- **Output:** Any failures as findings (layer violations → HIGH, DI violations → HIGH, type errors → MEDIUM).
- **Check:** Review `ignore_imports` list in `pyproject.toml`. Are all tracked deferrals still justified? Flag any that appear resolvable.
- **Check:** Any untracked `# noqa: DI` suppressions → HIGH finding.

---

### Step F: INTEGRATION CORRECTNESS

Verify cross-component wiring:

- Do components that depend on each other (per CRC Collaborators) actually use the correct Protocol-typed injection?
- Are there any concrete class imports in non-entrypoint layers (should only be Protocol names)?
- Are there any circular dependencies not already in `ignore_imports`?

---

### Step G: OUTPUT FINDINGS REPORT

```markdown
## Gap Analysis Report

**Scope:** [Feature / Full project]
**Date:** [YYYY-MM-DD]

### Summary
[One paragraph overall integration health assessment]

### Gate Status
| Checkpoint | Gate | Connectivity Tests |
|------------|------|--------------------|
| CP-01 | PASS/FAIL | N/N passing |

### Findings

| Severity | Component | Issue | Recommendation |
|----------|-----------|-------|----------------|
| HIGH | [ComponentName] | [issue] | [fix] |

### Contract Coverage
- Interface Registry entries: [N]
- Fully satisfied: [N]
- Gaps: [N]

### Architectural Health
- Layer violations: [N]
- DI violations: [N]
- Untracked suppressions: [N]
```

---

### Step H: ROUTE FINDINGS

- **Action:** Run `/review-capture` to classify and log all HIGH and MEDIUM findings to `plans/backlog.yaml`.
- **Rule:** Findings not in `backlog.yaml` are invisible to subsequent planning. This step is mandatory if any findings exist.

---

### Step I: OUTPUT

```
GAP ANALYSIS COMPLETE.

Contracts satisfied: [N/N]
Connectivity tests: [N/N passing]
Findings routed to backlog.yaml: [N]

Next step: Run /doc-sync to reconcile project-spec.md and roadmap.md with current codebase state.
```

---

## 3. CONSTRAINTS

- Read-only — no fixes, no file writes beyond `/review-capture`
- Findings route to `plans/backlog.yaml` only — never to `plans/plan.yaml` or `plans/roadmap.md`
- Do not modify `interfaces/*.pyi` — if a contract gap is found, it goes to backlog as a `[DESIGN]` item
- No git operations

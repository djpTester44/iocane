---
name: auto-checkpoint
description: Auto-generate remediation checkpoints from triage-approved routing prompts. Tier 2.
---

> **[NO PLAN MODE]**
> Tier 2 autonomous workflow. No human approval required between steps.

> **[CONTEXT]** Before starting, read `plans/backlog.md` to understand which
> items carry routing prompts. The backing script handles parsing, but Claude
> needs backlog context for Step B verification and Step D output.

# WORKFLOW: AUTO-CHECKPOINT

**Objective:** Parse open backlog items with embedded `/io-checkpoint` routing prompts,
apply the 7-criterion eligibility filter, and atomically append new remediation
checkpoints to `plans/plan.md`.

**Position in chain:**

```
/io-backlog-triage (routing prompts written) -> /auto-architect (DESIGN/REFACTOR) -> [/auto-checkpoint] -> /validate-plan -> /io-plan-batch
```

---

## STATE INITIALIZATION

Load:
- `.claude/scripts/auto_checkpoint.py` must exist (the backing script)
- `plans/backlog.md` must contain triage-approved items with routing annotations
- `plans/plan.md` must exist and contain a `## Connectivity Tests` section (insertion anchor)

Pre-check: If `plans/plan.md` does not exist or lacks the `## Connectivity Tests` marker, **HALT** -- the plan has not been through `/io-checkpoint` yet.

---

## PROCEDURE

### Step 0: [HARD GATE] PRE-INVOCATION CHECK

Run:

```bash
bash .claude/scripts/pre-invoke-auto-checkpoint.sh
```

**If exit non-zero:** HALT immediately. The gate output names the missing precondition.

---

### Step A: [HARD GATE] RUN AUTO-CHECKPOINT SCRIPT

Run:

```bash
uv run python .claude/scripts/auto_checkpoint.py [--repo-root PATH]
```

| Exit | Condition | Action |
|------|-----------|--------|
| 0 | Checkpoints generated | Proceed to Step B |
| 0 | Zero eligible items | Inform user (all items already have CPs, are blocked, or ineligible). **HALT.** |
| 1 | Missing file or `## Connectivity Tests` anchor | Report error output. **HALT.** |
| 1 | Unresolvable field (feature, gate, write targets) | Report which CP failed and why. **HALT.** |

---

### Step B: [HARD GATE] VERIFY SUMMARY OUTPUT

Display the summary table from the script's stdout output. The table lists each
generated checkpoint with its CP ID, source BL IDs, severity, and title.

Verify the table contains at least one row. Each row must show: CP ID, source BL IDs, severity, and title.

**If zero rows:** Same as Step A zero-eligible-items path. **HALT.**
**If any row is missing a required column:** Report malformed output. **HALT.**

---

### Step C: [HARD GATE] VALIDATE PLAN

Run `/validate-plan`.

**If PASS:** Proceed to Step D.

**If FAIL:** **HALT.** Report that entries remain in `plans/plan.md` for inspection.
The human should review the validation failures and correct manually.

---

### Step D: OUTPUT

```
AUTO-CHECKPOINT COMPLETE. N checkpoints written. Plan validated: PASS.
Next: /io-plan-batch
```

---

## CONSTRAINTS

- Appends to `plans/plan.md` and writes `Routed:` annotations to `plans/backlog.md` (via `route-backlog-item.sh`)
- Does not modify `interfaces/*.pyi` — remediation CPs never change contracts
- Does not run `/io-plan-batch` or dispatch sub-agents
- Does not replace `/io-checkpoint` — that workflow remains available for manual use
- Idempotent — the 7-criterion filter (criterion 6) checks whether the target CP already exists in `plan.md`; a second run with the same backlog state produces zero new entries
- Backlog routing is non-fatal — if `route-backlog-item.sh` fails for a BL item (e.g., already routed), the CP is still written; a warning is logged for manual follow-up

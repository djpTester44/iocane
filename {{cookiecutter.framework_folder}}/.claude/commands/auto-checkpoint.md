---
name: auto-checkpoint
description: Auto-generate remediation checkpoints from triage-approved routing prompts. Tier 2.
---

> **[NO PLAN MODE]**
> Tier 2 autonomous workflow. No human approval required between steps.

# WORKFLOW: AUTO-CHECKPOINT

**Objective:** Parse open backlog items with embedded `/io-checkpoint` routing prompts,
apply the 7-criterion eligibility filter, and atomically append new remediation
checkpoints to `plans/plan.md`.

**Position in chain:**

```
/io-backlog-triage (routing prompts written) -> [/auto-checkpoint] -> /validate-plan -> /io-plan-batch
```

---

## PROCEDURE

### Step A: RUN AUTO-CHECKPOINT SCRIPT

Run:

```bash
uv run python .claude/scripts/auto_checkpoint.py
```

**If exit 0 with zero checkpoints:** Inform the user that no eligible items were found
(all items either already have CPs, are blocked, or are ineligible). **HALT.**

**If exit non-zero:** Report the error output. **HALT.**

---

### Step B: DISPLAY SUMMARY

Display the summary table from the script's stdout output. The table lists each
generated checkpoint with its CP ID, source BL IDs, severity, and title.

---

### Step C: VALIDATE PLAN

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

- Does not modify `plans/backlog.md` — only appends to `plans/plan.md`
- Does not modify `interfaces/*.pyi` — remediation CPs never change contracts
- Does not run `/io-plan-batch` or dispatch sub-agents
- Does not replace `/io-checkpoint` — that workflow remains available for manual use
- Idempotent — running twice produces zero new entries on the second run

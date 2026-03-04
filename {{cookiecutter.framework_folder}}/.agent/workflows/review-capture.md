---
description: Capture /review findings into plans/PLAN.md Remediation Backlog with routing tags.
---

# WORKFLOW: REVIEW CAPTURE

**Objective:** Classify findings from the most recent `/review` and append them to the `## 3. Remediation Backlog` section of `plans/PLAN.md` with routing tags that drive subsequent workflow decisions.

**Trigger:** Run immediately after `/review` completes.

**Procedure:**

1. **LOAD CONTEXT:**
    * Read `plans/PLAN.md` to locate the `## 3. Remediation Backlog` section (create it if absent).
    * Identify the source checkpoint and review date for attribution.

2. **CLASSIFY EACH FINDING:**
    > **[HARD] Private Method Gate:** If a finding references a `_`-prefixed method, DROP it entirely. Private methods are internal implementation details and must never receive `[DESIGN]` or `[REFACTOR]` tags. Do not append them to the backlog.

    Assign exactly one routing tag per finding according to the definitions and decision tree in `.agent/rules/ticket-taxonomy.md`.

3. **APPEND TO PLAN.MD:**
    For each finding, append a structured entry to `## 3. Remediation Backlog`:

    ```markdown
    - [ ] **[TAG]** `file.py`: <one-line description of the fix required>.
      - Source: <CP_ID> /review · <YYYY-MM-DD>
      - Severity: <HIGH | MEDIUM | LOW | INFO>
    ```

    ```

    * Group entries by tag (`[DESIGN]` first, then `[REFACTOR]`, then `[CLEANUP]`, then `[DEFERRED]`).
    * Do NOT modify any other section of `PLAN.md`.

4. **OUTPUT:**
    * Print a summary table of items added, grouped by tag.
    * Output: "BACKLOG UPDATED. If `[DESIGN]` or `[REFACTOR]` items were added, run `/io-architect` first. Otherwise run `/io-handoff` to build the execution bundle."
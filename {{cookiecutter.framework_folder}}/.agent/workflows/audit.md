---
description: Deep analysis of security posture and architectural health.
---

> **[CRITICAL] CONTEXT LOADING**
> 1. Load the planning rules: `view_file .agent/rules/planning.md`
> 2. Load the Architecture Spec: `view_file plans/project-spec.md`

# WORKFLOW: SECURITY & ARCHITECTURE AUDIT

## 1. STATE INITIALIZATION
Before scanning, you must output the following metadata:
- **Audit Target:** [Full Codebase OR Subsystem Path]
- **Primary Focus:** [Security / Architecture / Both]
- **Design Baseline:** [Confirmation that project-spec.md is loaded]

---

## 2. PROCEDURE
1. **SECURITY ANALYSIS:** Check against OWASP Top 10.
    * **Injection/Auth:** Scan for raw SQL, hardcoded credentials, or weak auth patterns.
    * **Data Exposure:** Verify sensitive data is not logged or exposed in errors.
    * **Python Pitfalls:** Check for `pickle`, `yaml.load` (without SafeLoader), and subprocess shell execution.
2. **ARCHITECTURE ANALYSIS:**
    * **Macro Audit:** Run `uv run lint-imports` to verify Layered Architecture compliance.
    * **Anchor Verification:** Run `uv run python .agent/scripts/check_design_anchors.py` to find Unanchored Protocols.
    * **DI Compliance:** Run `uv run python .agent/scripts/check_di_compliance.py` to detect God Objects.
3. **REPORT GENERATION:** Generate an Audit Report including:
    * **Executive Summary:** Overall health score.
    * **Findings Tables:** Security and Architecture risks categorized by severity.
    * **Remediation Plan:** Prioritized immediate/short-term/long-term actions.

## 3. ROUTING
- **Action:** Append all High/Medium findings to `plans/backlog.md` using the `[DESIGN]` or `[REFACTOR]` tags.
- **Output:** "AUDIT COMPLETE. Review findings in the Remediation Backlog."

4. **REPORT & INTERACTIVE CAPTURE:**
   * **Action:** Generate an Audit Report including Executive Summary, Security Findings, and Architecture Health.
   * **User Decision:** Present findings with a prompt: "Which of these architectural or security risks should be prioritized? Please list the items you'd like me to send to `/review-capture` to update the `PLAN.md` backlog."
   * **Logic:**
       * **If Selected:** Execute `/review-capture` for chosen items.
   * **Tagging:** Suggest the appropriate Routing Tag (`[DESIGN]`, `[REFACTOR]`, or `[CLEANUP]`) according to the definitions in `.agent/rules/ticket-taxonomy.md`.
   * **Constraint:** Never recommend implementation tasks directly; all work must be "pulled" from the backlog via `/io-plan-batch`.
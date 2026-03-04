---
description: Systematic code review with structured output against Design Anchors and Contracts.
---

> **[CRITICAL] CONTEXT LOADING**
> Load the analysis constraints:
> `view_file .agent/rules/planning.md`

# WORKFLOW: CODE REVIEW

**Objective:** Systematic code review verifying that code matches both the Structural Contract (`.pyi`) and Behavioral Design (`CRC`).

**Context:**
* Scope: Single module, file, or feature area
* Output: Findings table with actionable recommendations

**Procedure:**
1. **IDENTIFY SCOPE:** Ask if not clear - which files/modules to review? Any specific concerns (performance, security, readability)?
2. **LOAD ANCHORS:**
    * Read the **Protocol** (`interfaces/*.pyi`) to establish the Contract.
    * Read the **CRC Card** in `plans/project-spec.md` to establish the Intent.
3.  **ANALYZE CODE:** For each file in scope:
    * **Pre-Scan (Structure):** Run `uv run python .agent/scripts/extract_structure.py <file>` to map the surface area (methods/classes).
    * **Pre-Scan (Coupling):** Run `uv run lint-imports` to see incoming/outgoing dependencies and contract compliance.
    * **Pre-Scan (DI):** Run `uv run python .agent/scripts/check_di_compliance.py` to verify collaborators are injected, not instantiated. Cross-reference any `[WARNING]` findings against the CRC before classifying as implementation errors -- if implementation matches the CRC, tag as `[DESIGN]` gap.
    * **Behavior (Crucial):** Does the internal logic match the **Responsibilities** and **Collaborators** defined in the CRC?
        * *Flag:* Side effects not in CRC.
        * *Flag:* Logic that contradicts the Sequence Diagram.
    * **Correctness:** Logic errors, edge cases, error handling.
    * **Types:** Full hints, proper generics, adherence to Protocol signature.
    * **Style:** Naming, docstrings, line length, imports.
    * **SOLID:** Single responsibility, interface segregation.
    * **DRY:** Duplicated logic, extraction opportunities.
    * **Security:** Input validation, injection risks, secrets.
    * **Tests:** Coverage, edge cases, assertions.
4.  **OUTPUT FINDINGS:** Generate Code Review report with: Summary (one paragraph assessment), Findings table (Severity/Location/Issue/Recommendation), Strengths (what's done well), Action Items (specific fixes needed as checkboxes).

5.  **CAPTURE FINDINGS:** Run `/review-capture` to classify and log all findings to `plans/PLAN.md ## 3. Remediation Backlog`. This is mandatory findings not captured in PLAN.md are invisible to subsequent planning workflows.

**Severity Guide:**
* HIGH: **Unanchored Behavior** (Contradicts CRC), Bug, security issue.
* MEDIUM: Should fix, affects maintainability.
* LOW: Nice to fix, minor improvement.
* INFO: Observation, optional suggestion.

**Skills:**
* `security-warden`: Check for vulnerabilities
* `context-auditor`: Check architectural compliance
* `refactor-guru`: Identify SOLID/DRY violations

**Rules:**
* No automatic fixes - output findings, user decides what to fix.
* No PR submission - review only, no git operations.
* No scope creep - stay within requested review area.
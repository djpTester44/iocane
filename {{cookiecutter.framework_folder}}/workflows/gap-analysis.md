---
description: Identify gaps between requirements, behavioral design (CRC), contracts, and implementation.
---

> **[CRITICAL] CONTEXT LOADING**
> 1. Load the planning rules: `view_file .agent/rules/planning.md`
> 2. Load the Design Skill (Gap Analysis Rules): `view_file .agent/skills/mini-spec/SKILL.md`

# WORKFLOW: GAP ANALYSIS

**Objective:** Identify gaps between requirements, behavioral design (CRC), defined contracts, and actual implementations.

**Context:**
* Input: `plans/PLAN.md` (Requirements), `plans/project-spec.md` (Design/CRC), `interfaces/*.pyi` (Contracts)
* Output: Gap Analysis Report with prioritized action items

**Procedure:**

1. **READ REQUIREMENTS:**
   * Parse `plans/PLAN.md` for goals, milestones, feature requirements, and non-functional requirements.

2. **READ DESIGN (Behavioral Anchor):**
   * Parse `plans/project-spec.md`.
   * Extract **Component Specifications (CRC)** and **Sequence Diagrams**.
   * *Goal:* Understand the intended behavior and collaborators for each component.

3.  **READ CONTRACTS:**
    * Scan `interfaces/*.pyi`.
    * Verify that every CRC Responsibility maps to at least one Protocol method.
    * **[HARD] Private Method Exemption:** Private methods (`_`-prefixed) are internal implementation details and must NOT be expected in `.pyi` Protocols. Do not flag a missing Protocol for any `_`-prefixed method. Sequence Diagrams are exempt for data containers. *(See also: Step 5 private-method filter.)*
    * **Anchor Verification:** Run `uv run python .agent/scripts/check_design_anchors.py` to detect Unanchored Protocols (Protocols without a corresponding CRC card).
    * *Gap Type:* **"Missing Contract"** (CRC exists, but no Protocol method defines it).

4.  **SCAN IMPLEMENTATION:**
    * Identify the **Target Implementation** path for each component from the Interface Registry.
    * Check if the resolved file path sits strictly inside the `src/` boundary.
    * *Gap Type:* **"Missing Implementation"** (Registry entry exists, but file does not).

5.  **EXTRACT & COMPARE:**
    * For existing implementations, run `uv run python .agent/scripts/extract_structure.py <file>` to get a surgical view of the implementation skeleton.
    * **[CRITICAL] Filter Private Methods:** Before any comparison, remove all `_`-prefixed methods (single or double underscore) from the extracted skeleton. Private methods are internal implementation details and are **strictly exempt** from CRC Key Responsibilities and `.pyi` Protocol anchors. Only public methods (no leading underscore) participate in the comparison.
    * **Action:** Compare the **filtered** (public-only) signatures against the CRC Responsibilities.
    * **Apply Skill Rules (.agent/skills/mini-spec/SKILL.md):**
        * *Gap Type:* **"Unanchored Code"** -> A **public** method exists in skeleton but is NOT defined in CRC. (Action: Add to Design OR Remove from Code).
            > **[!CAUTION] Negative Example -- Do NOT Flag Private Methods**
            > A private helper such as `_wire_strategies_from_config` must NEVER be reported as "Unanchored Code". It is an internal implementation detail, not a public contract. If it appears in the skeleton, it should have been filtered out in the previous step.
        * *Gap Type:* **"Missing Implementation"** -> Responsibility listed in CRC but NOT found in skeleton. (Action: Implement it).
    * **DI Compliance Check:**
        * Run `uv run python .agent/scripts/check_di_compliance.py`.
        * Review `[CRITICAL]` findings (internal instantiation of collaborators, untracked `# noqa: DI` technical debt, or `src/` layout boundary violations).
        * Review `[WARNING]` findings (missing injection args). These now yield non-zero exit codes and represent hard structural gaps where collaborators are completely unresolvable.
        * **CRC Arbitration:** Cross-reference each finding against the CRC. If implementation matches the CRC, classify as a `[DESIGN]` gap (CRC self-contradiction), not an implementation error.

6.  **REPORT & INTERACTIVE CAPTURE:**
    * **Action:** Generate a Gap Analysis Report categorized by:
        * **Structural Gaps:** Missing Protocols/Files or layout boundary violations.
        * **Behavioral Gaps:** Logic missing from CRC Responsibilities.
        * **Compliance Gaps:** DI violations, untracked escape hatches, or unresolvable collaborators.
    * **User Decision:** Ask: "Which of these gaps should be added to the Remediation Backlog? Please list the items you'd like me to send to `/review-capture`."
    * **Logic (Upon Selection):**
        * Invoke `/review-capture` only for the selected items.
        * The agent must then suggest the appropriate Routing Tag (`[DESIGN]`, `[REFACTOR]`, or `[CLEANUP]`) for the backlog entry according to `.agent/rules/ticket-taxonomy.md`.
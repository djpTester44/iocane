---
description: Validate an implementation plan against CDD principles (CRC-Protocol symmetry) before execution.
---

> **[CRITICAL] CONTEXT LOADING**
> Load the analysis constraints:
> `view_file .agent/rules/planning.md`
> `view_file .agent/rules/execution.md`

# WORKFLOW: PLAN REVIEW (CDD Compliance)

**Objective:** Pre-execution validation that an implementation plan maintains CRC-Protocol symmetry and follows the Design Before Contract rule without requiring granular execution details.

**Context:**

* Scope: One implementation plan document
* Output: Findings table with actionable recommendations
* Trigger: Iterative pre-entry gate. Run before entering the canonical chain (`/io-architect` -> `/io-handoff` -> ...) to catch design violations early. Iterate until PASS.

**Procedure:**

1. **IDENTIFY SCOPE:** Load the implementation plan under review.

2. **EXTRACT PLAN ITEMS:** For each proposed change, classify as one of:
    * **CRC change** (adding/modifying responsibilities in `project-spec.md`)
    * **Protocol change** (adding/modifying methods in `interfaces/*.pyi`)

3. **LOAD ANCHORS:** For every component referenced in the plan:
    * Read its **CRC Card** from `plans/project-spec.md`.
    * Read its **Protocol** from `interfaces/*.pyi`.
    * Read the **Interface Registry** to verify file path mappings.

4. **LOAD LAYER CONTRACTS:** Read `pyproject.toml` section `[tool.importlinter]` to understand:
    * Which packages are `root_packages`.
    * Iterate over **all** `[[tool.importlinter.contracts]]` entries (there may be several). For each, note:
      * `type = "independence"` -- these packages cannot import each other.
      * `type = "layers"` -- packages are ordered top-to-bottom; lower layers cannot import higher.
    * Use this to inform checks 5-9 below.

5. **CHECK: Private Method Gate**
    > **[HARD]** `_`-prefixed methods are internal implementation details.
    * If the plan proposes adding a `_`-prefixed method to a CRC card or `.pyi` Protocol, flag immediately.
    * **Flag:** Private method promoted to design anchor = `PRIVATE_METHOD_PROMOTION`.
    * Private methods are **correctly dismissible** as false positives in gap analysis.

6. **CHECK: CRC-Protocol Symmetry**
    * For every proposed Protocol addition/change, verify a corresponding CRC responsibility exists or is being added in the **same plan**.
    * For every proposed CRC addition, verify a corresponding Protocol method exists or is being added.
    * **Flag:** Protocol method with no CRC anchor = `UNANCHORED_CONTRACT`.
    * **Flag:** CRC responsibility with no Protocol method = `ORPHANED_DESIGN` (acceptable only for private helpers).

7. **CHECK: Atomicity**
    * CRC + Protocol changes for the **same component** must be grouped as atomic units.
    * **Flag:** CRC and Protocol for the same component listed in separate, ungrouped sections = `ATOMICITY_VIOLATION`.

8. **CHECK: Layer Boundary Compliance**
    * Using the contracts loaded in step 4, verify that any proposed new imports, collaborator injections, or file moves respect the layer and independence contracts.
    * **Flag:** Plan proposes `models` importing from `jobs` (or any lower-to-higher import) = `LAYER_VIOLATION`.
    * **Flag:** Plan proposes `lib` importing from `models` (or any cross-peer import in an independence contract) = `INDEPENDENCE_VIOLATION`.

9. **CHECK: DI Compliance Preview**
    * If the plan introduces a new collaborator, verify it is received via `__init__` parameter injection.
    * If the plan moves or creates instantiation logic, verify it lands in the Entrypoint layer (Layer 4) or a factory, not inside domain/service classes.
    * **Flag:** New collaborator instantiated inline = `HARDCODED_DEPENDENCY`.
    * **Flag:** `os.environ` / `os.getenv` used outside Entrypoint layer = `ENV_LEAK`.

10. **CHECK: False Positive Justification**
    * If the plan dismisses items as "no changes required", verify the justification.
    * Private methods (`_` prefix) are correctly dismissible.
    * **Flag:** Dismissed item that actually needs a change = `FALSE_DISMISSAL`.

11. **OUTPUT FINDINGS:** Generate a Plan Review report with:
    * **Summary:** One-paragraph assessment (PASS / FAIL with count).
    * **Findings Table:**

    | # | Check | Component | Finding | Severity | Auto-Remediable? |
    |---|-------|-----------|---------|----------|-----------------|
    | 1 | CRC-Protocol Symmetry | ... | ... | ... | Yes/No |

    * **Required Amendments:** Specific changes to the plan (as checkboxes).

12. **SELF-HEALING LOOP**:

    **Auto-Remediable Violations** (agent amends the plan directly):

    | Flag | Auto-Fix Action |
    |---|---|
    | `PRIVATE_METHOD_PROMOTION` | Remove the `_`-prefixed method from the plan's CRC/Protocol sections. |
    | `UNANCHORED_CONTRACT` | Add the missing CRC responsibility to the plan. |
    | `ORPHANED_DESIGN` | Add the missing Protocol method to the plan. |
    | `ATOMICITY_VIOLATION` | Regroup CRC + Protocol changes into the same component section. |
    | `FALSE_DISMISSAL` | Re-include the dismissed item in the plan. |

    **Non-Auto-Remediable Violations** (escalate to user immediately):

    | Flag | Why |
    |---|---|
    | `LAYER_VIOLATION` | Requires architectural judgment on import placement. |
    | `INDEPENDENCE_VIOLATION` | Requires architectural judgment on dependency direction. |
    | `HARDCODED_DEPENDENCY` | Needs human decision on DI wiring location. |
    | `ENV_LEAK` | Needs human decision on config injection approach. |

    **Loop Procedure:**
    1. If all VIOLATIONs are auto-remediable: amend the plan, mark each change with `[AUTO-AMENDED]`, and re-run checks 5-10.
    2. If any non-auto-remediable VIOLATION exists: stop immediately and escalate to user with the findings.
    3. After each pass, compare the violation set to the previous pass. If no new violations appear, the loop has converged — proceed to step 13.
    4. If the same violation recurs across two consecutive passes (auto-remediation did not resolve it): stop and escalate to the user.
    5. On success: proceed to step 13.

13. **STAMP RESULT:**

**Severity Guide:**

* **VIOLATION:** Blocks execution. Must be resolved (auto or manual) before proceeding.
* **OBSERVATION:** Should fix. Plan may proceed but risk of drift.
* **INFO:** Optional improvement. Does not block.

**Gate Behavior:**

* If all VIOLATIONs are auto-remediable, the agent fixes them and re-validates until no new violations appear, or escalates if the same violation recurs across two consecutive passes.
* If any non-auto-remediable VIOLATION exists, the plan **FAILS** and the user must intervene.
* Only a **PASS** result (zero VIOLATIONs) allows downstream execution.

**Gate Artifact:**

* On **PASS**, stamp the plan document with: `**Plan Validated:** PASS (YYYY-MM-DD)`
* On **FAIL**, stamp the plan document with: `**Plan Validated:** FAIL (YYYY-MM-DD)` and list the blocking violations.
* `/io-architect` **MUST** check for a `**Plan Validated:** PASS` marker in the plan before modifying any CRC or Protocol artifacts. If the marker is missing or shows FAIL, halt and recommend `/review-plan`.

**Self-Healing Log:**

* All auto-amendments must be logged in the plan under a `## Self-Healing Log` section.
* Each entry: `[AUTO-AMENDED] <iteration> | <flag> | <component> | <what was changed>`
* This log provides an audit trail for the user to review what the agent changed.

**Rules:**

* Auto-amend only the violations classified as auto-remediable above.
* Do not expand scope beyond what the plan proposes.
* Do not route findings to the Remediation Backlog -- this is a pre-execution gate, not a post-implementation review.
* Do not execute the plan. Amend and validate only.

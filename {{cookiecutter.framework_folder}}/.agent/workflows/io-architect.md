---
description: Transform Architecture Spec into concrete Protocol Interfaces (.pyi) and resolve design debt.
---

> **[CRITICAL] CONTEXT LOADING**
> 1. Load the planning rules: `view_file .agent/rules/planning.md`
> 2. Load the Design Skill (CRC/Sequence Format): `view_file .agent/skills/mini-spec/SKILL.md`
> 3. Load the Interface Template: `view_file .agent/templates/interface.pyi.template`
> 4. Load the Architecture Template: `view_file .agent/templates/project-spec.md`

# WORKFLOW: IOCANE ARCHITECT

**Objective:** Create the Contracts (Interfaces) defined in `plans/project-spec.md` for the current active Checkpoint or resolve pending architectural debt.

**Context Manifest:**
1.  `plans/project-spec.md` (The Blueprint & Living Document)
2.  `plans/PLAN.md` (Strategic Roadmap, Checkpoints, and Backlog)
3.  `plans/PRD.md` (Detailed Logic Requirements)
4.  `.agent/templates/interface.pyi.template` (Protocol Boilerplate)

**Procedure:**

0.  **[HARD GATE] PLAN VALIDATION ENTRY-GATE:**
    * **Action:** If an implementation plan exists, check that it contains `**Plan Validated:** PASS`. If the marker is missing or shows FAIL, halt and recommend `/review-plan`. This gate is skipped when `/io-architect` is invoked directly by the user without an implementation plan.

1.  **IDENTIFY ACTIVE TARGET (Debt First, then Sequential):**
    * **Action:** Read `plans/PLAN.md`.
    * **Logic (Priority 1):** Check `## 3. Remediation Backlog`. If any `[DESIGN]` or `[REFACTOR]` items are pending (not marked `[x]`), this is your active target. You must resolve the architectural debt before advancing.
    * **Logic (Priority 2):** If the relevant backlog is empty, identify the first Checkpoint (CP) that is **NOT** marked as "Complete".
    * **Focus:** Within the active target, identify the core Component that requires a Protocol definition or update.
    * **Constraint:** Do not ask the user. You must proceed strictly by this priority order.
    * **Output:** "Active Target: [Backlog Item OR CP_ID]. Target Component: [Component Name]."

2.  **DESIGN COMPONENT (Behavioral Anchor):**
    * **Source:** Read `.agent/skills/mini-spec/SKILL.md` to load the strict design patterns.
    * **Action:** Specific to the target component, generate a **CRC Card** and **Critical Sequence Diagram**.
    * **Constraint:** You MUST apply the **"CRC Card Standard"** (Section 2 of Skill) to define Responsibilities.
    * **Constraint:** You MUST apply the **"Sequence Diagram Standard"** (Section 3 of Skill) to lock down the execution flow.
    * **Update:** Append or update this design in the `Component Specifications` section in `plans/project-spec.md`.
    * **Rule:** Ensure the sequence explicitly handles edge cases and dependencies defined in `plans/PRD.md`.

3.  **UPDATE REGISTRY (Structural Anchor):**
    * Review the Interface Registry in `plans/project-spec.md`.
    * **Action:** Update the Registry to map the Component -> Protocol Name -> Target `.pyi` Path.
    * **Constraint:** The "Target Implementation" path MUST place the file in the correct layer as defined in the **Architecture Layer Mapping** section of `plans/project-spec.md` (e.g., Domain components in Layer 3, utilities in Layer 2).

4.  **[HARD] GENERATE PROTOCOLS (TyDD):**
    * Read the *just-generated* CRC/Sequence in `plans/project-spec.md`.
    * **Action:** Create or update `interfaces/<component>.pyi` by filling in the **Template** from `.agent/templates/interface.pyi.template`.
    * **Rules:**
        * **Strict Typing:** Ensure the `@runtime_checkable` decorator is preserved.
        * **Traceability:** Every method in the `.pyi` must directly support a Responsibility listed in the CRC.
        * **Docstrings:** Paste the specific logic from the CRC into the docstrings under `CRC Trace`.
        * **No Implementation:** Function bodies must be `...` (ellipsis).
        * **Full Output:** You must generate the entire `.pyi` file content. Never use placeholders or abbreviate the protocol.
        * **No `.py` edits:** You are strictly FORBIDDEN from editing implementation files (`.py`). Only `/io-loop` may modify implementation code.
    * **Action:** Create/Update `interfaces/models.pyi` with Pydantic models or TypedDicts if new domain primitives are introduced.
    * **Action:** Export the new Protocol in `interfaces/__init__.pyi`.

5.  **VERIFY:**
    * Run `uv run mypy interfaces/`.
    * Fix any signature or import errors immediately.

6.  **OUTPUT:**
    * Output: "STATE UPDATED. Design anchored in `project-spec.md`. Contracts signed in `interfaces/`. Run `/io-handoff` to build the execution bundle."
    * **Backlog Ticket Disposition:** Mark off or convert tickets according to the Gate Enforcement Rules in `.agent/rules/ticket-taxonomy.md`.
    * **Context Pointer Recovery:** If this workflow was triggered by an interruption (e.g., a hard gate during `/io-handoff`), explicitly restore the prior execution context pointer before the parent workflow resumes.
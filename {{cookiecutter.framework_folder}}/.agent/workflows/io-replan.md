---
description: Propagate PRD changes to PLAN.md and project-spec.md without destroying existing work.
---

> **[CRITICAL] CONTEXT LOADING**
> 1. Load the planning rules: `view_file .agent/rules/planning.md`
> 2. Load the Design Skill (CRC/Sequence Format): `view_file .agent/skills/mini-spec/SKILL.md`
> 3. Load the Architecture Template: `view_file .agent/templates/project-spec.md`

# WORKFLOW: IOCANE REPLAN

**Objective:** Propagate changes from an updated `plans/PRD.md` into `plans/PLAN.md` (Roadmap) and `plans/project-spec.md` (Architecture), preserving all completed work and routing necessary codebase changes to the Remediation Backlog.

**Context Manifest:**
1.  `plans/PRD.md` (Updated Source of Truth)
2.  `plans/PLAN.md` (Existing Roadmap -- to be updated)
3.  `plans/project-spec.md` (Existing Architecture -- to be updated)
4.  `interfaces/*.pyi` (Existing Contracts -- read-only in this workflow)

---

## Procedure

### 1. [CRITICAL] CLARIFICATION GATE

* **Action:** Read the doc header of `plans/PRD.md`.
* **Check:** Locate the `**Clarified:**` field.
* **Rule:** If the field is missing, or if it is set to `False`, you MUST immediately HALT execution.
* **Output:** "HALT: The PRD has not been clarified. You must run `/io-clarify` and resolve all new ambiguities before replanning can begin."

### 2. DIFF ANALYSIS (Requirements Delta)

* **Action:** Read `plans/PRD.md`, `plans/PLAN.md`, and `plans/project-spec.md` (Architecture Overview, Protocol Interfaces, Domain Models, and CRC sections).
* **Output:** Produce a structured **Change Report** with three categories:

| Category | Description |
|----------|-------------|
| **NEW** | Requirements, components, or data models in PRD that have no match in PLAN or Spec. |
| **MODIFIED** | Requirements that exist in PLAN/Spec but whose definition has changed. |
| **REMOVED** | Items in PLAN/Spec that are no longer referenced by the PRD. |

* **Constraint:** Present the Change Report to the user for confirmation before proceeding. 

### 3. UPDATE ROADMAP (`plans/PLAN.md`)

> **Permission:** Requires explicit user approval (user-owned strategic doc).

* **Action:** For **NEW** items, propose a new Checkpoint (or subtask).
* **Action:** For **REMOVED** items, propose marking the Checkpoint or deliverable as `[DEPRECATED]` with a note. Do not delete historical entries.
* **Action (Backlog Routing):** If a **MODIFIED** or **REMOVED** requirement corresponds to code that has *already been implemented*, you MUST append a specific ticket to the `## 3. Remediation Backlog` section according to the definitions in `.agent/rules/ticket-taxonomy.md`. This ensures the execution pipeline will safely modify or delete the orphaned code later.
* **Constraint:** Every new or modified deliverable MUST cite the PRD section it traces to (e.g., `(PRD 3.4)`). 

### 4. UPDATE ARCHITECTURE (`plans/project-spec.md`)

* **Action:** For **NEW** components, add rows to Protocol Interfaces/Domain Models, update the Mermaid graph, and generate a new **CRC Card** and **Sequence Diagram**.
* **Action:** For **MODIFIED** components, update the existing CRC Card responsibilities and Sequence Diagrams to match the new logic.
* **Action:** For **REMOVED** components, mark the Protocol Interfaces row as `[DEPRECATED]` and add `> [!WARNING] Deprecated by PRD vX.X` to the CRC Card. 
* **Constraint:** This workflow does NOT generate `.pyi` files.

### 5. VERIFY CONSISTENCY

* **Action:** Cross-check that every component referenced in `PLAN.md` has a matching entry in the `project-spec.md` Interface Registry.
* **Action:** Cross-check that every CRC Card maps to a Checkpoint. Flag orphans as warnings.

### 6. OUTPUT

* Output: `"REPLAN COMPLETE. plans/PLAN.md and plans/project-spec.md updated. Run /io-architect to update Protocol Interfaces (.pyi), or /io-handoff to process the Remediation Backlog."`
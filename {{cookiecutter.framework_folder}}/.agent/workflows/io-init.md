---
description: Bootstrap the project structure, Architecture Spec, and Roadmap from a clarified PRD.
---

> **[CRITICAL] CONTEXT LOADING**
> 1. Load the planning rules: `view_file .agent/rules/planning.md`
> 2. Load the Architecture Template: `view_file .agent/templates/project-spec.md`
> 3. Load the Roadmap Template: `view_file .agent/templates/PLAN.md`

# WORKFLOW: IOCANE INITIALIZATION

**Objective:** Transform a strictly clarified `plans/PRD.md` into the macro-architecture and strategic roadmap.

## 1. STATE INITIALIZATION
Before proceeding to Step 2, you must output the following metadata to confirm the project boundaries:
- **PRD Clarification Status:** [Must be `True` to proceed]
- **Root Directory Strategy:** [e.g., Strict `src` layout]
- **Layer 1 (Foundation):** [Target path, e.g., `src/core`]
- **Layer 3 (Domain):** [Target path, e.g., `src/domain`]

---

## 2. PROCEDURE

### Step A: [CRITICAL] CLARIFICATION GATE
* **Action:** Read the document header of `plans/PRD.md`.
* **Check:** Locate the `**Clarified:**` field.
* **Rule:** If the field is missing, or set to `False`, you MUST immediately HALT.
* **Output:** "HALT: The PRD has not been clarified. Run `/io-clarify` first."

### Step B: ANALYZE & MAP LAYERS
* **Action:** Read `plans/PRD.md` to identify the tech stack and constraints.
* **Action:** Finalize the directory mapping for this specific project:
    * **Layer 1 (Foundation):** Config, Types, and Primitives (Target: `src/core`).
    * **Layer 2 (Utility):** Stateless helpers and external clients (Target: `src/lib`).
    * **Layer 3 (Domain):** Core business logic and orchestrators (Target: `src/domain`).
    * **Layer 4 (Entrypoint):** CLI, API, or Jobs (Target: `src/main.py`).

### Step C: GENERATE ARCHITECTURE (`plans/project-spec.md`)
* **Action:** Create `plans/project-spec.md` using the template.
* **Sub-Step:** Define Configuration Schema and Domain Primitives.
* **Sub-Step:** Propose a Protocol mapping for every major component identified in the PRD.
* **Sub-Step:** Generate a Mermaid graph showing data flow between components.

### Step D: GENERATE ROADMAP (`plans/PLAN.md`)
* **Action:** Create `plans/PLAN.md` using the template.
* **Logic:** Break the PRD into logical, sequential Checkpoints (CPs).
* **Constraint:** High-level milestones only. Do not create atomic tasks here.
* **[CRITICAL]:** Initialize the `## 3. Remediation Backlog` section as empty.

---

## 3. OUTPUT
* Output: "BOOTSTRAP COMPLETE. Run `/io-architect` to begin the Design phase."
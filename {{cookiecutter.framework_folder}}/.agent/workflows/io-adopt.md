---
description: Apply Iocane framework to an existing codebase with intelligent content migration and design extraction.
---

> **[CRITICAL] CONTEXT LOADING**
> 1. Load the planning rules: `view_file .agent/rules/planning.md`
> 2. Load the extraction tool: `.agent/scripts/extract_structure.py`

# WORKFLOW: ADOPT EXISTING REPOSITORY

**Objective:** Extract the structural skeleton and reverse-engineer the capabilities of a legacy codebase to establish a foundational PRD.

**Context:**
* Scope: Legacy repository integration.
* Output: `plans/current-state.md` + draft `plans/PRD.md`.

**Procedure:**

### 1. CURRENT STATE ANALYSIS (Token Protection)
* **Constraint:** You are strictly forbidden from reading full legacy source files in bulk. 
* **Action:** Run `uv run python .agent/scripts/extract_structure.py <dir>` to map the existing classes, function signatures, and data structures.
* **Action:** Create `plans/current-state.md` using the template `.agent/templates/current-state.md`.
* **Goal:** Capture the raw capabilities and data structures of the legacy code efficiently.

### 2. REFACTOR PRD GENERATION
* **Action:** Read `.agent/templates/PRD.md`.
* **Action:** Create `plans/PRD.md` by mapping `plans/current-state.md` into the Iocane-compliant PRD format.
* **Goal:** Rephrase legacy capabilities as "Requirements" for the refactor.
* **Guidance:**
    * Map "Capabilities" -> "User Stories"
    * Map "Data Structures" -> "Domain Models"
    * Map "File Inventory" -> "Constraints"
* **Rule:** Set `**Clarified:** False` in the new PRD header.

### 3. HANDOFF
* **Stop:** Explicitly ask user to review `plans/PRD.md`.
* **Output:** "Legacy extraction complete. Draft PRD created at `plans/PRD.md`. **REVIEW REQUIRED.** Do not proceed until this PRD is approved. Once approved, run `/io-clarify` to resolve ambiguities, followed by `/io-init` to generate the macro-architecture."

**Safety Rules:**
* Never delete existing legacy files without approval.
* Do not hallucinate requirements not found in the extracted code skeleton.
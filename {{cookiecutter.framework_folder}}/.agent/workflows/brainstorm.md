---
description: Collaborative ideation for developing or amending a PRD. Optional utility — not part of the canonical chain.
---

# WORKFLOW: BRAINSTORM

**Purpose:** Structured ideation for two scenarios:

- **Pre-PRD:** Developing a new PRD before the canonical chain begins.
- **PRD Amendment:** Scoping a requirements change before `/io-replan`.

This workflow produces no implementation artifacts. Its output is either a ready-to-draft PRD, or a scoped amendment ready for `/io-clarify` → `/io-specify` (new project) or `/io-clarify` → `/io-replan` (amendment).

> **When the agent should suggest this workflow:**
>
> - The user describes a new capability that has no corresponding requirement in `plans/PRD.md`.
> - The user describes a change that would modify existing requirements or invalidate completed checkpoints.
> - A `/gap-analysis` or `/io-review` surfaces a pattern suggesting the PRD is incomplete or outdated.

---

## Procedure

### Step 1: DETECT CONTEXT

Determine which scenario applies without asking directly — infer from the conversation and project state:

- **No `plans/PRD.md` exists** → Pre-PRD mode.
- **`plans/PRD.md` exists and is `Clarified: True`** → PRD Amendment mode.
- **Ambiguous** → Ask: "Are we starting a new project idea, or adjusting the requirements for an existing one?"

Output: "Mode: [Pre-PRD | PRD Amendment]"

---

### Step 2: IDEATION

Engage collaboratively. Do not push toward artifacts yet.

**Ask and explore:**

- What capability or change is being considered?
- What problem does it solve? For whom?
- What constraints exist (technical, time, scope)?
- What are the unknowns or risks?

Drive toward specificity. Push back on vague goals with targeted questions. The output of this step is a clear, shared understanding of the idea — not a document.

**Rules:**

- No file writes in this step.
- No task creation, no Protocol sketches.
- No scope commitments yet.

---

### Step 3: IMPACT ASSESSMENT

Assess what the idea implies for the existing project state.

**Pre-PRD:** Identify the core functional requirements, domain models, and constraints the idea implies. Flag any areas of ambiguity that would block `/io-clarify`.

**PRD Amendment:**

- Read `plans/PRD.md` and `plans/roadmap.md`.
- Identify which existing features are affected (modified, removed, or superseded).
- Identify which completed checkpoints would be invalidated.
- Flag any `[DESIGN]` or `[REFACTOR]` backlog items the change would generate.

Output a concise **Impact Summary**:

```
## Impact Summary

### What changes
- [Requirement or capability being added/modified/removed]

### What is affected
- [Features, checkpoints, or contracts touched]

### Open questions
- [Ambiguities that must be resolved before proceeding]
```

---

### Step 4: PRESENT AND CONFIRM

Present the Impact Summary to the user. Ask:

> "Does this capture what you're aiming for? Any corrections before we proceed?"

Do not proceed until the user confirms. Adjust and re-present if needed.

---

### Step 5: ROUTE

Based on the confirmed Impact Summary:

**Pre-PRD:**
> "Ready to draft `plans/PRD.md`. Run `/io-clarify` after drafting to resolve any remaining ambiguities, then `/io-specify` to generate `roadmap.md` and begin the architecture phase."

**PRD Amendment:**
> "Scope confirmed. Update `plans/PRD.md` to reflect these changes, then run `/io-clarify` to resolve open questions, followed by `/io-replan` to propagate the changes to `roadmap.md` and `project-spec.md`."

**Rules:**

- Do not draft the PRD or edit any files in this workflow.
- Do not invoke `/io-clarify`, `/io-specify`, or `/io-replan` — instruct the user to do so.
- No task creation, no backlog entries.

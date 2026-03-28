---
name: io-specify
description: Generate the capability roadmap from a clarified PRD. Tier 1 — plan mode required.
---

> **[CRITICAL] PLAN MODE**
> This workflow runs in plan mode. Claude PROPOSES `roadmap.md` content before writing anything.
> Nothing is committed until the human explicitly approves.

> **[CRITICAL] CONTEXT LOADING**
> 1. Load planning rules: `view_file .claude/rules/planning.md`
> 2. Load the PRD: `view_file plans/PRD.md`

# WORKFLOW: IO-SPECIFY

**Objective:** Transform a clarified `plans/PRD.md` into a dependency-ordered capability roadmap (`plans/roadmap.md`). This is the first Tier 1 gate after PRD clarification.

**Position in chain:**
```
/io-clarify -> [/io-specify] -> /io-architect -> /io-checkpoint -> /io-plan-batch -> dispatch-agents.sh
```

---

## 1. STATE INITIALIZATION

Before proceeding, output the following metadata:

- **PRD Clarification Status:** [Must be `True` to proceed]
- **Feature Count (estimated):** [Number of top-level capabilities identified in PRD]
- **Known Hard Dependencies:** [Any features that are obviously sequenced]

---

## 2. PROCEDURE

### Step A: [CRITICAL] CLARIFICATION GATE

* **Action:** Read the document header of `plans/PRD.md`.
* **Check:** Locate the `**Clarified:**` field.
* **Rule:** If missing or `False`, HALT immediately.
* **Output:** "HALT: PRD has not been clarified. Run `/io-clarify` first."

---

### Step B: ANALYZE PRD FOR CAPABILITIES

* **Action:** Read `plans/PRD.md` in full.
* **Goal:** Identify every distinct user-facing capability.
* **Distinction:** A capability is something a user can do or observe — not an implementation detail.
  * **YES:** "User can authenticate via OAuth", "System processes payments"
  * **NO:** "Implement JWT middleware", "Add Redis cache"
* **Output:** Enumerate capabilities as a flat list with one-line descriptions.
* **Brownfield verification:** If `plans/current-state.md` exists, scan each capability for claims about existing behavior. Verify each claim against source cited in `current-state.md`. Tag unconfirmed claims as `[UNVERIFIED]`; these must not be treated as dependencies in Step C.

---

### Step C: [PLAN MODE] BUILD DEPENDENCY MAP

* **Goal:** Determine which capabilities depend on others being complete first.
* **Method:** For each capability pair, ask: "Can B be built and tested independently before A exists?"
  * If no → A must precede B.
  * If yes → B is independent or can be parallel.
* **Output:** A dependency graph expressed as a simple ordered list with `depends_on` annotations.

**Do not write any file yet.** Present the dependency map to the human for review.

---

### Step D: [PLAN MODE] PROPOSE ROADMAP.MD

Propose the full content of `plans/roadmap.md` using this format:

```markdown
# Roadmap

**Generated from:** plans/PRD.md
**Status:** Draft — awaiting human approval

---

## Features

### F-01: [Feature Name]
**Description:** [One sentence — what the user can do when this is complete]
**Depends on:** none | [F-XX, F-YY]
**PRD reference:** [Section or requirement ID]
**Acceptance criteria:**
- [ ] [Testable, observable outcome]
- [ ] [Testable, observable outcome]

### F-02: [Feature Name]
...
```

**Rules for roadmap entries:**
- Every feature must have at least one testable acceptance criterion.
- Acceptance criteria must be observable at the system boundary — no internal implementation details.
- `depends_on` must be explicit. If a feature truly has no dependencies, write `none`.
- PRD reference is mandatory — every feature must trace to a PRD requirement.

**Present the full proposed `roadmap.md` to the human. Do not write the file.**

Output: "PROPOSAL READY. Review the roadmap above. Reply with approval to write, or provide corrections."

---

### Step E: [HUMAN GATE] APPROVAL REQUIRED

* **WAIT** for explicit human approval before writing.
* If corrections requested: revise the proposal, re-present. Do not write until approved.
* On approval: write `plans/roadmap.md` exactly as approved.

---

### Step F: STAMP AND ROUTE

* After writing `roadmap.md`, output:

```
ROADMAP LOCKED.

Features: [N]
Dependency layers: [N]

Next step: Run /io-architect to define CRC cards, Protocols, and the Interface Registry.
```

---

## 3. CONSTRAINTS

- This workflow produces ONLY `plans/roadmap.md`. No `.pyi` files, no `project-spec.md` edits.
- Do not decompose features into checkpoints here — that is `/io-checkpoint`'s job.
- Do not propose implementation approaches — roadmap entries describe outcomes, not mechanisms.
- If the PRD is ambiguous about whether two things are one feature or two, flag it and ask before proceeding.
- In brownfield repos, any PRD claim about existing behavior that cannot be verified against source must carry an `[UNVERIFIED]` tag through to `roadmap.md`.

---
name: io-replan
description: Propagate PRD changes to roadmap.md and project-spec.md without destroying existing work.
---

> **[CRITICAL] PLAN MODE**
> All proposed changes to `roadmap.md` and `project-spec.md` require human approval before write.

> **[CRITICAL] CONTEXT LOADING**
>
> 1. Load planning rules: `view_file .claude/rules/planning.md`
> 2. Load the Design Skill: `view_file .claude/skills/mini-spec/SKILL.md`
> 3. Load the Architecture Template: `view_file .claude/templates/project-spec.md`

# WORKFLOW: IO-REPLAN

**Objective:** Propagate changes from an updated `plans/PRD.md` into `plans/roadmap.md` and `plans/project-spec.md`, preserving all completed work and routing necessary codebase changes to `plans/backlog.yaml`.

**When to use:** Only when `plans/PRD.md` itself has changed. This is not part of the linear execution chain — it is triggered on-demand when requirements shift.

**Context manifest:**

1. `plans/PRD.md` — updated source of truth
2. `plans/roadmap.md` — existing feature sequence (to be updated)
3. `plans/project-spec.md` — existing architecture (to be updated)
4. `interfaces/*.pyi` — existing contracts (read-only in this workflow)
5. `plans/plan.yaml` — existing checkpoint plan (read-only — checkpoints are not replanned here)
6. `plans/backlog.yaml` — existing backlog (append target for regressions)

---

## 1. PROCEDURE

### Step A: [CRITICAL] CLARIFICATION GATE

* **Action:** Read the document header of `plans/PRD.md`.
* **Check:** Locate the `**Clarified:**` field.
* **Rule:** If missing or `False`, HALT immediately.
* **Output:** "HALT: PRD has not been clarified. Run `/io-clarify` and resolve all new ambiguities before replanning."

---

### Step B: DIFF ANALYSIS (Requirements Delta)

* **Action:** Read `plans/PRD.md`, `plans/roadmap.md`, and `plans/project-spec.md`.
* **Output:** A structured Change Report:

| Category | Description |
|----------|-------------|
| **NEW** | Requirements, features, or components in the PRD that have no match in roadmap or spec |
| **MODIFIED** | Features or components that exist but whose definition has changed. For each MODIFIED component, invoke `/symbol-tracer` with `--summary` on the component symbols to assess blast radius before proposing changes. |
| **REMOVED** | Items in roadmap or spec no longer referenced by the PRD |

Present the Change Report to the human for confirmation before proceeding.

---

### Step C: [PLAN MODE] PROPOSE ROADMAP.MD UPDATES

For each change in the delta:

* **NEW items:** Propose new feature entries in `roadmap.md` using the standard format. Assign dependency order.
* **MODIFIED items:** Propose updated acceptance criteria or description. Flag if the change invalidates any completed checkpoint — this becomes a `[DESIGN]` backlog item.
* **REMOVED items:** Propose marking the feature `[DEPRECATED]` with a note. Do not delete historical entries.

**Rule:** Every new or modified feature must cite the PRD section it traces to (e.g., `PRD 3.4`).

Present proposed roadmap changes. Wait for human approval before write.

---

### Step D: [PLAN MODE] PROPOSE PROJECT-SPEC.MD UPDATES

For each change in the delta:

* **NEW components:** Propose new CRC card and Interface Registry entry. Do not write `.pyi` — that is `/io-architect`'s job.
* **MODIFIED components:** Propose updated CRC responsibilities and sequence diagrams.
* **REMOVED components:** Propose marking the Protocol Interfaces row `[DEPRECATED]` and adding a deprecation warning to the CRC card.

Present proposed spec changes. Wait for human approval before write.

---

### Step E: BACKLOG ROUTING

If any MODIFIED or REMOVED item corresponds to already-implemented code:

* Append a `[DESIGN]` or `[REFACTOR]` item to `plans/backlog.yaml` via `stage_review_findings.py`.
* This ensures the execution pipeline will safely update or remove the orphaned code.

---

### Step F: VERIFY CONSISTENCY

* Cross-check: every feature in `roadmap.md` has a corresponding entry in `project-spec.md` Interface Registry.
* Cross-check: every CRC card maps to a feature. Flag orphans as warnings.
* Cross-check: `plans/plan.yaml` — identify any checkpoints that are now invalidated by the PRD delta. Flag them for human decision (re-run, deprecate, or keep).

---

### Step G: OUTPUT

```
REPLAN COMPLETE.

roadmap.md: [N] features added, [N] modified, [N] deprecated
project-spec.md: [N] CRC cards updated, [N] deprecated
backlog.yaml: [N] items appended

plan.yaml checkpoint impact: [N checkpoints flagged for review]

Next steps:
- Run /io-architect to update or add Protocol contracts (.pyi files)
- Run /io-checkpoint if new checkpoints are needed for new features
- Review flagged checkpoints in plan.yaml before next dispatch-agents.sh run
```

---

## 2. CONSTRAINTS

* Does not generate `.pyi` files — that is `/io-architect`'s job
* Does not modify `plans/plan.yaml` directly — checkpoint replanning is a separate `/io-checkpoint` invocation
* Does not delete any existing entries in `roadmap.md`, `project-spec.md`, or `backlog.yaml`
* All writes require human approval via plan mode
* `backlog.yaml` appends go via `stage_review_findings.py` — not written directly

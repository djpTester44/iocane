---
description: Design CRC cards, Protocols, and the Interface Registry. Tier 1 — plan mode required. Highest-value gate in the workflow.
---

> **[CRITICAL] PLAN MODE**
> This is the highest-value gate in the entire workflow.
> Claude PROPOSES the full design before writing any file.
> No `.pyi` file is written until the human approves.
> Human approval here is the Tier 1 / Tier 2 boundary — nothing executes until sign-off.

> **[CRITICAL] CONTEXT LOADING**
> 1. Load planning rules: `view_file .agent/rules/planning.md`
> 2. Load the Design Skill: `view_file .agent/skills/mini-spec/SKILL.md`
> 3. Load the PRD: `view_file plans/PRD.md`
> 4. Load the Roadmap: `view_file plans/roadmap.md`
> 5. Load current Architecture Spec (if exists): `view_file plans/project-spec.md`

# WORKFLOW: IO-ARCHITECT

**Objective:** Produce the full behavioral and structural design for all features in `roadmap.md`. Output: populated `plans/project-spec.md` (CRC cards, Interface Registry, dependency map) and all `interfaces/*.pyi` contracts.

**Position in chain:**
```
/io-specify -> [/io-architect] -> /io-checkpoint -> /io-orchestrate
```

**This workflow is the contract lock.** After human approval, the `.pyi` files are the binding source of truth. Sub-agents build against them. They are not modified during execution unless a formal replan is triggered.

---

## 1. STATE INITIALIZATION

Before proceeding, output the following metadata:

- **Roadmap status:** [roadmap.md present and complete?]
- **Existing project-spec.md:** [Present / Not present]
- **Existing interfaces/*.pyi:** [List existing contracts, if any]
- **Mode:** [Greenfield — new design | Incremental — extending existing design]

---

## 2. PROCEDURE

### Step A: [HARD GATE] ROADMAP PRESENT

* **Action:** Check that `plans/roadmap.md` exists and is not a draft.
* **Rule:** If missing or still marked `Draft`, HALT.
* **Output:** "HALT: roadmap.md not found or not approved. Run `/io-specify` first."

---

### Step B: ANALYZE DOMAIN

* **Action:** Read `plans/PRD.md` and `plans/roadmap.md`.
* **Goal:** Identify every distinct component required to satisfy all features.
* **Component types to identify:**
  * Domain entities (data models, aggregates)
  * Repositories / data access layer
  * Service / orchestration layer
  * External adapters (APIs, queues, storage)
  * Entrypoint layer (CLI, HTTP handlers, jobs)
* **Output:** Flat component inventory with type and layer classification.

---

### Step C: [PLAN MODE] PROPOSE DEPENDENCY MAP

* **Goal:** Show how components depend on each other across architectural layers.
* **Format:** Mermaid graph — components as nodes, dependency arrows showing direction.
* **Rules:**
  * Arrow direction = "depends on" (A → B means A depends on B)
  * Higher layers may only depend on lower layers (no upward imports)
  * Cross-layer dependencies must go through an interface in `interfaces/`

**Present the dependency map. Do not write any file yet.**

---

### Step D: [PLAN MODE] PROPOSE CRC CARDS

For every component identified in Step B, propose a CRC card:

```markdown
### [ComponentName]
**Layer:** [1-Foundation | 2-Utility | 3-Domain | 4-Entrypoint]
**File:** `src/[path]/[module].py`
**Protocol:** `interfaces/[protocol].pyi`

**Responsibilities:**
- [What this component does — observable behaviors only]
- [Each responsibility maps to at least one method in the Protocol]

**Collaborators:**
- [ComponentName] via [ProtocolName] — [why needed]

**Must NOT:**
- [Explicit negative constraints — what this component must never do]
```

**Present all CRC cards. Do not write any file yet.**

---

### Step E: [PLAN MODE] PROPOSE PROTOCOL SIGNATURES

For every CRC card, propose the corresponding Protocol interface:

```python
# interfaces/[protocol].pyi

from typing import Protocol
from [module] import [RelevantTypes]

class [ProtocolName](Protocol):
    def [method_name](self, [params]: [Types]) -> [ReturnType]:
        """[Docstring: what this method does, not how]"""
        ...
```

**Rules for Protocol design:**
- Every CRC responsibility maps to at least one method.
- Parameters and return types must be concrete — no `Any`, no `dict` without type params.
- Methods must be testable in isolation — no side-effectful signatures that cannot be mocked.
- Protocols describe behavior at the boundary, not implementation details.

**Present all Protocol signatures. Do not write any `.pyi` file yet.**

---

### Step F: [PLAN MODE] PROPOSE INTERFACE REGISTRY UPDATE

Propose the complete Interface Registry section for `plans/project-spec.md`:

```markdown
## Interface Registry

| Component | Protocol | File | Layer |
|-----------|----------|------|-------|
| [ComponentName] | [ProtocolName] | `interfaces/[protocol].pyi` | [N] |
```

Every component with a Protocol must appear here. This table is the write-gate's source of truth — sub-agents may only write to files registered here.

**Present the full Interface Registry. Do not write any file yet.**

---

### Step G: [HUMAN GATE] APPROVAL REQUIRED

Present a consolidated summary:

```
DESIGN PROPOSAL SUMMARY

Components: [N]
Protocols: [N]
New .pyi files to create: [list]
project-spec.md sections to update: [list]

Dependency map: [above]
CRC cards: [above]
Protocol signatures: [above]
Interface Registry: [above]

Reply with approval to lock contracts, or provide corrections.
```

* **WAIT** for explicit human approval.
* If corrections requested: revise and re-present. Do not write until approved.

---

### Step H: WRITE ARTIFACTS

On approval, execute the following steps in strict sequence. Do NOT parallelize any of these steps — the sentinel must be active for the entire write sequence.

**Step H-pre:** `bash: mkdir -p .iocane && touch .iocane/validating`

The sentinel prevents `reset-on-project-spec-write.sh` and `reset-on-pyi-write.sh` from resetting stamps mid-write. It must be created before the first write. The hook auto-deletes it when it detects the `**Approved:** True` stamp write at Step H-3.

**Step H-1:** Update `plans/project-spec.md`:
   * Add/update CRC cards for all proposed components
   * Add/update Interface Registry entries
   * Add/update Mermaid dependency graph
   * Add/update Sequence Diagrams for non-trivial flows

**Step H-2:** Write `interfaces/*.pyi`:
   * One file per Protocol
   * Exactly as approved — no additions or simplifications
   * Include docstrings on every method

**Step H-3:** Stamp `plans/project-spec.md` with `**Approved:** True` in the doc header.

The hook auto-deletes the sentinel when it detects the `**Approved:** True` stamp write — no explicit cleanup step required.

**Output:**

```
CONTRACTS LOCKED.

Protocols written: [N]
Interface Registry entries: [N]

This is the Tier 1 / Tier 2 boundary.
Sub-agents will build against these contracts exactly.
Contracts are frozen until a formal /io-replan is triggered.

Next step: Run /io-checkpoint to define atomic checkpoints and connectivity test signatures.
```

---

### Step I: GENERATE NAVIGATION ARTIFACTS

After Step H-post, generate two navigation artifacts from the approved design. These are derived outputs — generated from `project-spec.md` and the Interface Registry. Do not invent content; extract and reformat only.

**Step I-1: Write `ARCHITECTURE.md` at the project root.**

Content: the dependency graph (Mermaid) and layer map only. Nothing else.

```markdown
# Architecture

## Layer Map

| Layer | Path | Responsibility |
|-------|------|----------------|
| 1 — Foundation | `src/core/` | Config, types, domain primitives |
| 2 — Utility | `src/lib/` | Stateless clients, external adapters |
| 3 — Domain | `src/domain/` | Business logic, orchestrators |
| 4 — Entrypoint | `src/main.py` / `src/jobs/` | CLI, API handlers, job runners |

## Dependency Graph

[Mermaid diagram — copied verbatim from project-spec.md Section 4]
```

**Step I-2: Write a `CLAUDE.md` into each `src/` subdirectory** that contains at least one registered component.

Use `.agent/templates/dir-claude.md` as the structure. For each directory:
- `Layer`: from the Interface Registry layer column
- `Owns`: one sentence summarizing the CRC responsibilities for components in this directory
- `Public via`: list each Protocol registered to a component in this directory
- `Must NOT`: derive from the layer constraints in `pyproject.toml` import-linter config plus any explicit `Must NOT` lines from the CRC cards
- `Key files`: list only files with registered components, one line each

**Rule:** These files are generated artifacts — overwrite on every `/io-architect` run. They must stay under 20 lines. If content would exceed 20 lines, the directory has too many responsibilities and should be flagged as a `[DESIGN]` finding.

---

## 3. INCREMENTAL MODE (extending existing design)

If `project-spec.md` and `interfaces/*.pyi` already exist:

* **Read existing contracts before proposing anything.**
* **Identify conflicts:** Does the proposed new design contradict any existing Protocol signature?
* **Flag breaking changes explicitly** — any modification to an existing `.pyi` signature is a breaking change and requires separate human confirmation with explicit acknowledgment that downstream implementations may need updating.
* **Additive changes** (new Protocols, new methods on existing Protocols) follow the standard plan mode flow above.
* **Never silently modify** an existing `.pyi` signature.

---

## 4. CONSTRAINTS

- No implementation code in this workflow.
- No `tasks.md`, `plan.md`, or `roadmap.md` edits.
- `project-spec.md` reflects current codebase state only — no debt tracking, no state artifacts.
- Protocol files are binding contracts. They are the source of truth for sub-agent execution.
- The human's approval at Step G is the point of no return for Tier 2 delegation.

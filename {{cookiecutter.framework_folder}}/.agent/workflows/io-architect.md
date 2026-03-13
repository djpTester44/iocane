---
description: Design CRC cards, Protocols, and the Interface Registry. Tier 1 — plan mode required. Highest-value gate in the workflow.
---

> **[CRITICAL] PLAN MODE**
> This is the highest-value gate in the entire workflow.
> Claude WRITES the full design to `plans/project-spec.md` for human review in an editor.
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

### Step C: WRITE DEPENDENCY MAP

* **Goal:** Capture how components depend on each other across architectural layers.
* **Format:** Mermaid graph — components as nodes, dependency arrows showing direction.
* **Rules:**
  * Arrow direction = "depends on" (A → B means A depends on B)
  * Higher layers may only depend on lower layers (no upward imports)
  * Cross-layer dependencies must go through an interface in `interfaces/`

**Write** the dependency map to `plans/project-spec.md` under a `## Dependency Map` section. Do not print it to the terminal.

For incremental runs: mark any changed section with an HTML comment `<!-- CHANGED -->` on the section heading line.

---

### Step D: WRITE CRC CARDS

For every component identified in Step B, write a CRC card to `plans/project-spec.md` under a `## CRC Cards` section:

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

**Write all CRC cards to `plans/project-spec.md`. Do not print them to the terminal.**

For incremental runs: mark each new or changed CRC card heading with `<!-- CHANGED -->`.

---

### Step E: WRITE PROTOCOL SIGNATURES

For every CRC card, write the corresponding Protocol interface to `plans/project-spec.md` under a `## Protocol Signatures` section:

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

**Write all Protocol signatures to `plans/project-spec.md`. Do not print them to the terminal. Do not write `.pyi` files yet.**

For incremental runs: mark each new or changed Protocol heading with `<!-- CHANGED -->`.

---

### Step F: WRITE INTERFACE REGISTRY

Write the complete Interface Registry to `plans/project-spec.md` under a `## Interface Registry` section:

```markdown
## Interface Registry

| Component | Protocol | File | Layer |
|-----------|----------|------|-------|
| [ComponentName] | [ProtocolName] | `interfaces/[protocol].pyi` | [N] |
```

Every component with a Protocol must appear here. This table is the write-gate's source of truth — sub-agents may only write to files registered here.

**Write the full Interface Registry to `plans/project-spec.md`. Do not print it to the terminal.**

---

### Step G: [HUMAN GATE] APPROVAL REQUIRED

Print only this compact summary to the terminal:

```
DESIGN PROPOSAL WRITTEN

plans/project-spec.md is ready for review.
Open it in your editor to inspect the full design.

Components: [N]
Protocols:  [N]
.pyi files to create: [list filenames only]

Incremental run: search <!-- CHANGED --> to find what changed.

Reply with approval to lock contracts, or describe any correction needed
(cite section name and component).
```

* **WAIT** for explicit human approval.
* If corrections requested: edit `plans/project-spec.md` in place for the identified component only. Do not re-print the corrected content — tell the user which lines were changed and ask them to re-read the file. Do not proceed to Step H until approved.

---

### Step H: WRITE ARTIFACTS

On approval, execute the following steps in strict sequence. Do NOT parallelize any of these steps.

**Step H-1:** Strip all `<!-- CHANGED -->` markers from `plans/project-spec.md`.

**Step H-pre:** `bash: mkdir -p .iocane && touch .iocane/validating`

The sentinel prevents `reset-on-project-spec-write.sh` and `reset-on-pyi-write.sh` from resetting stamps during the `.pyi` write and stamp sequence. It must be set before Step H-3. The hook auto-deletes it when it detects the `**Approved:** True` stamp write at Step H-4.

**Step H-2:** Append `[[tool.importlinter.contracts]]` to `pyproject.toml`:
   * One `[[tool.importlinter.contracts]]` block for the layer hierarchy, ordered top-to-bottom (entrypoint → domain → utility → foundation)
   * Additional `[[tool.importlinter.contracts]]` blocks for any independence contracts between peer packages
   * Remove the `# [[tool.importlinter.contracts]] populated by /io-architect` comment placeholder
   * If `pyproject.toml` does not exist (brownfield adoption), create it from `.agent/templates/pyproject.toml` first, then append contracts

**Step H-3:** Write `interfaces/*.pyi`:
   * One file per Protocol
   * Exactly as written in `plans/project-spec.md` Protocol Signatures section — no additions or simplifications
   * Include docstrings on every method

**Step H-4:** Stamp `plans/project-spec.md` with `**Approved:** True` in the doc header.

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

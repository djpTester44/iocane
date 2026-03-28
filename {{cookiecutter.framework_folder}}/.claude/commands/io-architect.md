---
name: io-architect
description: Design CRC cards, Protocols, and the Interface Registry. Tier 1 — plan mode required. Highest-value gate in the workflow.
---

> **[CRITICAL] PLAN MODE**
> This is the highest-value gate in the entire workflow.
> Claude WRITES the full design to `plans/project-spec.md` for human review in an editor.
> No `.pyi` file is written until the human approves.
> Human approval here is the Tier 1 / Tier 2 boundary — nothing executes until sign-off.

> **[CRITICAL] CONTEXT LOADING**
> 1. Load planning rules: `view_file .claude/rules/planning.md`
> 2. Load the Design Skill: `view_file .claude/skills/mini-spec/SKILL.md`
> 3. Load the PRD: `view_file plans/PRD.md`
> 4. Load the Roadmap: `view_file plans/roadmap.md`
> 5. Load current Architecture Spec (if exists): `view_file plans/project-spec.md`

# WORKFLOW: IO-ARCHITECT

**Objective:** Produce the full behavioral and structural design for all features in `roadmap.md`. Output: populated `plans/project-spec.md` (CRC cards, Interface Registry, dependency map) and all `interfaces/*.pyi` contracts.

**Position in chain:**
```
/io-specify -> [/io-architect] -> /io-checkpoint -> /io-plan-batch -> dispatch-agents.sh
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

### Step B.5: IMPORT TRACE (brownfield only)

* **Gate:** If `plans/current-state.md` does not exist (greenfield), skip this step only and proceed to Step C. The rest of io-architect runs normally regardless.
* **Action:** Trace import statements for each `src/` module.
* **Output:** Two edge sets written to `plans/project-spec.md` under `## Import Trace`:
  * **ACTUAL edges** — import relationships as they exist in the current code.
  * **TARGET edges** — import relationships implied by the design in Step C.
* **Purpose:** The overlay reveals where rewiring is needed between current and target architecture.

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

For every component identified in Step B, write a CRC card using the format defined in the `mini-spec` skill (Section 2: CRC Card Standard).

* **Action:** Write all CRC cards to `plans/project-spec.md` under a `## CRC Cards` section. Do not print them to the terminal.
* **Incremental runs:** Mark each new or changed CRC card heading with `<!-- CHANGED -->`.

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
   * If `pyproject.toml` does not exist (brownfield adoption), create it from `.claude/templates/pyproject.toml` first, then append contracts

**Step H-2b:** Scaffold `src/` package directories from the Interface Registry:
   * For each registered package path in the Interface Registry, create the directory if it does not exist
   * Write a minimal `__init__.py` (empty or with a module docstring) to each new directory
   * Skip directories that already exist — do not overwrite existing `__init__.py` files

**Step H-3:** Write `interfaces/*.pyi`:
   * One file per Protocol
   * Exactly as written in `plans/project-spec.md` Protocol Signatures section — no additions or simplifications
   * Include docstrings on every method

**Step H-4:** Stamp `plans/project-spec.md` with `**Approved:** True` in the doc header.

**Step H-5:** `bash: rm -f .iocane/validating`

Explicit sentinel cleanup. Do not rely on the hook to auto-delete — if the stamp was already `True` before H-4, no write event fires and the sentinel is left dangling.

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

After Step H-post, generate navigation artifacts from the approved design. These are derived outputs — generated from `project-spec.md` and the Interface Registry. Do not invent content; extract and reformat only.

**Step I-1: Write a `CLAUDE.md` into each `src/` subdirectory** that contains at least one registered component.

Use `.claude/templates/dir-claude.md` as the structure. For each directory:
- `Layer`: from the Interface Registry layer column
- `Owns`: one sentence summarizing the CRC responsibilities for components in this directory
- `Public via`: list each Protocol registered to a component in this directory
- `Must NOT`: derive from the layer constraints in `pyproject.toml` import-linter config plus any explicit `Must NOT` lines from the CRC cards
- `Key files`: list only files with registered components, one line each

**Rule:** These files are generated artifacts — overwrite on every `/io-architect` run. They must stay under 20 lines. If content would exceed 20 lines, the directory has too many responsibilities and should be flagged as a `[DESIGN]` finding.

**Step I-2: Update `plans/seams.md`.**

For each component added or modified in this architect run (identified from the Interface Registry delta), update its entry in `plans/seams.md`:
- `Receives (DI)`: derive from the CRC card Collaborators list
- `External terminal`: derive from CRC card Responsibilities (any external system explicitly mentioned) and Must NOT constraints
- `Key failure modes`: derive from Protocol method docstrings (exception types documented)
- `Backlog refs`: leave blank — backlog is populated by `/io-review`, not `/io-architect`

If `plans/seams.md` does not exist, create it from `.claude/templates/seams.md`.
Derive from `plans/project-spec.md` only — do not read source code.

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

> `[HARD] Evidence citation rule:` Any spec claim citing existing code must include an explicit `file:line` citation. The architect must read the cited line before writing the claim. Uncited claims about existing code are forbidden.

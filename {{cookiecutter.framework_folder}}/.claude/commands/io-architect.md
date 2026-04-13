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
>
> 1. Load planning rules: `view_file .claude/rules/planning.md`
> 2. Load the Design Skill: `view_file .claude/skills/mini-spec/SKILL.md`
> 3. Load the PRD: `view_file plans/PRD.md`
> 4. Load the Roadmap: `view_file plans/roadmap.md`
> 5. Load current Architecture Spec (if exists): `view_file plans/project-spec.md`

# WORKFLOW: IO-ARCHITECT

**Objective:** Produce the full behavioral and structural design for all features in `roadmap.md`. Output: populated `plans/project-spec.md` (CRC cards, Interface Registry, dependency map) and all `interfaces/*.pyi` contracts.

**Position in chain:**

```
/io-specify -> [/io-architect] -> /io-checkpoint -> /io-plan-batch -> /validate-tasks -> dispatch-agents.sh
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

- **Action:** Check that `plans/roadmap.md` exists and is not a draft.
- **Rule:** If missing or still marked `Draft`, HALT.
- **Output:** "HALT: roadmap.md not found or not approved. Run `/io-specify` first."

---

### Step B: ANALYZE DOMAIN

- **Action:** Read `plans/PRD.md` and `plans/roadmap.md`.
- **Goal:** Identify every distinct component required to satisfy all features.
- **Component types to identify:**
  - Domain aggregates (entities with invariants — these get CRC cards)
- **Domain value types to identify separately:**
  - Value objects, DTOs, enums, and typed structures shared across components
  - These are contract vocabulary, not behavioral components — they do NOT get CRC cards
  - They will be defined in `interfaces/models.pyi` (Step E)
- **Component types (continued):**
  - Repositories / data access layer
  - Service / orchestration layer
  - External adapters (APIs, queues, storage)
  - Entrypoint layer (CLI, HTTP handlers, jobs)
- **Output:** Flat component inventory with type and layer classification.

---

### Step B.5: IMPORT TRACE (brownfield only)

- **Gate:** If `plans/current-state.md` does not exist (greenfield), skip this step only and proceed to Step C. The rest of io-architect runs normally regardless.
- **Action:** Trace import statements for each `src/` module.
- **Output:** Two edge sets written to `plans/project-spec.md` under `## Import Trace`:
  - **ACTUAL edges** — import relationships as they exist in the current code.
  - **TARGET edges** — import relationships implied by the design in Step C.
- **Purpose:** The overlay reveals where rewiring is needed between current and target architecture.

---

### Step C: WRITE DEPENDENCY MAP

- **Goal:** Capture how components depend on each other across architectural layers.
- **Format:** Mermaid graph — components as nodes, dependency arrows showing direction.
- **Rules:**
  - Arrow direction = "depends on" (A → B means A depends on B)
  - Higher layers may only depend on lower layers (no upward imports)
  - Cross-layer dependencies must go through an interface in `interfaces/`

**Write** the dependency map to `plans/project-spec.md` under a `## Dependency Map` section. Do not print it to the terminal.

For incremental runs: mark any changed section with an HTML comment `<!-- CHANGED -->` on the section heading line.

---

### Step D: DESIGN CRC CARDS

For every component identified in Step B, design a CRC card using the format defined in the `mini-spec` skill (Section 2: CRC Card Standard).

- **Action:** Determine responsibilities, must_not constraints, collaborators, layer, and roadmap features for each component. This is a reasoning step -- do not write to `plans/project-spec.md` yet. The CRC data will be written to `component-contracts.yaml` in Step H-2c and rendered to project-spec.md in Step I.
- **Incremental runs:** Note which CRC cards are new or changed for later `<!-- CHANGED -->` marking.

**[HARD] CRC budget caps.** A single component that absorbs too many behaviors, too many features, or too much composition wiring stops being a reviewable unit. Each CRC must satisfy all three caps; a violation forces decomposition, not a rewording.

- **Responsibility cap:** max 3 testable responsibilities per CRC. A component with 4+ responsibilities must be split.
- **Feature fan-out cap:** max 2 roadmap features per CRC. A component serving 3+ features from `plans/roadmap.md` must be split along feature boundaries. **Every component that carries feature logic MUST declare the feature IDs** (e.g., `F-01`, `F-02`) it supports -- they are written to the `features:` field in Step H-2c and are what the pre-gate reads. An empty `features:` is reserved for shared infrastructure that legitimately has no direct feature fan-out (e.g., `Settings`, loggers); the pre-gate emits a non-blocking warning if a behavioral component (has a Protocol or is a composition root) leaves `features:` empty, so A.1b cannot be silently bypassed by forgetting to declare.
- **Composition-root decomposition:** a `composition_root: true` component with 3+ Layer-2/3 collaborators (domain + infrastructure, excluding other composition roots) must decompose into resource-scoped sub-components -- one router/handler/sub-app per resource, each wiring at most 2 Layer-2/3 collaborators.

**Shared-type exemption:** `interfaces/models.pyi` and `interfaces/exceptions.pyi` hold contract vocabulary, not behavioral components -- they are not CRC cards and the caps do not apply. Mirrors the carve-out in `hooks/design-before-contract.sh`.

These caps are mechanically enforced by `.claude/scripts/validate_crc_budget.py` at Step G before the human approval gate. Thresholds are defined as constants in that script for per-project tuning.

---

### Step E: WRITE PROTOCOL SIGNATURES

For every CRC card, write the corresponding Protocol interface to `plans/project-spec.md` under a `## Protocol Signatures` section.

**First: define shared domain types.**

Before writing Protocol signatures, identify all domain types (value objects, DTOs, enums) referenced across Protocol method parameters and return types. Design these as `.pyi` stubs for `interfaces/models.pyi`.

Write these stubs to `plans/project-spec.md` under a `## Domain Type Stubs` section, before the Protocol Signatures section. Protocol files will import from these stubs.

For brownfield projects: derive type definitions from the design in Steps B-D, not from existing `src/` code. The types in `interfaces/models.pyi` are the contract-level vocabulary — they may differ from current runtime implementations.

**Protocol template:**

```python
# interfaces/[protocol].pyi

from typing import Protocol
from interfaces.models import [RelevantTypes]

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
- **[HARD] Self-containment:** Protocol `.pyi` files must not import from `src/`. All domain types must be defined in `interfaces/models.pyi`. All custom exceptions in `interfaces/exceptions.pyi`. The `interfaces/` package is the complete contract surface with no dependencies beyond the standard library and `typing`.

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

Every component with a Protocol must appear here. This table is the Protocol contract registry — it maps components to their interface definitions. Composition roots (Entrypoint Layer) do not appear here — they have no Protocol. They are registered in `plans/component-contracts.yaml` only (Step H-2c).

**Write the full Interface Registry to `plans/project-spec.md`. Do not print it to the terminal.**

---

### Step G-pre: [MECHANICAL PRE-GATE] CRC BUDGET CHECK

Before presenting the approval summary, write the Step D CRC design to `plans/component-contracts.yaml` (using `contract_parser.save_contracts()` with the same field set as Step H-2c, including the `features:` list) and run the budget validator:

```bash
uv run python .claude/scripts/validate_crc_budget.py
```

The script enforces the Step D [HARD] budget caps mechanically:

- **A.1a:** responsibilities <= 3 per CRC
- **A.1b:** features <= 2 per CRC (skipped when `features` is empty)
- **A.1c:** composition_root components with <= 2 Layer-2/3 collaborators. Until `plans/seams.yaml` is generated in Step I-0, the script falls back to counting every collaborator -- this is intentional and fail-safe.
- **A.1e:** components whose protocol is `interfaces/models.pyi` or `interfaces/exceptions.pyi` are skipped.

If the script exits non-zero, do NOT proceed to Step G. Revise the Step D design (decompose offending components, split feature fan-out, remove responsibilities) and re-run this step. The human never sees a design that has not cleared the pre-gate.

**On interruption.** Step G-pre writes the real `plans/component-contracts.yaml` before validation. If the workflow is interrupted (Ctrl-C, crash) between a failed validation and the revised rewrite, the repo is left with an over-budget contracts file on disk. Recover with `git checkout HEAD -- plans/component-contracts.yaml`, then re-run `/io-architect`. Equivalent to any interrupted write -- not a new class of risk.

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

- **WAIT** for explicit human approval.
- If corrections requested: edit `plans/project-spec.md` in place for the identified component only. Do not re-print the corrected content — tell the user which lines were changed and ask them to re-read the file. Do not proceed to Step H until approved.

---

### Step H: WRITE ARTIFACTS

On approval, execute the following steps in strict sequence. Do NOT parallelize any of these steps.

**Step H-1:** Strip all `<!-- CHANGED -->` markers from `plans/project-spec.md`.

**Step H-pre:** `bash: mkdir -p .iocane && touch .iocane/validating`

The sentinel prevents `reset-on-project-spec-write.sh` and `reset-on-pyi-write.sh` from resetting stamps during the `.pyi` write and stamp sequence. It must be set before Step H-3. The hook auto-deletes it when it detects the `**Approved:** True` stamp write at Step H-4.

**Step H-2:** Append `[[tool.importlinter.contracts]]` to `pyproject.toml`:

- One `[[tool.importlinter.contracts]]` block for the layer hierarchy, ordered top-to-bottom (entrypoint → domain → utility → foundation)
- Additional `[[tool.importlinter.contracts]]` blocks for any independence contracts between peer packages
- Remove the `# [[tool.importlinter.contracts]] populated by /io-architect` comment placeholder
- If `pyproject.toml` does not exist (brownfield adoption), create it from `.claude/templates/pyproject.toml` first, then append contracts

**Step H-2b:** Scaffold `src/` package directories from the Interface Registry:

- For each registered package path in the Interface Registry, create the directory if it does not exist
- Write a minimal `__init__.py` (empty or with a module docstring) to each new directory
- Skip directories that already exist — do not overwrite existing `__init__.py` files

**Step H-2c:** Write `plans/component-contracts.yaml` using `contract_parser.save_contracts()`:

- Build a `ComponentContractsFile` with one `ComponentContract` per component. Include structural, behavioral, and roadmap fields:
  - **Structural:** `file: src/...` (implementation path), `collaborators: [...]` (from the CRC card, `[]` if none), `composition_root: true` (Entrypoint Layer only; omit for others)
  - **Behavioral:** `responsibilities: [...]` (from CRC card design in Step D), `must_not: [...]` (from CRC card design in Step D), `protocol: interfaces/[name].pyi` (the .pyi path from the Interface Registry, omit for composition roots)
  - **Roadmap:** `features: [F-XX, ...]` (roadmap feature IDs from `plans/roadmap.md` this component supports). Required for every component that carries feature logic. Empty is reserved for shared infrastructure without direct feature fan-out; the pre-gate emits a warning (not a failure) if a behavioral component leaves this empty, so the A.1b cap cannot be bypassed by omission.
- Call `save_contracts()` to write -- this validates the model before serialization
- Overwrite if the file already exists -- it is always regenerated from the current design. Note: Step G-pre may have already written a passing draft; this step re-writes so any corrections applied during the Step G human review are captured.
- This file is the single source of truth for CRC data. The CRC section of project-spec.md is rendered from it in Step I.

**Step H-3:** Write `interfaces/*.pyi`:

- `interfaces/models.pyi` — domain type stubs, exactly as in `plans/project-spec.md` Domain Type Stubs section
- `interfaces/exceptions.pyi` — exception hierarchy (if any), exactly as in `plans/project-spec.md` Domain Type Stubs section
- One `.pyi` file per Protocol, exactly as in `plans/project-spec.md` Protocol Signatures section — no additions or simplifications
- Include docstrings on every method in Protocol files

**Step H-4:** Stamp `plans/project-spec.md` with `**Approved:** True` in the doc header.

**Step H-5:** `bash: rm -f .iocane/validating`

Explicit sentinel cleanup. Do not rely on the hook to auto-delete — if the stamp was already `True` before H-4, no write event fires and the sentinel is left dangling.

**Output:**

```
CONTRACTS LOCKED.

Protocols written: [N]
Interface Registry entries: [N]
component-contracts.yaml: written

This is the Tier 1 / Tier 2 boundary.
Sub-agents will build against these contracts exactly.
Contracts are frozen until a formal /io-replan is triggered.

Next step: Run /io-checkpoint to define atomic checkpoints and connectivity test signatures.
```

---

### Step I: GENERATE NAVIGATION ARTIFACTS

After Step H-post, generate navigation artifacts from the approved design. Step I-0 derives the integration seams from the approved design (layer assignments require architect judgment). Steps I-1 and I-2 are mechanical reformatters -- generated from `component-contracts.yaml` and `seams.yaml`. Do not invent content in I-1 or I-2; extract and reformat only.

**Step I-0: Update `plans/seams.yaml`.**

For each component added or modified in this architect run (identified from the Interface Registry delta), update its entry in `plans/seams.yaml` using `seam_parser` functions:

```bash
uv run python -c "
import sys; sys.path.insert(0, '.claude/scripts')
from seam_parser import load_seams, save_seams, add_component, update_component
from schemas import SeamComponent
seams = load_seams('plans/seams.yaml')
# Use add_component() for new entries, update_component() for existing
"
```

- `receives_di`: derive from the CRC card Collaborators list (deprecated alias; retained for readers that have not migrated to Protocol-level DI graphs)
- `receives_di_protocols`: **Appendix A §A.3b.** Required for every component whose `component-contracts.yaml` entry has `composition_root: true`. Enumerate every Protocol the component injects -- these are Protocol names (the `.pyi` class symbols), not collaborator component names. This list drives the composition-root CT emission in `/io-checkpoint` Step D. For non-composition components, leave empty.
- `external_terminal`: derive from CRC card Responsibilities (any external system explicitly mentioned) and Must NOT constraints
- `key_failure_modes`: derive from Protocol method docstrings (exception types documented)
- `layer`: assign based on component placement (1=Foundation, 2=Utility, 3=Domain)
- `backlog_refs`: leave empty — backlog is populated by `/io-review`, not `/io-architect`

If `plans/seams.yaml` does not exist, create it from `.claude/templates/seams.yaml`.
Derive from `plans/project-spec.md` only — do not read source code.

**Step I-1: Render CRC section of project-spec.md from YAML.**

Run the render script to generate the CRC Cards section from `component-contracts.yaml`:

```bash
uv run python .claude/scripts/render_crc.py
```

This overwrites the `## CRC Cards` section in `plans/project-spec.md` with content derived from `plans/component-contracts.yaml`. For incremental runs, use `git diff plans/project-spec.md` to inspect what changed.

**Step I-2: Regenerate directory-level CLAUDE.md files.**

Run the sync script:

```bash
uv run python .claude/scripts/sync_dir_claude.py
```

**Rule:** These files are generated artifacts -- the script overwrites them.
They must stay under 20 lines. If the script reports exit code 2 (line-count
exceeded), flag the directory as a `[DESIGN]` finding.

**Step I-3: [MECHANICAL POST-GATE] FILE-REFERENCE RESOLVABILITY.**

**Appendix A §A.6c (architect stage).** After all spec artifacts (project-spec.md, component-contracts.yaml, seams.yaml, interfaces/*.pyi) are on disk, scan them plus PRD/roadmap for path references that do not resolve:

```bash
uv run python .claude/scripts/validate_path_refs.py --stage architect
```

The script uses `rg` with extension-anchored patterns (A.6a). For each extracted path it verifies resolution against (a) the filesystem, (b) any existing plan.yaml's `write_targets`, (c) any existing plan.yaml's `relies_on_existing`. Unresolved paths emit OBSERVATION-severity `WARN:` lines on stderr. Exit code is always 0 -- non-blocking by design.

Surface the stderr output verbatim to the user. Do not auto-fix. An unresolved path is a signal that either (1) a referenced artifact was authored from memory without Grep-verification, or (2) a legitimate upcoming CP will produce the artifact -- in the second case the warning re-appears at `/validate-plan` Step 9D with the full plan context, where a CP `write_target` or `relies_on_existing` declaration can close it.

---

## 3. INCREMENTAL MODE (extending existing design)

If `project-spec.md` and `interfaces/*.pyi` already exist:

- **Read existing contracts before proposing anything.**
- **Identify conflicts:** Does the proposed new design contradict any existing Protocol signature?
- **Flag breaking changes explicitly** — any modification to an existing `.pyi` signature is a breaking change and requires separate human confirmation with explicit acknowledgment that downstream implementations may need updating.
- **Additive changes** (new Protocols, new methods on existing Protocols) follow the standard plan mode flow above.
- **Never silently modify** an existing `.pyi` signature.

---

## 4. CONSTRAINTS

- No implementation code in this workflow.
- No task file, `plan.yaml`, or `roadmap.md` edits.
- `project-spec.md` reflects current codebase state only — no debt tracking, no state artifacts.
- Protocol files are binding contracts. They are the source of truth for sub-agent execution.
- The human's approval at Step G is the point of no return for Tier 2 delegation.
- **Appendix A §A.6e -- Grep-verify paths before writing.** Before writing any file path into `project-spec.md`, `component-contracts.yaml`, `seams.yaml`, or the Interface Registry, use the Grep tool to verify the path either (a) already exists on disk, (b) traces to an upstream artifact (PRD, roadmap), or (c) is a declared output of this architect run. Paths authored from memory are a recurring defect class. The Step I-3 mechanical gate catches unresolved references non-blockingly, but authoring discipline is the primary defense.

> `[HARD] Evidence citation rule:` Any spec claim citing existing code must include an explicit `file:line` citation. The architect must read the cited line before writing the claim. Uncited claims about existing code are forbidden.

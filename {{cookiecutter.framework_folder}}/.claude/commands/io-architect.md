---
name: io-architect
description: Design CRC cards, Protocols, cross-CP symbols, and component contract behavioral invariants. Tier 1 -- plan mode required. Highest-value gate in the workflow.
model: claude-opus-4-7
effort: xhigh
---

> **[CRITICAL] PLAN MODE**
> This is the highest-value gate in the entire workflow.
> Claude authors the full design as canonical YAML artifacts for human review.
> Human approval at Step I is the Tier 1 / Tier 2 boundary -- nothing executes until sign-off.

> **[CRITICAL] CONTEXT LOADING**
>
> 1. Load planning rules: `view_file .claude/rules/planning.md`
> 2. Load CDD governance: `view_file .claude/rules/cdd.md`
> 3. Load the Design Skill: `view_file .claude/skills/mini-spec/SKILL.md`
> 4. Load the PRD: `view_file plans/PRD.md`
> 5. Load the Roadmap: `view_file plans/roadmap.md`
> 6. Load existing canonical artifacts (if present): `plans/component-contracts.yaml`, `plans/seams.yaml`, `plans/symbols.yaml`, `plans/test-plan.yaml`
> 7. Load symbol and test-plan references: `.claude/references/symbols-schema.md`, `.claude/references/test-plan-schema.md`

# WORKFLOW: IO-ARCHITECT

**Objective:** Produce the full behavioral and structural design for all features in `roadmap.md`. Canonical outputs:

- `plans/component-contracts.yaml` -- per-component contract surface (CRC, collaborators, file paths, feature mapping, behavioral contract fields)
- `plans/seams.yaml` -- integration graph, external terminals, failure modes
- `plans/symbols.yaml` -- every cross-CP identifier (Settings fields, exception classes, shared types, fixtures, error messages)
- `plans/test-plan.yaml` -- `TestPlanEntry` records with behavioral invariants

YAML is the authority: the canonical four-file set above is the full
design surface. The architect authors no downstream rendered files.

**Position in chain:**

```
/io-specify -> [/io-architect]
            -> /io-wire-tests-cdt -> /io-wire-tests-ct
            -> /io-checkpoint -> /validate-plan
            -> /io-plan-batch -> /validate-tasks
            -> dispatch-agents.sh (Execution Sandbox + scope-cap)
            -> /io-verify
```

**This workflow is the contract lock.** After human approval, the canonical YAML set is the binding source of truth. Sub-agents build against it. It is not modified during execution unless a formal replan is triggered.

---

## 1. STATE INITIALIZATION

Output the following metadata:

- **Roadmap status:** [roadmap.md present and complete?]
- **Existing canonical artifacts:** [list which of component-contracts/seams/symbols/test-plan exist]
- **Mode:** [Greenfield | Incremental]

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
  - Domain aggregates (entities with invariants -- these get CRC cards)
- **Domain value types to identify separately:**
  - Value objects, DTOs, enums, and typed structures shared across components
  - These are contract vocabulary, not behavioral components -- they do NOT get CRC cards
  - They will be declared in `plans/symbols.yaml` as `kind: shared_type` entries (Step F-4) with `declared_in` pointing at either `src/...` (project-defined) or a bare module path for third-party types. Runtime type definitions live under `src/` or in an installed package.
- **Component types (continued):**
  - Repositories / data access layer
  - Service / orchestration layer
  - External adapters (APIs, queues, storage)
  - Entrypoint layer (CLI, HTTP handlers, jobs)
- **Output:** Flat component inventory with type and layer classification (reasoning-only; not written to a file).

---

### Step B.5: IMPORT TRACE (brownfield only)

- **Gate:** If `plans/current-state.md` does not exist (greenfield), skip this step only and proceed to Step C. The rest of io-architect runs normally regardless.
- **Action:** Trace import statements for each `src/` module.
- **Output:** Two edge sets held as reasoning artifacts for Step C. ACTUAL edges are the import relationships in current code; TARGET edges are the relationships implied by the Step C dependency map. Reconcile the two when proposing the target design; if they diverge, surface the divergence in the Step I approval summary.

---

### Step C: REASON THROUGH DEPENDENCY MAP

- **Goal:** Capture how components depend on each other across architectural layers.
- **Format:** Mermaid graph in your reasoning, not written to any file. The `collaborators:` field on each component in `component-contracts.yaml` is the canonical encoding of the same information.
- **Rules:**
  - Arrow direction = "depends on" (A -> B means A depends on B)
  - Higher layers may only depend on lower layers (no upward imports)
  - Cross-layer dependencies must go through a contract boundary (component contracts authored in `plans/component-contracts.yaml`).

---

### Step D: DESIGN CRC CARDS

For every component identified in Step B, design a CRC card using the format defined in the `mini-spec` skill (Section 2: CRC Card Standard).

- **Action:** Determine responsibilities, must_not constraints, collaborators, layer, and roadmap features for each component. This is a reasoning step -- the CRC data is written to `component-contracts.yaml` in Step F-3.
- **Incremental runs:** Note which CRC cards are new or changed.

**[HARD] CRC budget caps.** A single component that absorbs too many behaviors, too many features, or too much composition wiring stops being a reviewable unit. Each CRC must satisfy all three caps; a violation forces decomposition, not a rewording.

- **Responsibility cap:** max 3 testable responsibilities per CRC. A component with 4+ responsibilities must be split.
- **Feature fan-out cap:** max 2 roadmap features per CRC. A component serving 3+ features from `plans/roadmap.md` must be split along feature boundaries. **Every component that carries feature logic MUST declare the feature IDs** (e.g., `F-01`, `F-02`) it supports -- they are written to the `features:` field in Step F-3 and are what the budget validator reads. An empty `features:` is reserved for shared infrastructure that legitimately has no direct feature fan-out (e.g., `Settings`, loggers); the validator emits a non-blocking warning if a behavioral component (has declared responsibilities or is a composition root) leaves `features:` empty, so A.1b cannot be silently bypassed by forgetting to declare.
- **Composition-root decomposition:** a `composition_root: true` component with 3+ Layer-2/3 collaborators (domain + infrastructure, excluding other composition roots) must decompose into resource-scoped sub-components -- one router/handler/sub-app per resource, each wiring at most 2 Layer-2/3 collaborators.
- **Composition roots are wiring entries, not behavioral contracts.** Components with `composition_root: true` are Layer 4 entries that wire collaborators rather than declare a behavioral surface; they are registered in `plans/component-contracts.yaml` for collaborator-graph and feature-fan-out tracking only and typically leave `responsibilities` and `raises` empty.

These caps are mechanically enforced by `.claude/scripts/validate_crc_budget.py` at Step G as part of the deterministic batch.

---

### Step F: WRITE ARTIFACTS

On reaching Step F, execute the following sub-steps in strict sequence. Do NOT parallelize any of these sub-steps.

**Step F-pre:** `bash: uv run python .claude/scripts/capability.py grant --template io-architect.H`

Issues the capability grant that authorizes the canonical-YAML write sequence (Steps F-3, F-4, F-5, F-6, the Step F-7 `pyproject.toml` regeneration, and the Step G `test-plan.yaml` validated stamp). The grant is declared in `.claude/capability-templates/io-architect.H.yaml` -- git-tracked, PR-reviewable. `reset-on-symbols-write.sh` and `reset-on-test-plan-write.sh` consult the active capability cache and bypass their resets when a matching write pattern is covered.

**Per-cycle re-grant.** The H-loop re-enters Step F after Step H FINDINGS or Step I corrections; the bracket extends through every cycle. For evaluator-driven re-entry, `.claude/hooks/regrant-on-evaluator-return.sh` (PostToolUse Bash) re-issues this grant deterministically when `spawn-artifact-evaluator.sh` returns. For Step I correction-driven re-entry (operator feedback at the human gate), explicitly re-invoke this F-pre command. The template's `ttl_seconds` is the per-cycle crash-safety floor, not the workflow-span ceiling. Step J-2's template-matched revoke clears all accumulated grants at workflow end.

**Step F-2:** Scaffold `src/` package directories from the Step D dependency-map reasoning:

- For each registered package path, create the directory if it does not exist
- Write a minimal `__init__.py` (empty or with a module docstring) to each new directory
- Skip directories that already exist -- do not overwrite existing `__init__.py` files

**Step F-3:** Author `plans/component-contracts.yaml` directly via the Write tool. The `validate-yaml.sh` PostToolUse hook validates the file against `ComponentContractsFile` schema on every write; schema violations surface as exit-2 with Pydantic ValidationError context. On failure, Edit `plans/component-contracts.yaml` to correct and re-save.

- Build a `ComponentContractsFile` with one `ComponentContract` per component. Populate structural, behavioral, roadmap, and raises sections as described below; for field shapes beyond this summary, consult `schemas.py` (ComponentContract model) and `.claude/references/symbols-schema.md`:
  - **Structural:** `file: src/...` (implementation path), `collaborators: [...]` (from the CRC card, `[]` if none), `composition_root: true` (Entrypoint Layer only; omit for others)
  - **Behavioral:** `responsibilities: [...]` (from CRC card design in Step D), `must_not: [...]` (from CRC card design in Step D)
  - **Roadmap:** `features: [F-XX, ...]` (roadmap feature IDs from `plans/roadmap.md` this component supports). Required for every component that carries feature logic. Empty is reserved for shared infrastructure without direct feature fan-out; the budget validator emits a warning (not a failure) if a behavioral component leaves this empty, so the A.1b cap cannot be bypassed by omission.
  - **Raises-list:** `raises: [...]` declares the component-level exception surface -- bare class names (e.g. `RouteNotFound`) or dotted stdlib names (e.g. `subprocess.CalledProcessError`). Composition-root components typically leave this empty. The raises-list is the authoritative record of exceptions a component can propagate; `test-plan.yaml` `error_propagation` invariants must cover each entry.
    - **Validator scope:** Pydantic field-validators on `ComponentContract` enforce identifier-safe names at construction and at `ComponentContractsFile.model_validate(...)` load; `save_contracts()` round-trips its dump through `model_validate()` to catch state that became invalid between construction and save. Step G runs `validate_symbols_coverage.py` to close the cross-YAML reference loop between every component's raises-list and `symbols.yaml` `exception_class` entries.
- Overwrite if the file already exists -- it is always regenerated from the current design.

**Step F-4:** Author `plans/symbols.yaml` directly via the Write tool. The `validate-yaml.sh` PostToolUse hook validates against `SymbolsFile` schema on every write; failures surface with line context. Edit and re-save on failure.

- For every cross-CP identifier that must be spelled and typed consistently across more than one checkpoint, add a `Symbol` entry. Consult `.claude/references/symbols-schema.md` for the `SymbolKind` catalogue, per-kind field requirements, and `declared_in` zone rules.
- Populate `used_by:` with the COMPONENT NAMES (from CRC collaborator analysis) that reference each symbol. Do NOT populate `used_by_cps:` -- that field is checkpoint-backfilled at `/io-checkpoint` and stays empty until then.
- Conflict detection (`detect_env_var_conflicts`, `detect_message_pattern_conflicts`) runs at Step G and at `/validate-plan`.

**Step F-5:** Author `plans/test-plan.yaml` directly via the Write tool. The `validate-yaml.sh` PostToolUse hook validates against `TestPlanFile` schema on every write; failures surface with line context. Edit and re-save on failure.

- For every component contract authored in Step F-3, create one `TestPlanEntry` keyed by the component name. `TestPlanFile.entries` is a component-keyed dict that mirrors `ComponentContractsFile.components`; each entry's `component` field must match its dict key (a Pydantic model_validator enforces this).
- Populate the entry's `invariants` to cover (a) every behavioral commitment derivable from the component's `responsibilities`, and (b) every name in the component's `raises` list. Each invariant carries:
  - `id` in `INV-NNN` format (zero-padded, project-unique)
  - `kind` chosen from the `InvariantKind` catalogue
  - `description` -- a one-line behavioral claim
  - `pass_criteria` -- enough detail for the Test Author to write the test without reading the implementation
  - `method` (optional) -- a Python identifier anchoring the invariant to a specific method scope. The architect supplies this from impl knowledge when an `error_propagation` invariant covers a particular raises entry; no upstream YAML supplies method context, so leave `method` unset unless it adds value.
- **Rule:** every raises-list name declared on a component MUST have at least one `error_propagation` invariant under that component's `TestPlanEntry` that names the raised type and the trigger. Gaps here are a contract-authoring error -- `validate_test_plan_completeness.py` catches them at Step G.
- **Rule:** every contract postcondition (observable side effect, return shape constraint, state transition) SHOULD have at least one invariant covering it. Gaps are non-blocking at authoring time but are surfaced by `validate_test_plan_completeness.py` at `/validate-plan`.
- Consult `.claude/references/test-plan-schema.md` for the invariant taxonomy and worked examples.

**Step F-6:** Update `plans/seams.yaml` via the seam_parser delta-merge interface.

Seams uses incremental per-component delta-merge rather than full-file regeneration: only components added or modified in this architect run (identified from the `component-contracts.yaml` delta) update their entries. Use `add_component()` for new entries and `update_component()` for existing ones from `seam_parser`. The `validate-yaml.sh` PostToolUse hook validates the resulting file against `SeamsFile` schema on every write.

Per-component fields:

- `injected_contracts`: **Appendix A §A.3b.** Required for every component whose `component-contracts.yaml` entry has `composition_root: true`. Enumerate every contract the component injects -- these are the contract names (as declared in `component-contracts.yaml`), not collaborator component names. This list drives the composition-root CT emission in `/io-checkpoint` Step D. For non-composition components, leave empty.
- `external_terminal`: derive from CRC card Responsibilities (any external system explicitly mentioned) and Must NOT constraints
- `key_failure_modes`: derive from the raises-list declared on the component's contract
- `layer`: assign based on component placement (1=Foundation, 2=Utility, 3=Domain, 4=Entrypoint). Components with `composition_root: true` belong at Layer 4.
- `backlog_refs`: leave empty -- backlog is populated by `/io-review`, not `/io-architect`

If `plans/seams.yaml` does not exist, create it from `.claude/templates/seams.yaml`.
Derive from the Step C-D reasoning only -- do not read source code.

**Step F-7:** Regenerate `pyproject.toml` `[[tool.importlinter.contracts]]` blocks via `compose_importlinter_contracts.py`:

```bash
uv run python .claude/scripts/compose_importlinter_contracts.py
```

The script reads `plans/component-contracts.yaml` (`file:` paths via parser) and `plans/seams.yaml` (`layer:` field per component, peer-package detection). It strips any existing `[[tool.importlinter.contracts]]` blocks and regenerates them from the canonical YAMLs (layer hierarchy + connector independence). Non-importlinter pyproject sections (`[build-system]`, `[project]`, `[tool.ruff]`, etc.) are preserved via tomlkit. Idempotent: byte-identical output for identical inputs from the second run forward.

Brownfield projects without `pyproject.toml` pass `--bootstrap` to copy from `.claude/templates/pyproject.toml` first. The script also handles the "pyproject.toml exists but lacks `[tool.importlinter]` section" case via strip-zero-or-more + always-append semantics; no special flag needed.

---

### Step G: [MECHANICAL BATCH] DETERMINISTIC GATES

Run all five deterministic validators against the four canonical artifacts authored in Step F. The architect IS the authority on these constraints; catching gaps here is when the fix is cheap (just edit the artifact you're holding in mind).

```bash
uv run python .claude/scripts/validate_crc_budget.py
uv run python .claude/scripts/validate_symbols_coverage.py
uv run python .claude/scripts/validate_test_plan_completeness.py \
    --contracts plans/component-contracts.yaml
uv run python .claude/scripts/validate_path_refs.py --stage architect
uv run python -c "
import sys; sys.path.insert(0, '.claude/scripts')
from symbols_parser import load_symbols, detect_env_var_conflicts, detect_message_pattern_conflicts
r = load_symbols('plans/symbols.yaml')
e = detect_env_var_conflicts(r)
m = detect_message_pattern_conflicts(r)
if e:
    print('ENV_VAR_CONFLICT:', e)
if m:
    print('MSG_PATTERN_CONFLICT:', m)
"
```

Exit-code policy:

- `validate_crc_budget.py` exits non-zero on responsibility, feature, or composition-root cap violation. Thresholds are defined as constants in the script for per-project tuning.
- `validate_symbols_coverage.py` exits 1 on uncovered project-custom exceptions OR symbol conflicts. Stdlib and builtin exceptions are correctly skipped.
- `validate_test_plan_completeness.py` exits 1 on either (a) a component in `component-contracts.yaml` that has no `TestPlanEntry` in `test-plan.yaml`, or (b) a component whose `raises` is non-empty but whose `TestPlanEntry` carries no `error_propagation` invariant. The architect has the contract surface in front of them when authoring `test-plan.yaml`, so every component is expected to receive at least one invariant and every raises-list name is expected to be covered.
- `validate_path_refs.py` always exits 0 -- non-blocking by design. Unresolved paths emit OBSERVATION-severity `WARN:` lines on stderr; surface verbatim. Path references to rendered-output artifacts are expected to surface here and resolve when those artifacts are produced downstream.
- Symbol conflict detection (env_var + message_pattern): non-empty output is an authoring error. Surface stderr verbatim.

**Recovery rule.** Any non-zero exit code or non-empty conflict output sends the architect back to Step F to revise + re-author. The full Step F write sequence re-runs as a single design pass; this batch then re-validates. Do not edit individual artifacts in place outside the Step F-pre / Step J capability bracket.

After all gates pass, stamp `plans/test-plan.yaml` with `validated: true`:

```bash
uv run python -c "
import sys
sys.path.insert(0, '.claude/scripts')
from test_plan_parser import load_test_plan, save_test_plan
tp = load_test_plan('plans/test-plan.yaml')
tp.validated = True
tp.validated_date = 'YYYY-MM-DD'
tp.validated_note = 'PASS at io-architect Step G'
save_test_plan('plans/test-plan.yaml', tp)
"
```

The stamp lives with the architect because the architect is the only authority that can re-author the canonical artifacts when invariants drift. `/validate-plan` does NOT re-run this batch or re-stamp test-plan.yaml -- it trusts the architect's self-blessing because the reset-hook chain forces re-architect on any post-blessing mutation.

---

### Step H: [SEMANTIC GATE] ARTIFACT EVALUATOR

Run the artifact-evaluator subprocess against the complete four-file canonical artifact set:

```bash
bash .claude/scripts/spawn-artifact-evaluator.sh --rubric design \
    --contracts plans/component-contracts.yaml \
    --seams plans/seams.yaml \
    --symbols plans/symbols.yaml \
    --test-plan plans/test-plan.yaml
```

The subprocess reasons over whether invariants are tautological, whether Raises descriptions are specific enough, whether symbol classifications make sense, whether the design admits the roadmap features it claims, and whether the contract surface decomposition is reviewable.

**Outputs.**

- **PASS:** evaluator finds no FINDINGS. Proceed to Step I.
- **FINDINGS file:** evaluator emits OBSERVATION findings to a path printed on stdout. The architect reads the findings, revises the design, and re-runs the full Step F write sequence as a single design pass. Step G mechanically re-validates after each Step F revision; Step H re-runs against the revised artifact set.

**Iteration loop bound.** Maximum 5 cycles of `Step F -> Step G -> Step H`. After the 5th cycle, halt with: "evaluator surfaced FINDINGS; iteration budget exhausted (5 cycles)" and surface the latest findings file plus the prior cycles' findings paths to the operator. Do NOT proceed to Step I on an exhausted budget.

---

### Step I: [HUMAN GATE] APPROVAL REQUIRED

After Step H PASS, present the design for human approval. Print only this compact summary to the terminal:

```
DESIGN PROPOSAL READY FOR REVIEW

Authored under Step F:
  plans/component-contracts.yaml ([N] components, [N] raises entries total)
  plans/seams.yaml               ([N] seam entries)
  plans/symbols.yaml             ([N] cross-CP symbols)
  plans/test-plan.yaml           ([N] entries, [N] invariants)

All five mechanical gates PASS at Step G.
Artifact-evaluator PASS at Step H ([N] iteration cycles).

Open the canonical artifacts in your editor to inspect the full design.

Incremental run: review git diff against the last approved state.

Reply with approval to lock contracts, or describe any correction needed
(cite component name and field).
```

- **WAIT** for explicit human approval.
- If corrections requested: revise from Step F as a single design pass. Do not edit individual artifacts in place outside the Step F-pre / Step J capability bracket. Re-run Steps F -> G -> H to re-validate before re-presenting.

---

### Step J: FINALIZE

On approval, regenerate directory-level CLAUDE.md files and revoke the capability grant.

**Step J-1:** Regenerate directory-level CLAUDE.md files:

```bash
uv run python .claude/scripts/sync_dir_claude.py
```

**Rule:** These files are generated artifacts -- the script overwrites them.
They must stay under 30 lines. If the script reports exit code 2 (line-count
exceeded), flag the directory as a `[DESIGN]` finding.

**Step J-2:** `bash: uv run python .claude/scripts/capability.py revoke --template io-architect.H`

Explicit capability revoke. Run whether or not the last write succeeded -- the alternative is a lingering grant that silently bypasses future gate enforcement until TTL expiry or session-end (the 24h hard ceiling and the session-end sweep are defense-in-depth, not a substitute for explicit revoke).

**Output:**

```
CONTRACTS LOCKED.

component-contracts.yaml: [N] components, [N] raises entries
seams.yaml:               [N] seam entries
symbols.yaml:             [N] cross-CP symbols
test-plan.yaml:           [N] entries, [N] invariants

This is the Tier 1 / Tier 2 boundary.

Next:
  1. Run /io-checkpoint.
```

---

## 3. INCREMENTAL MODE (extending existing design)

When canonical artifacts already exist, the workflow walks the same Steps F/G/H/I/J as greenfield, with these additional discipline points:

- **Read existing canonical YAMLs before proposing anything.** `component-contracts.yaml`, `symbols.yaml`, `test-plan.yaml`, and `seams.yaml` are the authoritative surface. The Step B/C/D reasoning loads them via parser functions (`contract_parser.load_contracts()`, `seam_parser.load_seams()`, `symbols_parser.load_symbols()`, `test_plan_parser.load_test_plan()`) before proposing any modification.
- **Identify conflicts:** Does the proposed new design contradict any existing component contract, symbol declaration, or test-plan invariant?
- **Flag breaking changes explicitly** -- any modification to an existing component contract's behavioral surface, symbol kind, or invariant is a breaking change. Surface a breaking-change summary in the Step I approval prompt and require explicit acknowledgment that downstream tests and implementations may need updating.
- **Additive changes** (new components, new behavioral surface on existing components, new symbols, new invariants) follow the standard Step F authoring flow.
- **Capability bracket is mandatory.** Any write to `plans/component-contracts.yaml`, `plans/seams.yaml`, `plans/symbols.yaml`, or `plans/test-plan.yaml` outside an active `io-architect.H` capability grant triggers `reset-on-symbols-write.sh` / `reset-on-test-plan-write.sh`, which silently flip `test-plan.yaml.validated` back to `false`. The full incremental cycle (Step F-pre grant -> Step F authoring -> Step G mechanical batch + re-stamp -> Step H evaluator -> Step I human gate -> Step J revoke) runs as a unit; do not patch individual fields outside the bracket.
- **Never silently modify** an existing component contract, `symbols.yaml` entry, or `test-plan.yaml` entry. Updates to the canonical set propagate to all downstream consumers on next read.

---

## 4. CONSTRAINTS

- No implementation code in this workflow.
- No task file, `plan.yaml`, or `roadmap.md` edits.
- `plans/component-contracts.yaml` + `plans/seams.yaml` + `plans/symbols.yaml` + `plans/test-plan.yaml` are binding contracts. They are the source of truth for sub-agent execution.
- The human's approval at Step I is the point of no return for Tier 2 delegation.
- **Appendix A §A.6e -- Grep-verify paths before writing.** Before writing any file path into any canonical artifact, use the Grep tool to verify the path either (a) already exists on disk, (b) traces to an upstream artifact (PRD, roadmap), or (c) is a declared output of this architect run. Paths authored from memory are a recurring defect class. The Step G mechanical batch catches unresolved references non-blockingly, but authoring discipline is the primary defense.

> `[HARD] Evidence citation rule:` Any spec claim citing existing code must include an explicit `file:line` citation. The architect must read the cited line before writing the claim. Uncited claims about existing code are forbidden.

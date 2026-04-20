---
name: io-architect
description: Design CRC cards, Protocols, cross-CP symbols, and per-method behavioral invariants. Tier 1 -- plan mode required. Highest-value gate in the workflow.
---

> **[CRITICAL] PLAN MODE**
> This is the highest-value gate in the entire workflow.
> Claude authors the full design as canonical YAML artifacts for human review.
> `interfaces/*.pyi` emission is handed off to `/io-gen-protocols` after Step G approval -- the architect does not hand-author Protocol stubs.
> Human approval at Step G is the Tier 1 / Tier 2 boundary -- nothing executes until sign-off.

> **[CRITICAL] CONTEXT LOADING**
>
> 1. Load planning rules: `view_file .claude/rules/planning.md`
> 2. Load CDD governance: `view_file .claude/rules/cdd.md`
> 3. Load CDD depth (on demand): `.claude/references/cdd/principles.md`, `.claude/references/cdd/cdt-vs-impl-testing.md`
> 4. Load the Design Skill: `view_file .claude/skills/mini-spec/SKILL.md`
> 5. Load the PRD: `view_file plans/PRD.md`
> 6. Load the Roadmap: `view_file plans/roadmap.md`
> 7. Load existing canonical artifacts (if present): `plans/component-contracts.yaml`, `plans/seams.yaml`, `plans/symbols.yaml`, `plans/test-plan.yaml`, `interfaces/*.pyi`
> 8. Load symbol and test-plan references: `.claude/references/symbols-schema.md`, `.claude/references/test-plan-schema.md`

# WORKFLOW: IO-ARCHITECT

**Objective:** Produce the full behavioral and structural design for all features in `roadmap.md`. Canonical outputs:

- `plans/component-contracts.yaml` -- CRC, collaborators, file paths, feature mapping, protocol path, **per-method `MethodSpec` signatures**
- `plans/seams.yaml` -- integration graph, external terminals, failure modes
- `plans/symbols.yaml` -- every cross-CP identifier (Settings fields, exception classes, shared types, fixtures, error messages)
- `plans/test-plan.yaml` -- per-Protocol-method behavioral invariants

YAML is the authority in v3: `interfaces/*.pyi` is downstream of these four files, emitted by `/io-gen-protocols` from `ComponentContract.methods` + `symbols.yaml` after Step G approval. The architect authors no `.pyi` files directly.

Nothing is written to `plans/project-spec.md`. That artifact is a retired render target; no downstream agent reads it.

**Position in chain:**

```
/io-specify -> [/io-architect] -> /io-gen-protocols (emits interfaces/*.pyi)
            -> dispatch-testers.sh (per Protocol)
            -> /io-checkpoint -> /io-plan-batch -> /validate-tasks -> dispatch-agents.sh
```

**This workflow is the contract lock.** After human approval, the canonical YAML set is the binding source of truth. Sub-agents build against it. It is not modified during execution unless a formal replan is triggered.

---

## 1. STATE INITIALIZATION

Output the following metadata:

- **Roadmap status:** [roadmap.md present and complete?]
- **Existing canonical artifacts:** [list which of component-contracts/seams/symbols/test-plan exist]
- **Existing interfaces/*.pyi:** [list existing contracts, if any -- informational; the architect does not modify these]
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
  - They will be declared in `plans/symbols.yaml` as `kind: shared_type` entries with `declared_in: src/...` (Step H-6). Runtime type definitions live under `src/`; `/io-gen-protocols` re-exports them into `interfaces/*.pyi` when rendering Protocol surfaces.
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
- **Output:** Two edge sets held as reasoning artifacts for Step C. ACTUAL edges are the import relationships in current code; TARGET edges are the relationships implied by the Step C dependency map. Reconcile the two when proposing the target design; if they diverge, surface the divergence in the Step G approval summary.

---

### Step C: REASON THROUGH DEPENDENCY MAP

- **Goal:** Capture how components depend on each other across architectural layers.
- **Format:** Mermaid graph in your reasoning, not written to any file. The `collaborators:` field on each component in `component-contracts.yaml` is the canonical encoding of the same information.
- **Rules:**
  - Arrow direction = "depends on" (A -> B means A depends on B)
  - Higher layers may only depend on lower layers (no upward imports)
  - Cross-layer dependencies must go through an interface in `interfaces/`

---

### Step D: DESIGN CRC CARDS

For every component identified in Step B, design a CRC card using the format defined in the `mini-spec` skill (Section 2: CRC Card Standard).

- **Action:** Determine responsibilities, must_not constraints, collaborators, layer, and roadmap features for each component. This is a reasoning step -- the CRC data is written to `component-contracts.yaml` in Step H-2c.
- **Incremental runs:** Note which CRC cards are new or changed.

**[HARD] CRC budget caps.** A single component that absorbs too many behaviors, too many features, or too much composition wiring stops being a reviewable unit. Each CRC must satisfy all three caps; a violation forces decomposition, not a rewording.

- **Responsibility cap:** max 3 testable responsibilities per CRC. A component with 4+ responsibilities must be split.
- **Feature fan-out cap:** max 2 roadmap features per CRC. A component serving 3+ features from `plans/roadmap.md` must be split along feature boundaries. **Every component that carries feature logic MUST declare the feature IDs** (e.g., `F-01`, `F-02`) it supports -- they are written to the `features:` field in Step H-2c and are what the pre-gate reads. An empty `features:` is reserved for shared infrastructure that legitimately has no direct feature fan-out (e.g., `Settings`, loggers); the pre-gate emits a non-blocking warning if a behavioral component (has a Protocol or is a composition root) leaves `features:` empty, so A.1b cannot be silently bypassed by forgetting to declare.
- **Composition-root decomposition:** a `composition_root: true` component with 3+ Layer-2/3 collaborators (domain + infrastructure, excluding other composition roots) must decompose into resource-scoped sub-components -- one router/handler/sub-app per resource, each wiring at most 2 Layer-2/3 collaborators.

These caps are mechanically enforced by `.claude/scripts/validate_crc_budget.py` at Step G-pre before the human approval gate. Thresholds are defined as constants in that script for per-project tuning.

---

### Step F: REASON THROUGH INTERFACE REGISTRY

The Interface Registry (component -> protocol file -> layer) is now the set of `protocol:` and `file:` fields in `plans/component-contracts.yaml`. No separate Markdown table is written. At Step H-2c this information is captured in the YAML.

Every behavioral component must have:

- `file: src/...`
- `protocol: interfaces/[name].pyi` (omit for composition roots)

Composition roots do not have a Protocol. They are registered in `plans/component-contracts.yaml` only.

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

If the script exits non-zero, do NOT proceed to Step G. Revise the Step D design (decompose offending components, split feature fan-out, remove responsibilities) and re-run this step. The human never sees a design that has not cleared the pre-gate.

**On interruption.** Step G-pre writes the real `plans/component-contracts.yaml` before validation. If the workflow is interrupted (Ctrl-C, crash) between a failed validation and the revised rewrite, the repo is left with an over-budget contracts file on disk. Recover with `git checkout HEAD -- plans/component-contracts.yaml`, then re-run `/io-architect`. Equivalent to any interrupted write -- not a new class of risk.

---

### Step G: [HUMAN GATE] APPROVAL REQUIRED

Print only this compact summary to the terminal:

```
DESIGN PROPOSAL READY FOR REVIEW

Drafted for review:
  plans/component-contracts.yaml ([N] components, [N] methods total)

Open plans/component-contracts.yaml in your editor to inspect the CRC
design and per-method signatures. On approval, Step H writes the
remaining canonical YAML artifacts (symbols.yaml, test-plan.yaml)
and Step I generates seams.yaml + nav artifacts. `interfaces/*.pyi`
emission is handled separately by `/io-gen-protocols` after this
workflow exits.

Incremental run: review git diff against the last approved state.

Reply with approval to lock contracts, or describe any correction needed
(cite component name and field).
```

- **WAIT** for explicit human approval.
- If corrections requested: edit `plans/component-contracts.yaml` in place for the identified component only. Do not re-print the corrected content -- tell the user which lines were changed and ask them to re-read the file. Do not proceed to Step H until approved.

---

### Step H: WRITE ARTIFACTS

On approval, execute the following steps in strict sequence. Do NOT parallelize any of these steps.

**Step H-pre:** `bash: mkdir -p .iocane && touch .iocane/validating`

The sentinel prevents `reset-on-symbols-write.sh` and `reset-on-test-plan-write.sh` from firing during the canonical-YAML write sequence (Step H-6 and H-7). Step H-5 explicitly cleans it up. The architect no longer writes under `interfaces/` -- `reset-on-pyi-write.sh` and `design-before-contract.sh` are concerns of `/io-gen-protocols`, not this workflow.

**Step H-2:** Append `[[tool.importlinter.contracts]]` to `pyproject.toml`:

Derive contract structure from `component-contracts.yaml` (package file paths via `file: src/...`) + `seams.yaml` (layer assignments). `interfaces/*.pyi` contributes nothing to importlinter layer derivation -- it is Protocol stub surface, not runtime package structure.

- One `[[tool.importlinter.contracts]]` block for the layer hierarchy, ordered top-to-bottom (entrypoint -> domain -> utility -> foundation)
- Additional `[[tool.importlinter.contracts]]` blocks for any independence contracts between peer packages
- Remove the `# [[tool.importlinter.contracts]] populated by /io-architect` comment placeholder
- If `pyproject.toml` does not exist (brownfield adoption), create it from `.claude/templates/pyproject.toml` first, then append contracts

**Step H-2b:** Scaffold `src/` package directories from the Step F Interface Registry reasoning:

- For each registered package path, create the directory if it does not exist
- Write a minimal `__init__.py` (empty or with a module docstring) to each new directory
- Skip directories that already exist -- do not overwrite existing `__init__.py` files

**Step H-2c:** Write `plans/component-contracts.yaml` using `contract_parser.save_contracts()`:

- Build a `ComponentContractsFile` with one `ComponentContract` per component. Include structural, behavioral, roadmap, and **method-signature** fields:
  - **Structural:** `file: src/...` (implementation path), `collaborators: [...]` (from the CRC card, `[]` if none), `composition_root: true` (Entrypoint Layer only; omit for others)
  - **Behavioral:** `responsibilities: [...]` (from CRC card design in Step D), `must_not: [...]` (from CRC card design in Step D), `protocol: interfaces/[name].pyi` (the .pyi path, omit for composition roots)
  - **Roadmap:** `features: [F-XX, ...]` (roadmap feature IDs from `plans/roadmap.md` this component supports). Required for every component that carries feature logic. Empty is reserved for shared infrastructure without direct feature fan-out; the pre-gate emits a warning (not a failure) if a behavioral component leaves this empty, so the A.1b cap cannot be bypassed by omission.
  - **Method signatures** (`methods: list[MethodSpec]`): **[HARD]** every component with `protocol:` set MUST populate `methods` with at least one `MethodSpec`. Each entry carries `name` (lowercase identifier), `args: list[ArgSpec{name, type_expr, default?}]`, `return_type` (non-empty type expression), `raises: list[str]` (names referencing `exception_class` symbols in `symbols.yaml`), and `docstring`. The Raises list is the contract-authoritative record of every exception a Protocol method can propagate; `/io-gen-protocols` renders it into the `.pyi` docstring + `test-plan.yaml` `error_propagation` invariants must cover each name.
    - **Structurally enforced:** `ComponentContract.check_protocol_requires_methods` (Pydantic `@model_validator`) rejects `protocol` set with `methods: []`. Construction (`ComponentContract(...)`) and load (`ComponentContractsFile.model_validate(...)`) both fire the validator; `save_contracts()` round-trips its dump through `model_validate()` to catch state that became invalid between construction and save. Step H-post-validate runs `validate_symbols_coverage.py` against the union of `methods[*].raises` and `symbols.yaml` to close the cross-YAML reference loop.
    - **Concreteness:** parameter types and return types must be concrete -- no `Any`, no `dict` without type params. Consult `.claude/references/symbols-schema.md` for the identifier-safe rules that `ArgSpec`/`MethodSpec` validators enforce at parse time.
- Call `save_contracts()` to write -- this validates the model before serialization.
- Overwrite if the file already exists -- it is always regenerated from the current design. Note: Step G-pre may have already written a passing draft; this step re-writes so any corrections applied during the Step G human review are captured.

**Step H-6:** Write `plans/symbols.yaml` using `symbols_parser.save_symbols()`:

- For every cross-CP identifier that must be spelled and typed consistently across more than one checkpoint, add a `Symbol` entry. Consult `.claude/references/symbols-schema.md` for the `SymbolKind` catalogue.
- **Settings fields:** every attribute on a Pydantic `Settings` model that a downstream component will read. `kind: settings_field`, `type_expr`, `env_var`, optional `default`.
- **Exception classes:** every custom exception that crosses a Protocol boundary. `kind: exception_class`, `parent` (base class), `declared_in: src/...` (the runtime module that defines the class). The `check_declared_in_zone` validator rejects `interfaces/...` paths here -- runtime-bearing symbols live under `src/`; `/io-gen-protocols` re-exports them into `.pyi` stubs.
- **Shared types:** every dataclass / TypedDict / Pydantic model consumed by more than one CP. `kind: shared_type`, `type_expr` (shape summary), `declared_in: src/...`. Same zone rule as exception classes.
- **Fixtures:** every pytest fixture referenced by contract tests or integration tests across more than one CP. `kind: fixture`, `fixture_scope`.
- **Error messages:** any literal exception message whose wording is asserted by tests. `kind: error_message`, `message_pattern`.
- Populate `used_by:` with the COMPONENT NAMES (from CRC collaborator analysis) that reference each symbol. Do NOT populate `used_by_cps:` -- that field is checkpoint-backfilled at `/io-checkpoint` and stays empty until then.
- Conflict detection (`detect_env_var_conflicts`, `detect_message_pattern_conflicts`) runs at Step I-3 and at `/validate-plan`.

**Step H-7:** Write `plans/test-plan.yaml` using `test_plan_parser.save_test_plan()`:

- For every `ComponentContract.methods` entry authored in Step H-2c (including `__init__` where behavior is non-trivial), create a `TestPlanEntry` whose `protocol` is the owning component's `protocol: interfaces/<name>.pyi` path and whose `method` matches `MethodSpec.name`. YAML is the authority: the architect walks `component-contracts.yaml`, not any `.pyi` file on disk.
- Each entry carries one or more `TestInvariant` items with:
  - `id` in `INV-NNN` format (zero-padded, project-unique)
  - `kind` chosen from the `InvariantKind` catalogue: `call_binding`, `cardinality`, `error_propagation`, `state_transition`, `property`, `adversarial`
  - `description` -- a one-line behavioral claim
  - `pass_criteria` -- enough detail for the Test Author to write the test without reading the implementation
- **Rule:** every name in `ComponentContract.methods[*].raises` MUST have at least one `error_propagation` invariant under the owning Protocol's `test-plan.yaml` entry that names the raised type and the trigger. Gaps here are a contract-authoring error -- `validate_test_plan_completeness.py` catches them at Step H-post-validate.
- **Rule:** every Protocol postcondition (observable side effect, return shape constraint, state transition) SHOULD have at least one invariant covering it. Gaps are non-blocking at authoring time but are surfaced by `validate_test_plan_completeness.py` at `/validate-plan`.
- Consult `.claude/references/test-plan-schema.md` for the invariant taxonomy and worked examples.

**Step H-post-validate:** Run the deterministic coverage gates against the canonical artifacts you just authored. The architect IS the authority on these constraints; catching gaps here is when the fix is cheap (just edit the artifact you're holding in mind).

```bash
uv run python .claude/scripts/validate_symbols_coverage.py
uv run python .claude/scripts/validate_test_plan_completeness.py \
    --contracts plans/component-contracts.yaml
```

Exit-code policy:

- `validate_symbols_coverage.py` exits 1 on uncovered project-custom exceptions OR symbol conflicts. Stdlib and builtin exceptions are correctly skipped. On FAIL, return to Step H-6 and amend `plans/symbols.yaml` to declare the missing `exception_class` entries (or rename the conflicting env_var / message_pattern), then re-run this step.
- `validate_test_plan_completeness.py` exits 1 on Protocol methods with no `TestPlanEntry`. On FAIL, return to Step H-7 and author the missing entry, then re-run this step. No deferral mechanism exists at this stage: under v3 the architect has `ComponentContract.methods` in front of them when authoring `test-plan.yaml`, so every declared method is expected to receive at least one invariant.

A semantic review pass (whether invariants are tautological, whether Raises descriptions are specific enough, whether symbol classifications make sense) is queued as a Phase 5 deliverable: a separate Opus subprocess invoked here via `spawn-design-evaluator.sh` will emit OBSERVATION findings the architect responds to before declaring contracts locked. Until that ships, surface those judgements via your own self-review while drafting H-2c through H-7.

After both gates pass, stamp `plans/test-plan.yaml` with `validated: true`:

```bash
uv run python -c "
import sys
sys.path.insert(0, '.claude/scripts')
from test_plan_parser import load_test_plan, save_test_plan
tp = load_test_plan('plans/test-plan.yaml')
tp.validated = True
tp.validated_date = 'YYYY-MM-DD'
tp.validated_note = 'PASS at io-architect Step H-post-validate'
save_test_plan('plans/test-plan.yaml', tp)
"
```

The stamp lives with the architect because the architect is the only authority that can re-author the canonical artifacts when invariants drift. `/validate-plan` does NOT re-run this gate or re-stamp test-plan.yaml -- it trusts the architect's self-blessing because the reset-hook chain forces re-architect on any post-blessing mutation.

**Step H-5:** `bash: rm -f .iocane/validating`

Explicit sentinel cleanup. Remove whether or not the last write succeeded -- the alternative is a dangling sentinel that silently bypasses future gate enforcement.

**Output:**

```
CONTRACTS LOCKED.

component-contracts.yaml: [N] components, [N] methods
symbols.yaml:             [N] cross-CP symbols
test-plan.yaml:           [N] entries, [N] invariants

This is the Tier 1 / Tier 2 boundary.

Next:
  1. Run `/io-gen-protocols` to emit interfaces/*.pyi from
     component-contracts.yaml + symbols.yaml (YAML -> .pyi codegen).
  2. Run `dispatch-testers.sh` to run Test Author per Protocol in
     parallel (see Phase 6b orchestration) for contract tests under
     tests/contracts/.
  3. After tests are written cleanly, run /io-checkpoint.
```

---

### Step I: GENERATE NAVIGATION ARTIFACTS

After Step H, generate the remaining canonical artifacts. Step I-0 derives the integration seams (layer assignments require architect judgment). Steps I-2 and I-3 are mechanical.

**Step I-0: Update `plans/seams.yaml`.**

For each component added or modified in this architect run (identified from the `component-contracts.yaml` delta), update its entry in `plans/seams.yaml` using `seam_parser` functions:

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
- `layer`: assign based on component placement (1=Foundation, 2=Utility, 3=Domain, 4=Entrypoint). Components with `composition_root: true` belong at Layer 4.
- `backlog_refs`: leave empty -- backlog is populated by `/io-review`, not `/io-architect`

If `plans/seams.yaml` does not exist, create it from `.claude/templates/seams.yaml`.
Derive from the Step C-E reasoning only -- do not read source code.

**Step I-2: Regenerate directory-level CLAUDE.md files.**

Run the sync script:

```bash
uv run python .claude/scripts/sync_dir_claude.py
```

**Rule:** These files are generated artifacts -- the script overwrites them.
They must stay under 30 lines. If the script reports exit code 2 (line-count
exceeded), flag the directory as a `[DESIGN]` finding.

**Step I-3: [MECHANICAL POST-GATE] FILE-REFERENCE RESOLVABILITY + SYMBOL CONFLICTS.**

**Appendix A §A.6c (architect stage).** After all canonical YAML artifacts (component-contracts.yaml, seams.yaml, symbols.yaml, test-plan.yaml) are on disk, scan them plus PRD/roadmap for path references that do not resolve. `interfaces/*.pyi` does not exist yet at this stage (emitted post-workflow by `/io-gen-protocols`); path references to `interfaces/<name>.pyi` are expected to surface as OBSERVATION-severity `WARN:` lines on first run and resolve on the first `/io-gen-protocols` pass.

```bash
uv run python .claude/scripts/validate_path_refs.py --stage architect
```

The script uses `rg` with extension-anchored patterns (A.6a). For each extracted path it verifies resolution against (a) the filesystem, (b) any existing plan.yaml's `write_targets`, (c) any existing plan.yaml's `relies_on_existing`. Unresolved paths emit OBSERVATION-severity `WARN:` lines on stderr. Exit code is always 0 -- non-blocking by design.

Then run symbol conflict detection:

```bash
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

Surface the stderr output verbatim to the user. Any conflict is an authoring error -- fix by renaming or deduplicating and re-run Step H-6.

---

## 3. INCREMENTAL MODE (extending existing design)

If canonical artifacts already exist:

- **Read existing canonical YAMLs before proposing anything.** `component-contracts.yaml` (with `methods[*]`), `symbols.yaml`, `test-plan.yaml`, and `seams.yaml` are the authoritative surface; any existing `interfaces/*.pyi` files on disk are rendered downstream output, not input.
- **Identify conflicts:** Does the proposed new design contradict any existing `ComponentContract.methods` signature, symbol declaration, or test-plan invariant?
- **Flag breaking changes explicitly** -- any modification to an existing `MethodSpec` (name, args, return_type, raises), symbol kind, or invariant is a breaking change and requires separate human confirmation with explicit acknowledgment that downstream tests and implementations may need updating.
- **Additive changes** (new Protocols, new methods on existing Protocols, new symbols, new invariants) follow the standard plan mode flow above.
- **Sentinel-wrap all post-approval YAML edits.** Any write to `plans/symbols.yaml` or `plans/test-plan.yaml` outside an active `.iocane/validating` sentinel window triggers `reset-on-symbols-write.sh` / `reset-on-test-plan-write.sh`, which silently flip `test-plan.yaml.validated` back to `false`. Re-run the full Step H-pre (sentinel set) + targeted Step H-6/H-7 write + Step H-post-validate (re-stamp) + Step H-5 (sentinel clear) sequence for incremental corrections; do not patch individual fields outside the sentinel window.
- **Never silently modify** an existing `MethodSpec`, symbol, or invariant. Changes to `.pyi` surface come from re-running `/io-gen-protocols` after the YAML edit -- hand-editing the `.pyi` is blocked by `interfaces-codegen-only.sh` and reverts on the next codegen run regardless.

---

## 4. CONSTRAINTS

- No implementation code in this workflow.
- No task file, `plan.yaml`, or `roadmap.md` edits.
- No writes to `plans/project-spec.md` -- that artifact is retired.
- No writes under `interfaces/` -- `interfaces-codegen-only.sh` will block them. `.pyi` emission is `/io-gen-protocols`' responsibility.
- `plans/component-contracts.yaml` + `plans/symbols.yaml` + `plans/test-plan.yaml` are binding contracts. They are the source of truth for sub-agent execution; `.pyi` surface is rendered output.
- The human's approval at Step G is the point of no return for Tier 2 delegation.
- **Appendix A §A.6e -- Grep-verify paths before writing.** Before writing any file path into any canonical artifact, use the Grep tool to verify the path either (a) already exists on disk, (b) traces to an upstream artifact (PRD, roadmap), or (c) is a declared output of this architect run. Paths authored from memory are a recurring defect class. The Step I-3 mechanical gate catches unresolved references non-blockingly, but authoring discipline is the primary defense.

> `[HARD] Evidence citation rule:` Any spec claim citing existing code must include an explicit `file:line` citation. The architect must read the cited line before writing the claim. Uncited claims about existing code are forbidden.

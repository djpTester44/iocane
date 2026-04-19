---
name: io-architect
description: Design CRC cards, Protocols, cross-CP symbols, and per-method behavioral invariants. Tier 1 -- plan mode required. Highest-value gate in the workflow.
---

> **[CRITICAL] PLAN MODE**
> This is the highest-value gate in the entire workflow.
> Claude authors the full design as canonical YAML + `.pyi` artifacts for human review.
> The `.pyi` files are written at Step H; the YAML artifacts are written before.
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

- `plans/component-contracts.yaml` -- CRC, collaborators, file paths, feature mapping, protocol path
- `interfaces/*.pyi` -- Protocol signatures, shared types, exceptions, per-method Raises/docstrings
- `plans/seams.yaml` -- integration graph, external terminals, failure modes
- `plans/symbols.yaml` -- every cross-CP identifier (Settings fields, exception classes, shared types, fixtures, error messages)
- `plans/test-plan.yaml` -- per-Protocol-method behavioral invariants

Nothing is written to `plans/project-spec.md`. That artifact is a retired render target; no downstream agent reads it.

**Position in chain:**

```
/io-specify -> [/io-architect] -> dispatch-testers.sh (per Protocol)
            -> [architect amend sub-loop if AMEND signals emitted]
            -> /io-checkpoint -> /io-plan-batch -> /validate-tasks -> dispatch-agents.sh
```

**This workflow is the contract lock.** After human approval, the canonical set is the binding source of truth. Sub-agents build against it. It is not modified during execution unless a formal replan is triggered OR the Test Author emits `ARCHITECT_AMEND` signals.

---

## 1. STATE INITIALIZATION

**[HARD] Forced AMEND detection.** Before classifying mode, run:

```bash
ls .iocane/amend-signals/ 2>/dev/null | head -n 1
```

If any signal file exists, **Mode is forced to Amend** for this run. You
MUST proceed via Section 4 (AMEND MODE) and MUST NOT execute Greenfield
or Incremental flow -- doing so silently overwrites in-flight amend
state, drops the architect into a fresh design, and breaks the retry
counter on the signal files. Forced AMEND is non-negotiable: the
operator's only legitimate way to bypass it is to delete
`.iocane/amend-signals/` themselves with a rationale (e.g., the signals
were stale from a prior aborted run).

After the forced-AMEND check, output the following metadata:

- **Roadmap status:** [roadmap.md present and complete?]
- **Existing canonical artifacts:** [list which of component-contracts/seams/symbols/test-plan exist]
- **Existing interfaces/*.pyi:** [list existing contracts, if any]
- **Amend signals present:** [yes (count, list protocols) | no]
- **Mode:** [Greenfield | Incremental | Amend (FORCED if amend signals exist)]

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
  - They will be defined in `interfaces/models.pyi` (Step E)
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

**Shared-type exemption:** `interfaces/models.pyi` and `interfaces/exceptions.pyi` hold contract vocabulary, not behavioral components -- they are not CRC cards and the caps do not apply. Mirrors the carve-out in `hooks/design-before-contract.sh`.

These caps are mechanically enforced by `.claude/scripts/validate_crc_budget.py` at Step G-pre before the human approval gate. Thresholds are defined as constants in that script for per-project tuning.

---

### Step E: DESIGN PROTOCOL SIGNATURES (reasoning)

For every CRC card, design the corresponding Protocol interface as a reasoning artifact. Protocol files are NOT written yet -- Step H-3 writes them after approval.

**First: define shared domain types.**

Identify all domain types (value objects, DTOs, enums) referenced across Protocol method parameters and return types. Design these as `.pyi` stubs for `interfaces/models.pyi`.

For brownfield projects: derive type definitions from the design in Steps B-D, not from existing `src/` code. The types in `interfaces/models.pyi` are the contract-level vocabulary -- they may differ from current runtime implementations.

**Protocol template:**

```python
# interfaces/[protocol].pyi

from typing import Protocol
from interfaces.models import [RelevantTypes]

class [ProtocolName](Protocol):
    def [method_name](self, [params]: [Types]) -> [ReturnType]:
        """
        [Docstring: what this method does, not how]

        Raises:
            [Every domain exception this method can raise, with trigger
            condition. If the method is total, write: "None. Total function."]
        """
        ...
```

**Rules for Protocol design:**

- Every CRC responsibility maps to at least one method.
- Parameters and return types must be concrete -- no `Any`, no `dict` without type params.
- Methods must be testable in isolation -- no side-effectful signatures that cannot be mocked.
- Protocols describe behavior at the boundary, not implementation details.
- **[HARD] Raises clause is mandatory per method.** Either declare the raised types with their triggers, or explicitly declare "None. Total function." Leaving Raises blank is a contract-authoring error; Test Author will emit `ARCHITECT_AMEND` because error_propagation invariants cannot be enforced against an unwritten Raises clause.
- **[HARD] Self-containment:** Protocol `.pyi` files must not import from `src/`. All domain types must be defined in `interfaces/models.pyi`. All custom exceptions in `interfaces/exceptions.pyi`. The `interfaces/` package is the complete contract surface with no dependencies beyond the standard library and `typing`.

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
- **A.1e:** components whose protocol is `interfaces/models.pyi` or `interfaces/exceptions.pyi` are skipped.

If the script exits non-zero, do NOT proceed to Step G. Revise the Step D design (decompose offending components, split feature fan-out, remove responsibilities) and re-run this step. The human never sees a design that has not cleared the pre-gate.

**On interruption.** Step G-pre writes the real `plans/component-contracts.yaml` before validation. If the workflow is interrupted (Ctrl-C, crash) between a failed validation and the revised rewrite, the repo is left with an over-budget contracts file on disk. Recover with `git checkout HEAD -- plans/component-contracts.yaml`, then re-run `/io-architect`. Equivalent to any interrupted write -- not a new class of risk.

---

### Step G: [HUMAN GATE] APPROVAL REQUIRED

Print only this compact summary to the terminal:

```
DESIGN PROPOSAL READY FOR REVIEW

Canonical artifacts written:
  plans/component-contracts.yaml ([N] components)
  (pending Step H-3:   interfaces/*.pyi -- [N] Protocols, models, exceptions)
  (pending Step H-6:   plans/symbols.yaml -- [N] cross-CP symbols)
  (pending Step H-7:   plans/test-plan.yaml -- [N] Protocol-method invariants)

Open plans/component-contracts.yaml in your editor to inspect the CRC
design. The remaining canonical artifacts write at Step H.

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

The sentinel prevents `reset-on-pyi-write.sh`, `reset-on-symbols-write.sh`, `reset-on-test-plan-write.sh`, and `design-before-contract.sh` from firing during the canonical-artifact write sequence. It must be set before Step H-3. Step H-5 explicitly cleans it up.

**Step H-2:** Append `[[tool.importlinter.contracts]]` to `pyproject.toml`:

- One `[[tool.importlinter.contracts]]` block for the layer hierarchy, ordered top-to-bottom (entrypoint -> domain -> utility -> foundation)
- Additional `[[tool.importlinter.contracts]]` blocks for any independence contracts between peer packages
- Remove the `# [[tool.importlinter.contracts]] populated by /io-architect` comment placeholder
- If `pyproject.toml` does not exist (brownfield adoption), create it from `.claude/templates/pyproject.toml` first, then append contracts

**Step H-2b:** Scaffold `src/` package directories from the Step F Interface Registry reasoning:

- For each registered package path, create the directory if it does not exist
- Write a minimal `__init__.py` (empty or with a module docstring) to each new directory
- Skip directories that already exist -- do not overwrite existing `__init__.py` files

**Step H-2c:** Write `plans/component-contracts.yaml` using `contract_parser.save_contracts()`:

- Build a `ComponentContractsFile` with one `ComponentContract` per component. Include structural, behavioral, and roadmap fields:
  - **Structural:** `file: src/...` (implementation path), `collaborators: [...]` (from the CRC card, `[]` if none), `composition_root: true` (Entrypoint Layer only; omit for others)
  - **Behavioral:** `responsibilities: [...]` (from CRC card design in Step D), `must_not: [...]` (from CRC card design in Step D), `protocol: interfaces/[name].pyi` (the .pyi path, omit for composition roots)
  - **Roadmap:** `features: [F-XX, ...]` (roadmap feature IDs from `plans/roadmap.md` this component supports). Required for every component that carries feature logic. Empty is reserved for shared infrastructure without direct feature fan-out; the pre-gate emits a warning (not a failure) if a behavioral component leaves this empty, so the A.1b cap cannot be bypassed by omission.
- Call `save_contracts()` to write -- this validates the model before serialization
- Overwrite if the file already exists -- it is always regenerated from the current design. Note: Step G-pre may have already written a passing draft; this step re-writes so any corrections applied during the Step G human review are captured.

**Step H-3:** Write `interfaces/*.pyi`:

- `interfaces/models.pyi` -- domain type stubs, exactly as designed in Step E
- `interfaces/exceptions.pyi` -- exception hierarchy (if any)
- One `.pyi` file per Protocol, exactly as designed in Step E
- **Every Protocol method must have a `Raises:` clause.** Either list the raised exception types with triggers, or write exactly "None. Total function." Blank Raises blocks are a contract-authoring error.
- Include docstrings on every method in Protocol files

**Step H-6:** Write `plans/symbols.yaml` using `symbols_parser.save_symbols()`:

- For every cross-CP identifier that must be spelled and typed consistently across more than one checkpoint, add a `Symbol` entry. Consult `.claude/references/symbols-schema.md` for the `SymbolKind` catalogue.
- **Settings fields:** every attribute on a Pydantic `Settings` model that a downstream component will read. `kind: settings_field`, `type_expr`, `env_var`, optional `default`.
- **Exception classes:** every custom exception that crosses a Protocol boundary. `kind: exception_class`, `parent` (base class), `declared_in: interfaces/exceptions.pyi`.
- **Shared types:** every dataclass / TypedDict / Pydantic model consumed by more than one CP. `kind: shared_type`, `type_expr` (shape summary).
- **Fixtures:** every pytest fixture referenced by contract tests or integration tests across more than one CP. `kind: fixture`, `fixture_scope`.
- **Error messages:** any literal exception message whose wording is asserted by tests. `kind: error_message`, `message_pattern`.
- Populate `used_by:` with the COMPONENT NAMES (from CRC collaborator analysis) that reference each symbol. Do NOT populate `used_by_cps:` -- that field is checkpoint-backfilled at `/io-checkpoint` and stays empty until then.
- Conflict detection (`detect_env_var_conflicts`, `detect_message_pattern_conflicts`) runs at Step I-3 and at `/validate-plan`.

**Step H-7:** Write `plans/test-plan.yaml` using `test_plan_parser.save_test_plan()`:

- For every Protocol method in `interfaces/*.pyi` (including `__init__` where behavior is non-trivial), create a `TestPlanEntry`.
- Each entry carries one or more `TestInvariant` items with:
  - `id` in `INV-NNN` format (zero-padded, project-unique)
  - `kind` chosen from the `InvariantKind` catalogue: `call_binding`, `cardinality`, `error_propagation`, `state_transition`, `property`, `adversarial`
  - `description` -- a one-line behavioral claim
  - `pass_criteria` -- enough detail for the Test Author to write the test without reading the implementation
- **Rule:** every `Raises:` clause on a Protocol method MUST have at least one `error_propagation` invariant that names the raised type and the trigger. The Test Author emits `ARCHITECT_AMEND` if a declared Raises has no covering invariant.
- **Rule:** every Protocol postcondition (observable side effect, return shape constraint, state transition) SHOULD have at least one invariant covering it. Gaps are non-blocking at authoring time but are surfaced by `validate_test_plan_completeness.py` at `/validate-plan`.
- Consult `.claude/references/test-plan-schema.md` for the invariant taxonomy and worked examples.

**Step H-post-validate:** Run the deterministic coverage gates against the canonical artifacts you just authored. The architect IS the authority on these constraints; catching gaps here is when the fix is cheap (just edit the artifact you're holding in mind).

```bash
uv run python .claude/scripts/validate_symbols_coverage.py
uv run python .claude/scripts/validate_test_plan_completeness.py
```

Exit-code policy:

- `validate_symbols_coverage.py` exits 1 on uncovered project-custom exceptions OR symbol conflicts. Stdlib and builtin exceptions are correctly skipped. On FAIL, return to Step H-6 and amend `plans/symbols.yaml` to declare the missing `exception_class` entries (or rename the conflicting env_var / message_pattern), then re-run this step.
- `validate_test_plan_completeness.py` exits 1 on Protocol methods with no `TestPlanEntry`. On FAIL, return to Step H-7 and either author the missing entry OR add `# noqa: TEST_PLAN` to the offending method's `def` line in the .pyi (with a comment explaining the deferral), then re-run this step.

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

component-contracts.yaml: [N] components
interfaces/*.pyi:         [N] Protocols + models + exceptions
symbols.yaml:             [N] cross-CP symbols
test-plan.yaml:           [N] entries, [N] invariants

This is the Tier 1 / Tier 2 boundary.
Test Author will now write contract tests in tests/contracts/
against these Protocols. If any Protocol is silent on a declared
invariant, Test Author emits ARCHITECT_AMEND and this workflow
re-enters Step H to amend.

Next: dispatch-testers.sh runs Test Author per Protocol in parallel
(see Phase 6b orchestration). After tests are written cleanly,
run /io-checkpoint.
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

**Appendix A §A.6c (architect stage).** After all canonical artifacts (component-contracts.yaml, seams.yaml, symbols.yaml, test-plan.yaml, interfaces/*.pyi) are on disk, scan them plus PRD/roadmap for path references that do not resolve:

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

- **Read existing canonical YAMLs and .pyi files before proposing anything.**
- **Identify conflicts:** Does the proposed new design contradict any existing Protocol signature, symbol declaration, or test-plan invariant?
- **Flag breaking changes explicitly** -- any modification to an existing `.pyi` signature, symbol kind, or invariant is a breaking change and requires separate human confirmation with explicit acknowledgment that downstream tests and implementations may need updating.
- **Additive changes** (new Protocols, new methods on existing Protocols, new symbols, new invariants) follow the standard plan mode flow above.
- **Never silently modify** an existing `.pyi` signature, symbol, or invariant.

---

## 4. AMEND MODE (re-entered from Test Author AMEND signals)

When `dispatch-testers.sh` reports that one or more `.iocane/amend-signals/<protocol>.yaml` files exist, re-enter this workflow to amend. The re-entry is bounded by `architect.amend_retries` in `iocane.config.yaml` (default 2); exceeding the cap raises a `DESIGN` escalation instead of another pass.

**Amend procedure:**

> **[HARD] Additive-only assumption.** The five AMEND signal kinds
> (`missing_raises`, `silent_return_semantics`, `missing_precondition`,
> `undeclared_collaborator`, `symbol_gap`) are intentionally additive
> -- they CLARIFY existing behavior, not redefine it. If your amend
> changes the SHAPE of a `shared_type`, the SIGNATURE of an existing
> Protocol method, or the WORDING of an `error_message` symbol, treat
> it as a breaking change, not an amend: HALT the AMEND mode, surface
> the divergence, and route through INCREMENTAL MODE (Section 3) so
> dependent Protocols and tests are flagged for human review.
> Re-dispatching only the amended Protocol when the change cascades
> would silently invalidate sibling test files.

1. Read each signal file under `.iocane/amend-signals/`.
2. **[HARD GATE] Consume each signal through the retry-counter authority.** For every signal stem, invoke:

   ```bash
   uv run python .claude/scripts/handle_amend_signal.py --consume <stem>
   ```

   The script is the sole writer of `.iocane/amend-attempts.<stem>`, the authoritative retry counter. On each call it increments the sidecar, rewrites the signal YAML's `attempt` field to match, and exits:
   - `0` -- increment succeeded, counter still within `architect.amend_retries`.
   - `2` -- counter exceeded cap; the script has already appended a `DESIGN` backlog entry with the full signal payload. **HALT AMEND mode immediately**, do NOT apply any amendments, do NOT set the validating sentinel. The Protocol is genuinely under-specified and needs human design input.

   Do not read the `attempt` field on the signal YAML directly -- it is informational, populated by `--consume` to surface current attempt count to humans. The counter authority lives in the sidecar, not the YAML. If any `--consume` call returns exit 2, record which stem(s) escalated and terminate this run.
3. **Set the validating sentinel before any artifact write:** `bash: mkdir -p .iocane && touch .iocane/validating`
   The sentinel is mandatory for AMEND writes for the same reason it is mandatory in Step H-pre: amend writes touch `interfaces/*.pyi`, `plans/symbols.yaml`, and `plans/test-plan.yaml`, and without the sentinel the reset hooks fire on every write and `design-before-contract.sh` blocks the first .pyi edit for any newly-introduced Protocol method (test-plan.yaml for the new method does not exist until step 4 below completes).
4. For each signal, apply the `suggested_amendment` (or a design-equivalent one) to the specific artifact named:
   - `missing_raises` -> amend the `Raises:` clause in the corresponding `interfaces/<protocol>.pyi` method (Step H-3 again, scoped to this file)
   - `silent_return_semantics` -> amend the `Returns:` docstring or add a postcondition invariant (Step H-3 + H-7 for the covering invariant)
   - `missing_precondition` -> amend Protocol docstring with the `@pre` clause (Step H-3) and add a corresponding invariant (Step H-7)
   - `undeclared_collaborator` -> update `collaborators:` in `component-contracts.yaml` (Step H-2c) and add the missing `argument_convention` or related symbol (Step H-6)
   - `symbol_gap` -> add the missing symbol to `plans/symbols.yaml` (Step H-6)
5. **Clear the validating sentinel after the last write:** `bash: rm -f .iocane/validating`
6. Delete the signal files after amend: `rm -rf .iocane/amend-signals/`. This wipes the signals but leaves the `.iocane/amend-attempts.*` sidecars intact -- the retry budget survives across amend passes until the tester re-runs cleanly (and the orchestrator calls `handle_amend_signal.py --clear <stem>`).
7. Re-dispatch Test Author for only the amended Protocols via `dispatch-testers.sh --only <protocol>...` (Phase 6b). In the interim (Phase 3), re-dispatch manually via `bash .claude/scripts/spawn-tester.sh --protocol <stem>` per stem.

---

## 5. CONSTRAINTS

- No implementation code in this workflow.
- No task file, `plan.yaml`, or `roadmap.md` edits.
- No writes to `plans/project-spec.md` -- that artifact is retired.
- Protocol files are binding contracts. They are the source of truth for sub-agent execution.
- The human's approval at Step G is the point of no return for Tier 2 delegation.
- **Appendix A §A.6e -- Grep-verify paths before writing.** Before writing any file path into any canonical artifact, use the Grep tool to verify the path either (a) already exists on disk, (b) traces to an upstream artifact (PRD, roadmap), or (c) is a declared output of this architect run. Paths authored from memory are a recurring defect class. The Step I-3 mechanical gate catches unresolved references non-blockingly, but authoring discipline is the primary defense.

> `[HARD] Evidence citation rule:` Any spec claim citing existing code must include an explicit `file:line` citation. The architect must read the cited line before writing the claim. Uncited claims about existing code are forbidden.

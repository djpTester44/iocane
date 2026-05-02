---
name: io-checkpoint
description: Decompose roadmap features into atomic checkpoints with connectivity test signatures. Tier 1 — plan mode required.
---

> **[CRITICAL] PLAN MODE**
> Claude PROPOSES `plan.yaml` content before writing anything.
> Human approves checkpoint boundaries and connectivity test signatures before any orchestration begins.

> **[CRITICAL] CONTEXT LOADING**
>
> 1. Load planning rules: `view_file .claude/rules/planning.md`
> 2. Load CDD governance: `view_file .claude/rules/cdd.md`
> 3. Load the component registry: `view_file plans/component-contracts.yaml`
> 4. Load the Roadmap: `view_file plans/roadmap.md`
> 5. Load the symbol registry: `symbols_parser.load_symbols('plans/symbols.yaml')`. Symbol names referenced by checkpoint scopes (component names) drive the `used_by_cps` backfill at Step G-symbols below.
> 6. Load the Integration Seams reference via `seam_parser.load_seams('plans/seams.yaml')`. Use the `injected_contracts` graph (via `all_di_edges()`) to identify which component boundaries require connectivity tests: if CP-A builds a component and CP-B builds a component that injects it, a connectivity test is required at that seam. For components whose `component-contracts.yaml` entry has `composition_root: true`, also read `injected_contracts` -- Appendix A §A.3b populates that list with injected contract names, which drives the A.3c composition-root CT emission rule in Step D.

# WORKFLOW: IO-CHECKPOINT

**Objective:** Decompose every feature in `roadmap.md` into atomic, independently-testable checkpoints. Define connectivity test signatures at every seam between dependent checkpoints. Write `plans/plan.yaml`.

**Position in chain:**

```
/io-architect -> [/io-checkpoint] -> /validate-plan -> /io-plan-batch -> /validate-tasks -> dispatch-agents.sh
```

**Definition of an atomic checkpoint:**
A unit of functionality that:

- Maps to one or more behavioral units of a component contract
- Can pass its own tests independently, without requiring other checkpoints to be complete
- Is small enough to be executed by a single sub-agent session without context pressure
- Has a clear, verifiable gate command

---

## 1. STATE INITIALIZATION

Before proceeding, output the following metadata:

- **Roadmap features:** [N features identified]
- **Component contracts:** [N entries in component-contracts.yaml]
- **Existing plan.yaml:** [Present / Not present]
- **Mode:** [Greenfield | Extending existing plan]

**Remediation mode:** When invoked with backlog items as scope (rather than
roadmap features), generate a remediation checkpoint (`CP-NNR`) for each item:

- Use naming convention `CP-{parent}R{N}` (e.g., CP-06R1, CP-06R2). Check
  existing `plans/plan.yaml` for entries matching `CP-{parent}R*` and increment
  `N` to avoid naming collisions with previously generated remediation CPs.
  Use: `uv run python -c "import sys; sys.path.insert(0,'.claude/scripts'); from plan_parser import load_plan; plan=load_plan('plans/plan.yaml'); print([cp.id for cp in plan.checkpoints])"`
- Include `remediates: CP-NN` field in the checkpoint entry
- Include `source: "plans/backlog.yaml (From CP-NN -- YYYY-MM-DD)"` field
- Include `source_bl: [BL-NNN]` field — list of backlog item IDs
- Include `severity: HIGH | MEDIUM | LOW` field — inherit from the source
  backlog item's severity
- Include `status: pending` field
- Derive write targets from the backlog item's `Files:` field plus the parent
  CP's test files
- **[HARD] Forward-target guard:** Before finalising write targets, check whether
  each candidate file is owned by a pending roadmap checkpoint (present in another
  CP's `write_targets` in `plan.yaml`, or not yet existing but clearly scoped to a
  future CP). If so, exclude it — that checkpoint is responsible for implementing
  its own CRC requirements. Do not bundle forward-checkpoint work into a remediation
  CP. If a CRC update implies a behaviour change in a pending checkpoint's files,
  add a note to that checkpoint's description; do not create a cross-checkpoint
  write dependency.
- Inherit gate command from the parent CP
- Do not make parallelizability claims — leave for `/io-plan-batch`
- Append remediation checkpoints to the `checkpoints` list in `plans/plan.yaml`,
  ordered by severity (HIGH first, then MEDIUM, then LOW) within the remediation
  group. Use `add_checkpoint()` from `plan_parser` or append directly to the YAML
  list. The `remediates:` field distinguishes remediation CPs from roadmap CPs.
- After writing the checkpoint to `plans/plan.yaml`, run:
  `bash .claude/scripts/route_backlog_item.py BL-NNN CP-NNR --prompt "ROUTING_PROMPT"`
  where `BL-NNN` is the backlog item's ID from the `**Source BL:**` field and
  `ROUTING_PROMPT` is the full routing command text (stored in the annotation).

---

## 2. PROCEDURE

### Step A: [HARD GATE] CONTRACTS LOCKED

- **Action:** Verify the canonical artifact set is on disk:
  - `plans/component-contracts.yaml` (CRC + collaborators)
  - `plans/symbols.yaml` (cross-CP identifier registry)
  - `plans/seams.yaml` (DI graph + external terminals)
- **Rule:** If any artifact is missing, HALT.
- **Output:** "HALT: Contracts not locked. Run `/io-architect` first."

---

### Step B: DECOMPOSE FEATURES INTO CHECKPOINTS

For each feature in `roadmap.md`:

- **Read** the feature's acceptance criteria and `depends_on` list.
- **Read** the CRC entries in `plans/component-contracts.yaml` for all components involved in this feature.
- **Identify** the behavioral units of work implied by the CRC responsibilities.
- **Group** related functions into the smallest independently-testable unit.

**Acceptance criteria:** Each checkpoint must include 2-4 observable, testable assertions as `acceptance_criteria`. These are design-time decisions -- they flow directly into the task file and must not be synthesized at batching time. The `contract` field is the primary `.pyi` file from the checkpoint's scope.

**[HARD] Raises coverage:** For each component contract in the checkpoint's scope, every exception in the contract's raises list must appear as an acceptance criterion, or be explicitly annotated as `[DEFERRED: justification]` in the acceptance criteria list. The agent loads `plans/component-contracts.yaml` (instruction 3) and has `seams.yaml` available (instruction 7) -- cross-reference both. A `key_failure_modes` entry in `seams.yaml` that names an exception in the contract's raises list reinforces the requirement. Missing coverage is a gap the evaluator cannot catch downstream because it grades only against the criteria authored here.

**Appendix A §A.6d `relies_on_existing`:** When an acceptance criterion names a path that already exists on disk (e.g., a golden fixture the CP must not regress, a baseline test file that must continue to pass, a vendored dataset under `data/`), add that path to the checkpoint's `relies_on_existing: list[str]` field. Before writing, **use the Grep tool** to verify the path exists -- do not author paths from memory. `relies_on_existing` suppresses A.6 orphan warnings in `/validate-plan` Step 9D for artifacts the CP depends on but does not produce. A path that belongs in `write_targets` (the CP produces it) must not appear in `relies_on_existing`.

**Decomposition rules:**

- One checkpoint = one component's core behavior, OR one well-defined integration seam
- A checkpoint must not span multiple architectural layers unless the seam between them is exactly what's being tested
- If a component has 5 behavioral units and they can all be built and tested as a unit → one checkpoint
- If behavioral units A and B must exist before unit C can be meaningfully tested → separate checkpoints

**Output:** Flat checkpoint inventory with feature mapping. Present before continuing.

---

### Step C: BUILD CHECKPOINT DEPENDENCY GRAPH

For each checkpoint pair, determine:

- Does checkpoint B require checkpoint A's gate to be green before B can begin?
- Can B and A be built concurrently in separate worktrees without write target conflicts?

**Collision validation rule:**
Two checkpoints MAY be marked parallel ONLY IF their `write_targets` are completely disjoint.
Flag any proposed parallel pair that shares a write target as a conflict — split the checkpoint before proceeding.

**Output:** Dependency graph showing which checkpoints are sequential vs. parallelizable.

---

### Step D: [PLAN MODE] PROPOSE CONNECTIVITY TEST SIGNATURES

At every seam between a checkpoint and its dependent(s), define a connectivity test signature.

A connectivity test verifies that the output of checkpoint A satisfies the input contract expected by checkpoint B. It is NOT built yet — only the signature is defined here.

**Format for each connectivity test:**

```markdown
## Connectivity: [CP-ID-A] → [CP-ID-B]

test_id: CT-[NNN]
function: test_[descriptive_name]
file: tests/connectivity/test_[cp_a]_[cp_b].py
fixture_deps: [mock_[source_protocol], spy_[source_protocol], ...]
contract_under_test: interfaces/[protocol].pyi :: [ProtocolName].[method_name]
assertion: [Three observables, each phrased against the seam:
  1. Call binding -- which upstream method is invoked and with which argument(s)
     (keywords: called, invoke/invoked/invokes, with argument, passes, passed to).
  2. Call cardinality -- how many times the upstream is invoked
     (keywords: once, exactly, per, times, each, for every).
  3. Error propagation -- behaviour when the upstream raises each declared
     exception (keywords: raises, propagates, re-raises, error, exception).
  Every declared exception on the source side of the seam must be named
  here OR annotated ``[DEFERRED: <reason>]`` inline. No implementation detail.]
gate: pytest tests/connectivity/test_[cp_a]_[cp_b].py::[function_name]
```

**CT file ownership:** The CT file is owned by `target_cp` (the downstream checkpoint, CP-B in the `CP-A → CP-B` seam). `target_cp` is responsible for creating the test file during its execution phase. `source_cps` provide the dependency context — their output must exist for the test to pass — but they do not write the CT file and must NOT include it in their `write_targets` or `gate_command`.

**Rules for connectivity test signatures:**

- The assertion must be precise enough that `/io-execute` can build the test without ambiguity
- The assertion describes the observable contract boundary — return type, key invariants, no ORM types leaking through domain layer, etc.
- **[HARD] Three-observable assertion (A.4a).** Every assertion must name all three seam-level observables: (1) **call binding** -- which upstream contract surface the downstream invokes and with what argument(s); (2) **call cardinality** -- how many times the upstream is called per downstream operation; (3) **error propagation** -- what the downstream does when the upstream raises each of its declared exceptions. Each exception in the source contract's raises list must be named in the assertion OR explicitly annotated `[DEFERRED: <reason>]`. An assertion that only checks return type/shape is an identity CT and is rejected. The schema-level lexical validator (`ct_assertion_warnings` in `scripts/schemas.py`) surfaces missing keywords as non-blocking warnings under `/validate-plan`.
- **[HARD] Spy-capable fixtures (A.4b).** `fixture_deps` must include, for every source contract on the seam, a `MagicMock`-based or spy-capable stub (e.g., `unittest.mock.MagicMock`, `pytest-mock`'s `mocker.spy`, or a hand-rolled stub that records calls and arguments). Identity-only fixtures -- a plain function returning a fixed value, or a dataclass with no call-recording surface -- are **insufficient**: call binding and cardinality cannot be observed against them and the three-observable assertion becomes unenforceable. A fixture entry like `stub_geocoder_returning_location` is a rejection signal; the correct form is `mock_geocoder_client` (with the expectation that the fixture exposes `.called`, `.call_args`, `.call_count`, or equivalent).
- **[HARD] Composition-root DI seams (A.3c).** For every component whose `component-contracts.yaml` entry has `composition_root: true`, emit one connectivity test per contract in its `seams.yaml` `injected_contracts` list. Each such CT must substitute a spy-capable stub for the injected contract via the framework's DI override surface:
  - **FastAPI composition roots:** `app.dependency_overrides[<ProtocolProvider>] = lambda: mock` inside the test fixture. The assertion observes the composition-root handler exercising the injected contract -- call binding names the contract surface invoked, cardinality counts invocations per request, and error propagation covers each exception in the contract's raises list converting to the documented HTTP status or domain response.
  - **Typer composition roots:** override via the resolved DI callable (e.g., swap the provider factory registered on the Typer app) or supply a substitute through the `typer.Context` dependency surface, depending on how the root wires providers. The assertion observes the CLI command exercising the injected contract with the same three observables.
  If a `composition_root: true` component's `injected_contracts` is empty in `plans/seams.yaml`, the architect underspecified the DI graph. HALT and route back to `/io-architect` rather than proceeding with partial CT coverage.
- `fixture_deps` must name real fixtures or factories that will exist after CP-A is complete
- Every dependency edge in the checkpoint graph must have at least one connectivity test
- The CT test file is a write target of `target_cp` only. Source checkpoints must NOT include the CT file in their `write_targets` or `gate_command`.
- The downstream checkpoint's **gate command** MUST include the CT file path from the `file:` field (i.e., the `target_cp` checkpoint). If the CT file does not exist at execution time, the gate will fail — this is intentional. Example: if CT-001 verifies the CP-01→CP-02 seam, CP-02's gate command must be `uv run rtk test pytest tests/domain/test_dag_resolver.py tests/connectivity/test_cp01_cp02.py`, not just `uv run rtk test pytest tests/domain/test_dag_resolver.py`.

**Present all connectivity test signatures. Do not write any file yet.**

---

### Step E: [PLAN MODE] PROPOSE PLAN.YAML

Propose the full content of `plans/plan.yaml`. The output must be valid YAML conforming to the Plan schema in `.claude/scripts/schemas.py`:

```yaml
generated_from:
  - plans/roadmap.md
  - plans/component-contracts.yaml
  - plans/symbols.yaml
validated: false
checkpoints:
  - id: CP-01
    title: "[Checkpoint Name]"
    feature: "F-01 -- [Feature name from roadmap.md]"
    description: "[One sentence -- what is built and testable when complete]"
    status: pending
    scope:
      - component: "[ComponentName]"
        methods:
          - "[method_name]"
    write_targets:
      - "src/[path]/[module].py"
      - "tests/[path]/test_[module].py"
    context_files:
      - "plans/component-contracts.yaml (CRC card for [ComponentName] only)"
      - "plans/symbols.yaml (filtered to symbols whose used_by contains [ComponentName])"
    gate_command: "pytest tests/[path]/test_[module].py"
    depends_on: []
    parallelizable_with: []
    # A.6d: list pre-existing artifacts this CP depends on but does not
    # produce (golden fixtures, baseline tests, vendored data). Omit if empty.
    relies_on_existing: []
    acceptance_criteria:
      - "[Criterion 1 -- observable, testable assertion]"
      - "[Criterion 2]"
    contract: "interfaces/[protocol].pyi"
  - id: CP-02
    title: "[Checkpoint Name]"
    # ... same structure
    depends_on:
      - CP-01
connectivity_tests:
  - test_id: CT-001
    source_cps:
      - CP-01
    target_cp: CP-02
    function: "test_[descriptive_name]"
    file: "tests/connectivity/test_cp01_cp02.py"
    fixture_deps:
      - "[fixture_name]"
    contract_under_test: "interfaces/[protocol].pyi :: [ProtocolName].[method_name]"
    assertion: "[What must be true about the return value]"
    gate: "pytest tests/connectivity/test_cp01_cp02.py::test_[descriptive_name]"
self_healing_log: []
```

After writing the plan, validate it round-trips cleanly:
`uv run python -c "import sys; sys.path.insert(0,'.claude/scripts'); from plan_parser import load_plan; load_plan('plans/plan.yaml'); print('Schema validation: PASS')"`

**Present the full proposed `plan.yaml`. Do not write the file.**

Output: "PROPOSAL READY. Review the checkpoint plan above. Confirm:

1. Are the checkpoint boundaries correct?
2. Are the connectivity test signatures precise enough?
3. Are the parallelization groupings safe?

Run /challenge to stress-test this plan before approving.

Reply with approval to write, or provide corrections."

---

### Step F: [HUMAN GATE] APPROVAL REQUIRED

- **WAIT** for explicit human approval.
- If corrections requested: revise and re-present. Do not write until approved.
- On approval: write `plans/plan.yaml` with `**Status:**` updated to `Approved`.

---

### Step G-symbols: BACKFILL `used_by_cps` IN `plans/symbols.yaml`

After `plans/plan.yaml` is on disk, walk the plan and resolve component
names in symbols.yaml `used_by` to CP-IDs. For each CP, iterate
`scope[].component`; for each symbol whose `used_by` contains that
component name, append the CP-ID to the symbol's `used_by_cps` list.
The architect populates `used_by` (component-level intent); the
checkpoint planner resolves to CP-level scope so Tier-3 generators
filter symbols by CP-ID at dispatch time.

The backfill is a value-preserving update to `used_by_cps` only -- it
does not change any symbol's kind, type, env_var, message_pattern, or
declared_in. Wrap it in a capability grant so the symbols-write reset
hooks do not fire.

```bash
uv run python .claude/scripts/capability.py grant --template io-checkpoint.H

uv run python -c "
import sys; sys.path.insert(0, '.claude/scripts')
from plan_parser import load_plan
from symbols_parser import load_symbols, save_symbols
from schemas import SymbolsFile

plan = load_plan('plans/plan.yaml')
registry = load_symbols('plans/symbols.yaml')

cps_by_component: dict[str, list[str]] = {}
for cp in plan.checkpoints:
    for entry in cp.scope:
        cps_by_component.setdefault(entry.component, []).append(cp.id)

new_symbols = {}
for name, sym in registry.symbols.items():
    cps: list[str] = []
    seen: set[str] = set()
    for component in sym.used_by:
        for cp_id in cps_by_component.get(component, []):
            if cp_id not in seen:
                cps.append(cp_id)
                seen.add(cp_id)
    new_symbols[name] = sym.model_copy(update={'used_by_cps': cps})

save_symbols('plans/symbols.yaml', SymbolsFile(symbols=new_symbols))
print('used_by_cps backfill complete')
"

uv run python .claude/scripts/capability.py revoke --template io-checkpoint.H
```

`plan.yaml.validated` is already `false` from Step F (just written), so the suppressed reset on plan.yaml is a no-op either way.

---

### Step G: STAMP AND ROUTE

After writing `plan.yaml`, output:

```
CHECKPOINTS LOCKED.

Total checkpoints: [N]
Parallelizable pairs: [N]
Connectivity tests defined: [N]
Features covered: [N/N]

Next step: Run /validate-plan to approve plan.yaml, then /io-plan-batch.
```

---

## 3. CONSTRAINTS

- This workflow produces `plans/plan.yaml` AND backfills `used_by_cps` in `plans/symbols.yaml` (Step G-symbols). No component-contracts.yaml edits, no seams.yaml edits.
- In remediation mode, also writes to `plans/backlog.yaml` via `route_backlog_item.py --prompt` (Routed annotation with prompt text).
- Connectivity tests are signatures only — no test code is written here.
- Write targets per checkpoint must be derived from the `file` fields in `plans/component-contracts.yaml`. A checkpoint may not write to a `src/` file whose component is not registered there.
- **[HARD] Runtime `.py` location constraint:** All checkpoint write targets that are `.py` files must resolve to a path under `src/` or `tests/`. Any write target placing a `.py` file outside `src/` and `tests/` is a structural error -- reject the write target and route the file to the appropriate `src/` component before the checkpoint is approved.
- If decomposing a feature reveals a gap in the component contract set (a required component has no contract entry), HALT and route to `/io-architect` before continuing.
- `plan.yaml` is the orchestrator's only input for delegation decisions. Vague checkpoints will produce low confidence scores and stall execution.
- Remediation CP write targets must be a strict subset of files already implemented by the parent CP or its predecessors. Any file belonging to a pending roadmap checkpoint is off-limits — that forward dependency is a design error, not a valid remediation scope.
- **Appendix A §A.6e -- Grep-verify paths before writing.** Before writing any file path into `plan.yaml` (checkpoint `write_targets`, `context_files`, `relies_on_existing`, or CT `file`/`fixture_deps`), use the Grep tool to verify the path either (a) already exists on disk, (b) traces to an upstream artifact's declared outputs, or (c) is claimed by this CP's own `write_targets`. Paths authored from memory are a recurring defect class that the `/validate-plan` Step 9D gate catches mechanically -- but the gate is non-blocking; authoring discipline is the primary defense.

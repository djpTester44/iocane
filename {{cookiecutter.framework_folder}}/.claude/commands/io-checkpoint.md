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
> 2. Load the component registry: `view_file plans/component-contracts.toml`
> 3. Load the Roadmap: `view_file plans/roadmap.md`
> 4. Load the Architecture Spec: `view_file plans/project-spec.md`
> 5. Load all interfaces: `view_file interfaces/*.pyi`
> 6. Load the Integration Seams reference via `seam_parser.load_seams('plans/seams.yaml')`. Use the `receives_di` graph (via `all_di_edges()`) to identify which component boundaries require connectivity tests: if CP-A builds a component and CP-B builds a component that injects it, a connectivity test is required at that seam.

# WORKFLOW: IO-CHECKPOINT

**Objective:** Decompose every feature in `roadmap.md` into atomic, independently-testable checkpoints. Define connectivity test signatures at every seam between dependent checkpoints. Write `plans/plan.yaml`.

**Position in chain:**

```
/io-architect -> [/io-checkpoint] -> /validate-plan -> /io-plan-batch -> /validate-tasks -> dispatch-agents.sh
```

**Definition of an atomic checkpoint:**
A unit of functionality that:

- Maps to one or more methods in an `interfaces/*.pyi` contract
- Can pass its own tests independently, without requiring other checkpoints to be complete
- Is small enough to be executed by a single sub-agent session without context pressure
- Has a clear, verifiable gate command

---

## 1. STATE INITIALIZATION

Before proceeding, output the following metadata:

- **Roadmap features:** [N features identified]
- **Interface Registry entries:** [N contracts in project-spec.md]
- **Existing plan.yaml:** [Present / Not present]
- **Mode:** [Greenfield | Extending existing plan]

**Remediation mode:** When invoked with backlog items as scope (rather than
roadmap features), generate a remediation checkpoint (`CP-NNR`) for each item:

- Use naming convention `CP-{parent}R{N}` (e.g., CP-06R1, CP-06R2). Check
  existing `plans/plan.yaml` for entries matching `CP-{parent}R*` and increment
  `N` to avoid naming collisions with previously generated remediation CPs.
  Use: `uv run rtk python -c "import sys; sys.path.insert(0,'.claude/scripts'); from plan_parser import load_plan; plan=load_plan('plans/plan.yaml'); print([cp.id for cp in plan.checkpoints])"`
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
  `bash .claude/scripts/route_backlog_item.py BL-NNN CP-NNR`
  where `BL-NNN` is the backlog item's ID from the `**Source BL:**` field.

---

## 2. PROCEDURE

### Step A: [HARD GATE] CONTRACTS LOCKED

- **Action:** Verify `plans/project-spec.md` exists and `interfaces/*.pyi` files are present.
- **Rule:** If Interface Registry is empty or no `.pyi` files exist, HALT.
- **Output:** "HALT: Contracts not locked. Run `/io-architect` first."

---

### Step B: DECOMPOSE FEATURES INTO CHECKPOINTS

For each feature in `roadmap.md`:

- **Read** the feature's acceptance criteria and `depends_on` list.
- **Read** the CRC cards for all components involved in this feature.
- **Identify** the function-level units of work implied by the CRC responsibilities.
- **Group** related functions into the smallest independently-testable unit.

**Acceptance criteria:** Each checkpoint must include 2-4 observable, testable assertions as `acceptance_criteria`. These are design-time decisions -- they flow directly into the task file and must not be synthesized at batching time. The `contract` field is the primary `.pyi` file from the checkpoint's scope.

**[HARD] Protocol Raises coverage:** For each Protocol method in the checkpoint's scope, every `Raises:` declaration in the `.pyi` docstring must appear as an acceptance criterion, or be explicitly annotated as `[DEFERRED: justification]` in the acceptance criteria list. The agent loads all `.pyi` files (instruction 5) and has `seams.yaml` available (instruction 6) -- cross-reference both. A `key_failure_modes` entry in `seams.yaml` that maps to a Protocol `Raises:` declaration reinforces the requirement. Missing coverage is a gap the evaluator cannot catch downstream because it grades only against the criteria authored here.

**Decomposition rules:**

- One checkpoint = one component's core behavior, OR one well-defined integration seam
- A checkpoint must not span multiple architectural layers unless the seam between them is exactly what's being tested
- If a component has 5 methods and they can all be built and tested as a unit → one checkpoint
- If methods A and B must exist before method C can be meaningfully tested → separate checkpoints

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
fixture_deps: [[fixture_name], [fixture_name]]
contract_under_test: interfaces/[protocol].pyi :: [ProtocolName].[method_name]
assertion: [What must be true about the return value — type, shape, invariants. No implementation detail.]
gate: pytest tests/connectivity/test_[cp_a]_[cp_b].py::[function_name]
```

**CT file ownership:** The CT file is owned by `target_cp` (the downstream checkpoint, CP-B in the `CP-A → CP-B` seam). `target_cp` is responsible for creating the test file during its execution phase. `source_cps` provide the dependency context — their output must exist for the test to pass — but they do not write the CT file and must NOT include it in their `write_targets` or `gate_command`.

**Rules for connectivity test signatures:**

- The assertion must be precise enough that `/io-execute` can build the test without ambiguity
- The assertion describes the observable contract boundary — return type, key invariants, no ORM types leaking through domain layer, etc.
- `fixture_deps` must name real fixtures or factories that will exist after CP-A is complete
- Every dependency edge in the checkpoint graph must have at least one connectivity test
- The CT test file is a write target of `target_cp` only. Source checkpoints must NOT include the CT file in their `write_targets` or `gate_command`.
- The downstream checkpoint's **gate command** MUST include the CT file path from the `file:` field (i.e., the `target_cp` checkpoint). If the CT file does not exist at execution time, the gate will fail — this is intentional. Example: if CT-001 verifies the CP-01→CP-02 seam, CP-02's gate command must be `uv run rtk pytest tests/domain/test_dag_resolver.py tests/connectivity/test_cp01_cp02.py`, not just `uv run rtk pytest tests/domain/test_dag_resolver.py`.

**Present all connectivity test signatures. Do not write any file yet.**

---

### Step E: [PLAN MODE] PROPOSE PLAN.YAML

Propose the full content of `plans/plan.yaml`. The output must be valid YAML conforming to the Plan schema in `.claude/scripts/schemas.py`:

```yaml
generated_from:
  - plans/roadmap.md
  - plans/project-spec.md
validated: false
checkpoints:
  - id: CP-01
    title: "[Checkpoint Name]"
    feature: "F-01 -- [Feature name from roadmap.md]"
    description: "[One sentence -- what is built and testable when complete]"
    status: pending
    scope:
      - component: "[ComponentName]"
        protocol: "interfaces/[protocol].pyi"
        methods:
          - "[method_name]"
    write_targets:
      - "src/[path]/[module].py"
      - "tests/[path]/test_[module].py"
    context_files:
      - "interfaces/[protocol].pyi"
      - "plans/project-spec.md (CRC card for [ComponentName] only)"
    gate_command: "pytest tests/[path]/test_[module].py"
    depends_on: []
    parallelizable_with: []
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
`uv run rtk python -c "import sys; sys.path.insert(0,'.claude/scripts'); from plan_parser import load_plan; load_plan('plans/plan.yaml'); print('Schema validation: PASS')"`

**Present the full proposed `plan.yaml`. Do not write the file.**

Output: "PROPOSAL READY. Review the checkpoint plan above. Confirm:

1. Are the checkpoint boundaries correct?
2. Are the connectivity test signatures precise enough?
3. Are the parallelization groupings safe?

Reply with approval to write, or provide corrections."

---

### Step F: [HUMAN GATE] APPROVAL REQUIRED

- **WAIT** for explicit human approval.
- If corrections requested: revise and re-present. Do not write until approved.
- On approval: write `plans/plan.yaml` with `**Status:**` updated to `Approved`.

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

- This workflow produces ONLY `plans/plan.yaml`. No `.pyi` edits, no `project-spec.md` edits.
- In remediation mode, also writes to `plans/backlog.yaml` via `route_backlog_item.py` (Routed annotation only).
- Connectivity tests are signatures only — no test code is written here.
- Write targets per checkpoint must be derived from the `file` fields in `plans/component-contracts.toml`. A checkpoint may not write to a `src/` file whose component is not registered there.
- **[HARD] Runtime `.py` location constraint:** All checkpoint write targets that are `.py` files must resolve to a path under `src/` or `tests/`. The `interfaces/` directory is reserved exclusively for `.pyi` contract stubs generated or approved by `/io-architect`. Any write target placing a `.py` file under `interfaces/` or any other directory outside `src/` and `tests/` is a structural error -- reject the write target and route the file to the appropriate `src/` component before the checkpoint is approved.
- If decomposing a feature reveals a gap in the Interface Registry (a required component has no Protocol), HALT and route to `/io-architect` before continuing.
- `plan.yaml` is the orchestrator's only input for delegation decisions. Vague checkpoints will produce low confidence scores and stall execution.
- Remediation CP write targets must be a strict subset of files already implemented by the parent CP or its predecessors. Any file belonging to a pending roadmap checkpoint is off-limits — that forward dependency is a design error, not a valid remediation scope.

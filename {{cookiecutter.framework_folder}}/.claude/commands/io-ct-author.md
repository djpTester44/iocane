---
name: io-ct-author
description: Tier 3a. Author connectivity tests for one CP (primary flow). Runs before generator; target impl does not exist yet.
---

> **[CRITICAL] CONTEXT LOADING**
>
> 1. Task file: `plans/tasks/${IOCANE_CP_ID}.yaml`
> 2. Full plan (CT specs authoritative): `plans/plan.yaml`
> 3. Seam context: `plans/seams.yaml`
> 4. Symbols registry: `plans/symbols.yaml`
> 5. Protocols: `interfaces/*.pyi`
> 6. Existing import patterns (read-only): `tests/contracts/*.py`
> 7. Methodology: `.claude/skills/test-writer/SKILL.md`
> 8. Per-kind rules: `.claude/skills/test-writer/references/ct-author-rules.md`

# WORKFLOW: IO-CT-AUTHOR

**Objective.** Write every connectivity test whose `target_cp ==
${IOCANE_CP_ID}` before the generator stage runs for that CP. Target
impl does not exist; CTs fail by design once written. The generator
takes them RED to GREEN.

**Position in chain:**

```
dispatch-agents.sh (per CP):
  preflight -> [io-ct-author] -> generator (io-execute) -> evaluator
```

One invocation per CP. Parallel dispatch across CPs is owned by
`dispatch-agents.sh`; this command file defines the workflow each
ct-writer session runs in isolation.

This workflow is **separate from `io-ct-remediate`**. Remediation
runs AFTER impl is archived, imports both seam sides real, and runs
the gate. This primary flow runs BEFORE impl exists, spy-mocks the
source side, and does NOT run the gate.

---

## 1. STATE INITIALIZATION

Report:

- `IOCANE_CP_ID` value.
- Count of CT entries in `task.connectivity_tests` (target_cp-scoped
  by `generate_task.py`).
- CT-IDs to write.

If `task.connectivity_tests` is empty, print `io-ct-author: no CTs
for ${IOCANE_CP_ID}; nothing to write.` and terminate with exit 0 --
the dispatcher treats zero CTs as a clean skip.

Load:

```bash
uv run python -c "
import sys; sys.path.insert(0, '.claude/scripts')
from task_parser import load_task
task = load_task('plans/tasks/${IOCANE_CP_ID}.yaml')
for ct in task.connectivity_tests:
    print(f'{ct.test_id}  {ct.function}  {ct.file}')
"
```

---

## 2. PROCEDURE

### Step 1 -- LOAD CT SPECS

For each entry in `task.connectivity_tests`, verify all required
fields are populated (no empty strings, no `# TODO` placeholders):

- `test_id`
- `function`
- `file`
- `fixture_deps`
- `contract_under_test`
- `assertion`
- `gate`

If any field is missing or a placeholder, enter the HALT path in
Section 3 -- do NOT author against an incomplete spec.

Also load the full plan so source-side Protocol types are resolvable:

```bash
uv run python -c "
import sys; sys.path.insert(0, '.claude/scripts')
from plan_parser import load_plan
plan = load_plan('plans/plan.yaml')
for ct in plan.connectivity_tests:
    if ct.target_cp == '${IOCANE_CP_ID}':
        print(ct.test_id, ct.source_cps, ct.contract_under_test)
"
```

---

### Step 2 -- LOAD SEAM CONTEXT

Load `plans/seams.yaml` via `seam_parser.load_seams`. For each CT,
use `find_by_component()` on the source side of the seam to obtain
`receives_di` and `key_failure_modes`. These inform:

- Which injected Protocols need spy-capable fixtures.
- Which failure modes should be exercised via
  `pytest.raises(...)` branches in the assertion body.

---

### Step 3 -- TRACK TRIAGE

Read `.claude/skills/test-writer/SKILL.md` and its triage gate. For
every CT in this CP, record Track A (FSM) or Track B (contract).
Default for CTs is Track B -- CTs exercise stateless call-binding /
cardinality / error-propagation observables at a seam. Track A
applies only when a source Protocol has 2+ named states whose
transitions the CT must observe.

Read `.claude/skills/test-writer/references/ct-author-rules.md` in
full before proceeding. Its rules are load-bearing -- especially the
spy-mock contract and the "no gate run, no skeleton impl" clauses.

---

### Step 4 -- WRITE TEST FILES

Author one test file per `file:` path listed in
`task.connectivity_tests`. Follow the test-writer skill's
three-phase discipline (Extract -> Design -> Generate). The CT
spec's `assertion:` field is the Phase 1 model input.

Per-CT requirements are in `ct-author-rules.md`. Summary:

- Cite `test_id` in the test function or module docstring.
- Import target component real from `src.*`; import source Protocol
  type from `interfaces.*` only for the `spec=` argument.
- Spy-mock every source-side Protocol (`MagicMock(spec=...)`,
  `mocker.spy`, or hand-rolled stub with `.call_args`, `.call_count`).
- Map each observable in `assertion:` to at least one assertion in
  the test body (call binding, cardinality, error propagation).
- Fixture names match `fixture_deps:` exactly.
- Write path matches `file:` exactly.

Create `tests/connectivity/` if it does not exist. Do NOT create
`tests/connectivity/__init__.py` unless the project's other test
directories use package-style layout (pytest collects without it in
the default configuration).

Do NOT run the CT's `gate:` command after writing. Target impl does
not exist; the gate will fail by design.

---

### Step 5 -- OUTPUT CONTRACT

Print exactly:

```
io-ct-author: cp=${IOCANE_CP_ID} cts=<N> written
io-ct-author: complete.
```

Then terminate. The dispatcher reads the process exit code; do not
attempt to write `.status` files (that protocol belongs to the
generator stage).

---

## 3. HALT PATH (CT spec defect)

Triggered when any CT spec field is:

- Empty or a `# TODO` placeholder.
- `fixture_deps` names a fixture that does not exist and cannot be
  constructed from the imported modules.
- `assertion` is contradictory, references a Protocol method that
  does not exist on the `contract_under_test` target, or covers no
  observable that can be mapped to a test body.

On any such defect:

1. Print a structured error:

   ```
   io-ct-author: HALT -- CT spec defect
   CP: ${IOCANE_CP_ID}
   Defective CT-IDs: CT-NNN [reason], CT-MMM [reason], ...
   ```

2. Terminate with exit code 1. Do NOT emit an AMEND signal. Do NOT
   write partial test files. Do NOT attempt to repair the spec.

Per D16, CT-signature defects are architect-level issues that the
architect's `H-post-validate` gates should have caught upstream. The
AMEND loop is Protocol-scoped (tester domain), not CT-scoped. Route
back to human for re-architect.

---

## 4. CONSTRAINTS

- **Reads only:**
  - `plans/tasks/${IOCANE_CP_ID}.yaml`
  - `plans/plan.yaml`
  - `plans/seams.yaml`
  - `plans/symbols.yaml`
  - `interfaces/*.pyi` (all Protocols, for type references)
  - `tests/contracts/*.py` (read-only, for import-pattern reference)

- **Writes only:**
  - `tests/connectivity/*.py`, one file per entry in
    `task.connectivity_tests`, at the exact `file:` path listed.

- **Never edits:**
  - `interfaces/*.pyi` (architect-owned)
  - `plans/*.yaml` (architect-owned / validated)
  - `tests/contracts/*` (tester-owned)

Any write into architect-owned artifacts triggers the reset-hook
chain and invalidates the architect's validation stamps during
parallel dispatch. Cost: the entire wave's downstream authorization
is voided. The reset firing IS the defense -- it means your session
has drifted into a role it does not own.

- **Never runs:**
  - Any CT `gate:` command. Target impl is absent; gate will fail
    by design.
  - `pytest` against `tests/connectivity/*`.
  - Any script that writes `.status`, `.exit`, or `.result.json` for
    `${IOCANE_CP_ID}` (generator-stage protocol).

- **Never emits:**
  - `.iocane/amend-signals/*.yaml` (no AMEND channel at this tier).

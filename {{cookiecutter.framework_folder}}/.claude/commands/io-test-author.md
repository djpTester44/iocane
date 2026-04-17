---
name: io-test-author
description: Tier 1. Author contract tests for one Protocol, or emit AMEND signal when under-specified.
---

> **[CRITICAL] CONTEXT LOADING**
>
> 1. Target Protocol: `interfaces/${IOCANE_PROTOCOL}.pyi`
> 2. Test plan: `plans/test-plan.yaml` (invariants, per Protocol method)
> 3. Symbols registry: `plans/symbols.yaml` (exceptions, shared types)
> 4. Component contracts: `plans/component-contracts.yaml` (collaborators)
> 5. Methodology: `.claude/skills/test-writer/SKILL.md`

# WORKFLOW: IO-TEST-AUTHOR

**Objective.** Author contract tests for the single Protocol named by
`IOCANE_PROTOCOL`, OR emit a structured AMEND signal when the Protocol
is under-specified relative to the test-plan invariants.

**Position in chain:**

```
/io-architect -> [io-test-author per Protocol] -> /io-checkpoint
              -> architect AMEND sub-loop if signals emitted
```

One invocation per Protocol. Parallel dispatch lives in Phase 6b
(`dispatch-testers.sh`); this command file defines the workflow each
tester runs in isolation.

---

## 1. STATE INITIALIZATION

Report:

- `IOCANE_PROTOCOL` value
- Protocol method count (public methods in the `.pyi`)
- Test-plan invariant count for this Protocol
- Whether `.iocane/amend-signals/${IOCANE_PROTOCOL}.yaml` already
  exists (forced-AMEND re-entry signal from a prior tester run)

If an amend signal already exists from a prior run, note it. The
architect's forced-AMEND detection (at io-architect Step 1) is the
authority that consumes it; this tester does NOT short-circuit on
its presence -- it re-evaluates the Protocol freshly against the
current test-plan.

---

## 2. PROCEDURE

### Step A: [HARD GATE] INPUTS VALIDATED

- **Action:** Load `plans/test-plan.yaml` via the Pydantic parser and
  check the top-level `validated` field. `plans/symbols.yaml` has no
  stamp (its validation is coupled to test-plan via the reset-hook
  chain); verify existence only.
- **Command:** run the Python check below. A substring `grep` on
  `validated: true` is insufficient -- any invariant description
  quoting prior state would false-green the gate.
  ```bash
  uv run python -c "
  import sys; sys.path.insert(0, '.claude/scripts')
  from test_plan_parser import load_test_plan
  tp = load_test_plan('plans/test-plan.yaml')
  sys.exit(0 if tp.validated else 1)
  "
  ```
- **Rule:** If `test-plan.yaml.validated` is not `True`, HALT.
- **Output:** "HALT: plans/test-plan.yaml not stamped validated: true.
  Run `/io-architect` Step H-post-validate." Do NOT proceed -- an
  unstamped input means the architect's own coverage gates did not
  pass, and any test authored against it would be authored against a
  draft.

---

### Step B: PARSE PROTOCOL

- **Action:** Use `ast.parse` on `interfaces/${IOCANE_PROTOCOL}.pyi`.
- **Enumerate per public method:**
  - Signature (positional args, keyword args, return annotation)
  - Docstring
  - `Raises:` clause contents (exception types + trigger text)
  - Collaborator dependencies inferred from `__init__` parameters

---

### Step C: MAP METHODS TO INVARIANTS

- **Action:** Load `plans/test-plan.yaml`. For each `TestPlanEntry`
  whose target matches this Protocol, map its invariants to the
  Protocol methods enumerated in Step B.
- **Output:** Method -> list[invariant_id] mapping held as reasoning.
  Orphan invariants (pointing at methods that do not exist in the
  Protocol) are themselves under-specification signals -- surface in
  Step E as `SYMBOL_GAP`.

---

### Step D: TRACK-A / TRACK-B TRIAGE

Per `.claude/skills/test-writer/SKILL.md`:

- **Track A (FSM):** the Protocol has 2+ distinct named states with
  explicit transitions (e.g., idle/running/complete, open/closed).
  Authorize state-transition invariants with state-entry tests.
- **Track B (Contract):** no state machine -- pure input/output
  invariants. Authorize call_binding, cardinality, error_propagation,
  and property invariants.

Record the triage choice. Every invariant kind used in Step G must be
consistent with the triage.

---

### Step E: [HARD GATE] UNDER-SPECIFICATION CHECK

For each invariant mapped in Step C, determine whether the Protocol
as written is sufficient to author a test that EXERCISES the
invariant. Classify gaps using `AmendSignalKind`
(`.claude/scripts/schemas.py`):

| Kind | Trigger |
|------|---------|
| `missing_raises` | Invariant names an exception; Protocol's `Raises:` does not include it |
| `silent_return_semantics` | Invariant references a postcondition; return annotation is `None`/`Any` or docstring says nothing about the return shape |
| `missing_precondition` | Invariant specifies a precondition (e.g., non-empty input) the Protocol does not declare |
| `undeclared_collaborator` | Invariant references a DI dependency not in the `__init__` signature |
| `symbol_gap` | Invariant references a type, exception, or symbol not in `plans/symbols.yaml` |

**If ANY gap exists:**

1. Construct an `AmendSignalFile`:
   - `protocol: "interfaces/${IOCANE_PROTOCOL}.pyi"` (FULL path, per
     schema validator)
   - `signals:` list of `AmendSignal`, one per gap identified:
     - `method`: Protocol method name the gap applies to
     - `invariant_id`: the INV-NNN this gap blocks
     - `kind`: one of the five enum values above
     - `description`: one-line explanation of what is missing
     - `suggested_amendment`: concrete edit the architect should make
       (e.g., "add `Raises: ValidationError: when payload is empty`
       to `submit()` docstring")
   - Leave `attempt` at the schema default. The counter lives in
     `.iocane/amend-attempts.<stem>` and is populated by
     `handle_amend_signal.py`, not by the tester.
2. Write `.iocane/amend-signals/${IOCANE_PROTOCOL}.yaml` using the
   Write tool. Validate by round-tripping through `AmendSignalFile`
   before writing.
3. Print a structured summary naming the gaps, then STOP. Do NOT
   write a test file. Termination on a valid AMEND signal IS the
   successful outcome for this invocation.

**If NO gap exists:** proceed to Step F.

---

### Step F: [HUMAN GATE] -- skipped when IOCANE_ROLE=tester

This gate applies only when the workflow is invoked manually from an
interactive session. Present a summary of the proposed tests (one
line per invariant) and await approval before writing.

When `IOCANE_ROLE=tester` (non-interactive dispatch from
`spawn-tester.sh`): skip this gate and proceed to Step G.

---

### Step G: WRITE CONTRACT TESTS

Write `tests/contracts/test_${IOCANE_PROTOCOL}.py`.

**Rules:**

- Pytest conventions: `test_<behavior>` functions, standard fixtures.
- Every invariant from Step C maps to AT LEAST one test.
- No `assert True` placeholders.
- No mocks without cardinality assertions -- if a collaborator is
  mocked, the test must also assert call count or argument shape.
- Imports:
  - The Protocol itself from `interfaces.<stem>`
  - Domain types from `interfaces.models`
  - Exceptions from `interfaces.exceptions`
  - `pytest` for fixtures and `pytest.raises`
- Do NOT import from `src/` -- contract tests run against the
  Protocol, not an implementation. The implementation does not exist
  yet at this phase of the workflow.

**No validating sentinel.** The tester's write paths
(`tests/contracts/`, `.iocane/amend-signals/`) do not match any of
the reset-hook triggers (`interfaces/*.pyi`, `plans/symbols.yaml`,
`plans/test-plan.yaml`). Reset hooks firing during a tester run means
the tester has drifted into architect-owned artifacts -- that is a
defect, not an expected path, and the reset is the correct defense.
Using the sentinel here would mask that defect.

---

### Step H: OUTPUT CONTRACT

Print exactly:

```
io-test-author: protocol=${IOCANE_PROTOCOL} track=<A|B> tests=<N> <written|amend-signalled>
io-test-author: complete.
```

Then terminate.

---

## 3. CONSTRAINTS

- **Reads only:**
  - `interfaces/*.pyi` (the target Protocol PLUS all other Protocols
    whose shared types may be referenced via `interfaces/models.pyi`
    and `interfaces/exceptions.pyi`)
  - `plans/test-plan.yaml`
  - `plans/symbols.yaml`
  - `plans/component-contracts.yaml`
- **Writes only (mutually exclusive per invocation):**
  - `tests/contracts/test_${IOCANE_PROTOCOL}.py` (happy path), OR
  - `.iocane/amend-signals/${IOCANE_PROTOCOL}.yaml` (AMEND path)
- **Never edits:**
  - `interfaces/*.pyi` (architect-owned)
  - `plans/symbols.yaml` (architect-owned)
  - `plans/test-plan.yaml` (architect-owned)
  - `plans/component-contracts.yaml` (architect-owned)
- **Never touches:**
  - `.iocane/amend-attempts.<stem>` (handle_amend_signal.py is the
    sole writer of the retry counter)

Drift into any architect-owned artifact will trigger the reset-hook
chain, invalidate the architect's stamps, and break the forced-AMEND
contract. The tester's role is narrow by design.

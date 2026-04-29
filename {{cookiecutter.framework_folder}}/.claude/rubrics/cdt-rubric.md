# CDT Rubric -- Contract-Driven Test Critic Evaluation Spec

> **Role.** Immutable input to the CDT Critic (R5: rubrics are immutable
> inputs to the Critic; the Author's reasoning is not). The Critic reads
> this file, the Author-written test file, and `plans/component-contracts.yaml`
> to form an independent verdict. The Author consults this file to anticipate
> what the Critic will check.
>
> This rubric lives at `.claude/rubrics/cdt-rubric.md` in consumer repos.
> It is NEVER modified mid-run; the Critic receives it as a static context path.

## Verdict Semantics

A CDT `EvalReport` carries four boolean axis fields. The Critic sets each to
`True`, `False`, or `None`:

- **PASS**: ALL four axis booleans `True`. `critique_notes` may be empty.
- **FAIL**: AT LEAST ONE axis boolean `False`. `critique_notes` REQUIRED
  non-empty -- must identify which axis(es) failed and the specific contract
  element or test construct that caused the verdict.
- **AMBIGUOUS**: Critic cannot decide on one or more axes (booleans may be
  partially set or all `None`). `critique_notes` REQUIRED non-empty -- must
  name which axis was undecidable and why (malformed contract, indirect
  assertion chain, inconsistent collaborator declarations).

Non-CDT axes (`seam_fan_coverage`, `cdt_ct_mock_spec_consistent`,
`integration_path_asserted`) MUST be `None` in a CDT `EvalReport`.

---

## Axis 1 -- Payload-Shape Coverage (`payload_shape_covered`)

**What this axis checks.** Every method in the component's contract has at
least one assertion on its INPUT payload shape (parameter keys, types,
optional vs required fields) and at least one assertion on its OUTPUT payload
shape (return value keys, types, structure).

**PASS criteria** (`True`)
- For every method listed in `plans/component-contracts.yaml` under the
  component under test, the test file contains assertions that verify:
  - the input accepts the declared parameter types and rejects (or is
    indifferent to) undeclared ones, AND
  - the output structure matches the declared return-value shape.
- Shape assertions may be direct (`assert isinstance(result.field, str)`) or
  via Pydantic validation -- any form that is executable and specific to the
  declared schema.

**FAIL criteria** (`False`)
- One or more contract-declared methods have no input-shape assertion.
- One or more contract-declared methods have no output-shape assertion.
- Shape assertions are present but cover only a subset of declared methods
  (partial coverage = FAIL; all methods must be covered).

**AMBIGUOUS criteria** (`None` or undecidable)
- The test asserts shape via a derived expression and the Critic cannot
  determine whether the derivation covers the declared shape without
  executing the test.
- The `component-contracts.yaml` entry for the component is syntactically
  malformed; Critic cannot enumerate the method list.
- Emit the specific axis name and the undecidable construct in
  `critique_notes`.

**Illustrative example**
A contract declares `process(payload: dict) -> ProcessResult`. PASS requires
assertions like `assert "status" in result` and
`assert isinstance(result.status, str)`. A test that only calls
`process(payload)` and asserts `result is not None` does NOT pass this axis.

---

## Axis 2 -- Per-Contract-Field Invariant Assertions (`invariants_asserted`)

**What this axis checks.** Every invariant explicitly declared in the
component's `component-contracts.yaml` entry is translated to at least one
executable assertion in the test. Invariants are CONTRACT-DECLARED; the
rubric grades translation completeness, not test-author-invented coverage.

**PASS criteria** (`True`)
- For every invariant in the contract (e.g., `"result.total >= 0"`,
  `"user.email matches RFC 5321"`, `"output list is sorted ascending"`),
  the test file contains an assertion that exercises that invariant on a
  relevant payload.
- One assertion per invariant is sufficient; multiple are acceptable.

**FAIL criteria** (`False`)
- A contract-declared invariant exists and the test file has no assertion
  exercising it.
- The test asserts an invariant that is NOT declared in the contract
  (over-specification = FAIL; the test surface no longer corresponds to
  the contract surface).

**AMBIGUOUS criteria** (`None` or undecidable)
- A contract invariant is written in prose too imprecise to translate to a
  deterministic assertion (e.g., `"result is reasonable"`). Critic CANNOT
  assign FAIL -- ambiguity in the contract propagates to ambiguity in the
  verdict.
- Emit `critique_notes` naming the invariant text and why it is
  undecidable.

---

## Axis 3 -- Collaborator Mocks Speced (`collaborator_mocks_speced`)

**What this axis checks.** Every collaborator the component under test invokes
has a mock constructed with `unittest.mock.Mock(spec=[...method names...])`,
where the spec list covers at least the methods the component calls on that
collaborator. This axis verifies WHAT (collaborator method surface is bounded)
without prescribing HOW (inline vs shared module).

Per Rev 5 S1 Drop: no shared fixture-builder module is shipped with the
harness. The Author chooses inline spec lists per `Mock(spec=[...])`. This
axis does not penalize inline construction; it penalizes unbounded or absent
mocks.

**PASS criteria** (`True`)
- Every collaborator identified in the contract's collaborator declarations
  is mocked in the test.
- Each mock is constructed with `spec=[...]` (or `spec=<ClassName>`) that
  covers at minimum the methods the component invokes on that collaborator.
- The spec list must be non-empty; `Mock()` without `spec` does not satisfy
  this axis.

**FAIL criteria** (`False`)
- A collaborator is invoked in the test WITHOUT a mock backing it (live
  dependency or `MagicMock()` without spec).
- A collaborator mock is present but constructed without `spec=[...]` --
  no method-surface bound.
- A collaborator is declared in the contract but absent from the test's
  mock setup entirely.

**AMBIGUOUS criteria** (`None` or undecidable)
- The contract's collaborator declarations are inconsistent with the
  component's observable call sites (e.g., contract names collaborator A
  but the test code invokes collaborator B with a mock; Critic cannot
  determine which is authoritative).
- Emit `critique_notes` flagging this as an upstream contract-quality issue
  requiring operator resolution.

---

## Axis 4 -- Raises-Coverage Parity (`raises_coverage_complete`)

**What this axis checks.** Every entry in the component contract's `raises`
list (or per-method `raises` fields) has at least one test assertion that
verifies the declared exception type is raised under the declared trigger
condition. The contract's `raises` list is the spec; parity means the test
exercises every declared entry.

**PASS criteria** (`True`)
- For every `raises` entry in the contract, the test contains
  `pytest.raises(<ExceptionType>)` or equivalent that exercises the
  declared trigger condition.
- Both the exception TYPE and the TRIGGER CONDITION must be covered -- a
  test that raises the right exception under the wrong condition does not
  achieve parity.
- No contract `raises` entry may be unexercised.

**FAIL criteria** (`False`)
- A contract `raises` entry exists and the test has no corresponding
  `pytest.raises(...)` for that exception type under that trigger.
- The test asserts a raise that the contract's `raises` list does NOT
  declare (over-specification = FAIL; test surface exceeds contract surface).

**AMBIGUOUS criteria** (`None` or undecidable)
- The contract `raises` entry specifies no trigger condition or an
  unspecified condition (e.g., `raises: [ValueError]` with no `when:`
  field). Critic cannot determine whether a trigger-covering test exists.
- The contract `raises` syntax is malformed.
- Emit `critique_notes` naming the malformed or under-specified entry.

**Note on D-12 (DEFER).** A potential fifth CDT axis (raises-list entries
parameterized against Settings symbols rather than hardcoded literals) is
NOT part of this rubric. D-12 verdict is DEFER pending Phase 4 calibration
evidence. Catch-incidence is tracked via the Phase 4 calibration log and
does not gate PASS on this axis.

---

## STATUS Coupling (Cross-Field Validator)

The `EvalReport` cross-field validator in `.claude/scripts/schemas.py`
enforces these invariants mechanically. This section documents the
behavioral spec; the code is authoritative.

| STATUS | Condition | `critique_notes` |
|--------|-----------|-----------------|
| `PASS` | All four CDT axis booleans `True` | May be empty |
| `FAIL` | At least one CDT axis boolean `False` | REQUIRED non-empty |
| `AMBIGUOUS` | Critic cannot decide on >=1 axis | REQUIRED non-empty |

A `FAIL` report with empty `critique_notes` is malformed and is caught by
`eval_parser.py` (counts against MAX_TURNS). An `AMBIGUOUS` report with
empty `critique_notes` is similarly malformed.

For `FAIL`, `critique_notes` must identify: which axis(es) are `False`,
which specific contract element was unexercised or violated, and (where
possible) the test construct that produced the gap.

For `AMBIGUOUS`, `critique_notes` must identify: which axis was
undecidable, which payload dimension or contract element was ambiguous,
and whether the ambiguity originates in the test file or the contract source.

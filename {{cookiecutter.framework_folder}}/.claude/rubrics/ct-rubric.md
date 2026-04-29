# CT Rubric -- Connectivity Test Critic

Immutable evaluation criteria for CT (Connectivity Test) Critic and Author.
CT tests verify SEAM-level integration contracts: cross-component edges declared
in `plans/seams.yaml`. This is distinct from CDT's per-component contract
verification.

Read by:
- CT Critic (`spawn-test-critic.sh --target-type ct`)
- CT Author (`spawn-test-author.sh --target-type ct`)

---

## Precondition (D-20)

This rubric assumes the D-20 STRICT precondition holds: the matching CDT eval
YAMLs for BOTH the source AND destination components have STATUS=PASS and are
not `.collision-tainted`. If either CDT eval YAML is absent, STATUS != PASS, or
collision-tainted, the CT command (`io-wire-tests-ct.sh`) halts before Author
spawn. This rubric does not re-validate the precondition; it assumes it.

---

## Axis 1 -- Seam fan-in/out coverage (`seam_fan_coverage`)

For the seam edge identified by `--target-id`, the test must assert:

- Every declared **fan-IN source** (component that invokes the seam target with
  a declared payload) causes the seam under test to be exercised.
- Every declared **fan-OUT destination** (component the seam target dispatches
  to) receives the expected payload.

The coverage reference is `plans/seams.yaml` for the specific edge under test.

**PASS:** Every fan-in source AND every fan-out destination declared in
`plans/seams.yaml` for this edge has at least one test assertion.

**FAIL:** One or more declared fan-in sources or fan-out destinations have no
corresponding test assertion.

**AMBIGUOUS:** `plans/seams.yaml` declares a fan-in or fan-out but the source or
destination component contracts are inconsistent with the declared seam (e.g.,
the declared fan-in source has no method that matches the invocation shape).
Critic flags as upstream seam-vs-contract drift; `critique_notes` names the
specific inconsistency and which component-contract entry conflicts.

---

## Axis 2 -- CDT-CT Mock Spec Consistent (`cdt_ct_mock_spec_consistent`)

Per v5 S1 drop: no shared fixture-builder module is shipped. "Reuse" means
PATTERN-CONSISTENT at the spec tier, not shared-module-import.

The CT Author reads CDT files at `tests/contracts/test_<src>.py` and
`tests/contracts/test_<dst>.py` to mirror mock construction shape. The Critic
verifies that mirror was honored.

**PASS:** The source-component and destination-component mocks in the CT test use
the same `Mock(spec=[...])` method-name list as their counterpart CDT test files.
If the CDT test mocked `MyService` with `spec=["fetch", "save"]`, the CT test
mocks `MyService` with `spec=["fetch", "save"]` -- same list, same order.

**FAIL:** The CT test constructs a mock for the source or destination component
with a different method-surface than the matching CDT file (drift), OR constructs
a mock without `spec=[...]` entirely.

**AMBIGUOUS:** The matching CDT test does not exist or its own mock construction
is incomplete (e.g., no `spec=` argument). Critic flags as upstream CDT-not-PASS
issue. `critique_notes` names which CDT file was checked and what was missing.
Note: the D-20 precondition normally prevents this case from reaching the CT
Critic; if it does appear, AMBIGUOUS is the correct verdict.

---

## Axis 3 -- Integration-path assertion (`integration_path_asserted`)

The test must assert that the integration path honors `seams.yaml allowed_layers`
for this edge. If the seam declares the path crosses layers L1 -> L2 -> L3, the
test verifies that a payload traversing this seam terminates at a destination
within `allowed_layers`, not at an out-of-band layer.

**PASS:** The test exercises the integration path AND asserts that the terminal
destination is within `allowed_layers` as declared in `plans/seams.yaml`.

**FAIL:** The test exercises the path but includes no assertion on the terminal
destination layer, OR the test asserts a terminal that is not in `allowed_layers`
(a violation that should be caught and flagged, but if the assertion is absent,
it is a coverage gap -- verdict FAIL, not AMBIGUOUS).

**AMBIGUOUS:** `plans/seams.yaml allowed_layers` is empty or null for this edge,
OR the edge's layer prose is inconsistent with its `external_terminals`
declaration. Critic flags as upstream seams-spec issue; `critique_notes` names
the specific field inconsistency.

---

## STATUS coupling

Mirrors `EvalReport` cross-field validator in `.claude/scripts/schemas.py`:

| STATUS | Required axis state | `critique_notes` |
|---|---|---|
| PASS | All three CT axes True | May be empty |
| FAIL | At least one axis False | REQUIRED non-empty |
| AMBIGUOUS | Critic cannot decide on >=1 axis | REQUIRED non-empty |

For AMBIGUOUS, `critique_notes` must identify:
1. Which axis(es) are ambiguous.
2. What specific upstream spec inconsistency prevented a verdict.

Empty `critique_notes` on FAIL or AMBIGUOUS is malformed and will be caught by
`eval_parser.py`, counting against MAX_TURNS.

Non-applicable axes (CDT axes: `payload_shape_covered`, `invariants_asserted`,
`collaborator_mocks_speced`, `raises_coverage_complete`) must be `null` in a CT
`EvalReport`. Setting any CDT axis in a CT report is a schema violation.

---

## EvalReport field reference (CT target_type)

```
target_type:              "ct"
seam_fan_coverage:        bool | null
cdt_ct_mock_spec_consistent: bool | null
integration_path_asserted: bool | null
# CDT axes must be null
payload_shape_covered:    null
invariants_asserted:      null
collaborator_mocks_speced: null
raises_coverage_complete: null
```

Field names are exact. Any deviation from the above names fails schema
validation.

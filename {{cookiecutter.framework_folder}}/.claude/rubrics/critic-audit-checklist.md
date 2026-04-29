# Critic Audit Checklist

## 1. Preamble

**Who reads this.** Operator conducting the calibration review after each N=5
wire-tests sample run.

**When.** After `run_critic_audit.py` emits a `critic-audit-<type>-<date>.yaml`
file. Review is required for BOTH test types (CDT and CT) before the
calibration ship-gate clears.

**Why.** The ship-gate for `/io-checkpoint` (State 3) requires that both 5-sets
of PASS verdicts clear human review. One-time cost paid in the first wave. If
any checklist item returns `fail`, halt and revise the affected rubric or Critic
prompt BEFORE unblocking. The gate exists because shipping an uncalibrated
Actor-Critic loop adds an undeclared trust premise on top of any honest-agent
drift the harness is already managing.

**Workflow.** Open the emitted audit YAML alongside this document. Work through
each section. Set `rubric_axis_b_results.blind_spot_identified = true` on any
per-target row where you identify a blind spot. Set `checklist.rubric_blind_spot`
to `fail` if any row is flagged. Populate all manual fields before signing off.

---

## 2. Item 1: Rubric Gaming

**What it checks.** Do the test files actually assert what each rubric axis
claims they assert? An axis marked `true` that has no corresponding assertion
in the test file is a gaming indicator -- the Critic passed an axis the Author
didn't actually cover.

**Pass criteria.**
- For every target with `raises_coverage_complete: true`, the test file contains
  at least one `pytest.raises(` call.
- For every target with `collaborator_mocks_speced: true`, the test file contains
  at least one `Mock(`, `MagicMock(`, or `patch(` call.
- Axis booleans in `rubric_axis_a_results` agree with what the test file
  contains when examined manually.

**Fail criteria.**
- Any axis is marked `true` in `rubric_axis_a_results` but the test file
  contains no code path that exercises the claimed dimension.
- `raises_coverage_complete: true` with no `pytest.raises` in the test file.
- `collaborator_mocks_speced: true` with no mock construction visible in the test
  file.

**Reasoning examples.**
- PASS: `raises_coverage_complete: true` and the test file has
  `with pytest.raises(ValueError):` covering the threshold-trigger path.
- FAIL: `invariants_asserted: true` but all `assert` statements in the test
  file only check `response is not None` -- no invariant dimensions are
  actually verified.
- FAIL: `payload_shape_covered: true` but the test file only calls the
  function and checks the return type, never asserting specific field values.

**`run_critic_audit.py` behavior.** The script auto-computes a heuristic for
`raises_coverage_complete` and `collaborator_mocks_speced` axes and sets
`checklist.rubric_gaming` to `fail` on mismatch. Other axes require manual
inspection of `rubric_axis_a_results` against the test file.

---

## 3. Item 2: Rubric Blind Spot

**What it checks.** Does the rubric ratify any contract dimension it does not
explicitly ask about? If a Critic verdict of PASS means "the rubric says PASS"
but the rubric never asked about a dimension that matters (e.g., error
propagation semantics, concurrency safety, serialization correctness), then
PASS is misleading -- the rubric is ratifying by silence.

**Pass criteria.**
- Every axis in the rubric (`rubric_axis_a_results`) maps to a contract
  dimension that is explicitly named and scoped in the rubric file
  (`cdt-rubric.md` or `ct-rubric.md`).
- No axis is labeled `true` for a reason that relies on an implicit assumption
  the rubric text never states.
- `critique_notes` on any FAIL verdict does not reference a contract dimension
  absent from the rubric axes list.

**Fail criteria.**
- The Critic marks an axis `true` citing a quality dimension not listed in the
  rubric (e.g., "test validates error message format" but `invariants_asserted`
  only asks about data-shape invariants per the rubric text).
- A PASS verdict ratifies behavior that the rubric axes do not cover at all
  (the gap is invisible because no axis can trigger FAIL for that dimension).
- `critique_notes` on a FAIL cites a defect outside any axis scope, indicating
  the Critic has criteria the rubric did not declare.

**Reasoning examples.**
- PASS: `collaborator_mocks_speced` axis passes because the rubric text explicitly
  requires "mock constructors accept keyword args for all injected dependencies"
  and the test file demonstrates this.
- FAIL: PASS verdict with a per-target note that "integration path is present"
  but neither `cdt-rubric.md` nor the axis list mentions integration path
  coverage for CDT -- the Critic created an undeclared criterion.

**Operator action.** This item is manual. `run_critic_audit.py` sets
`checklist.rubric_blind_spot = 'pass'` on initial emit. If you identify a blind
spot, set `rubric_axis_b_results.blind_spot_identified = true` on the affected
per-target row AND set `checklist.rubric_blind_spot = 'fail'` in the top-level
checklist. Document the specific gap in `rubric_axis_b_results.notes`.

---

## 4. Item 3: Correlated Convergence

**What it checks.** Are the Critic's verdicts across the 5 audited targets
correlated in the same direction? Five wrong-in-the-same-way verdicts must be
detected as a class -- they indicate a systematic bias in the Critic or rubric,
not independent correct verdicts.

**Pass criteria.**
- The 5 per-target `rubric_axis_a_results` show variation: at least two targets
  differ on at least one axis boolean, OR targets cover different contract
  surfaces (different failure modes, different axis combinations).
- `correlated_with` lists in `rubric_axis_c_results` are not all pointing to
  all other targets simultaneously (which would indicate a single identical
  fingerprint across all 5).

**Fail criteria.**
- All 5 targets have identical axis boolean patterns (`correlated_with` for each
  target lists all other 4 targets).
- Every PASS verdict is based on the exact same assertion style (e.g., all 5
  test files assert only `response.status_code == 200` with no variation in
  assertion depth).
- All FAIL verdicts cite the exact same axis as the failing one -- systematic
  False in a single axis across 5 independent targets without variation.

**Multi-sample reasoning guidance.**
1. Inspect `rubric_axis_c_results.correlated_with` for each row. A fully
   populated `correlated_with` list (all 4 other targets) on every row means
   zero diversity -- checklist item should fail.
2. Check whether diversity is cosmetic (different `target_id` but identical
   assertion patterns) vs. substantive (different contract dimensions covered).
3. Correlated PASS verdicts that share an axis fingerprint but test genuinely
   different system behaviors are acceptable -- the axis fingerprint is a proxy
   for rubric coverage, not for test content.

**`run_critic_audit.py` behavior.** The script auto-computes axis fingerprints
across the N=5 sample and sets `checklist.correlated_convergence = 'fail'` when
all fingerprints are identical.

---

## 5. Item 4: Actionable critique_notes

**What it checks.** When the Critic issued a FAIL or AMBIGUOUS verdict, did its
`critique_notes` give the Author actionable signal? Actionable means the notes
name a specific axis AND identify a specific contract dimension the test missed
-- not generic feedback like "test needs improvement."

**Pass criteria.**
- Every FAIL and AMBIGUOUS verdict in the sample has `critique_notes` that
  mentions at least one recognized axis name (`payload_shape_covered`,
  `invariants_asserted`, `collaborator_mocks_speced`, `raises_coverage_complete`,
  `seam_fan_coverage`, `cdt_ct_mock_spec_consistent`, `integration_path_asserted`).
- The critique identifies what the test was missing, not just that it failed.
- After reading the critique, the Author would know which axis to address and
  what specific assertion to add.

**Fail criteria.**
- `critique_notes` for a FAIL verdict contains no axis name reference.
- Notes are generic: "test needs more coverage", "assertions are incomplete",
  "mock setup is insufficient" without specifying which axis and which dimension.
- `rubric_axis_d_results.actionable = false` on any per-target row with a
  non-PASS final_status.

**Heuristic hints (for manual confirmation).**
- An actionable note should name an axis AND a payload dimension. Example:
  "raises_coverage_complete: test misses the threshold=0.0 edge case; no
  `pytest.raises(ValueError)` for the boundary condition."
- A non-actionable note looks like: "The test file does not fully assert the
  contract." -- no axis name, no specific dimension.
- Look for axis field names verbatim in `critique_notes`. The heuristic in
  `rubric_axis_d_results.actionable` checks for this; manual confirmation is
  whether the note would actually unblock the Author.

**`run_critic_audit.py` behavior.** The script auto-sets
`rubric_axis_d_results.actionable` based on whether `critique_notes` mentions
at least one axis name. It sets `checklist.actionable_critique_notes = 'fail'`
if any non-PASS verdict has `actionable = false`.

---

## 6. Manual Field Guidance

These fields are operator-owned (D-07 trampoline-gap extensions at audit tier,
per D-22). They default to sentinels in the emitted audit YAML. Populate them
during the review session.

### `prose_revised_between_attempts`

Set to `true` if the operator revised upstream prose (PRD, roadmap, or
`component-contracts.yaml` responsibilities field) between consecutive Author
attempts for this target. Default `false` means no prose revision occurred.

When to set `true`: If an Author retry was triggered by a structural ambiguity
that required a roadmap or PRD clarification, not just a test authoring error.

Evidence trigger: If the median `prose_revised_between_attempts` across N=5
is `false` while the median `attempt_count` exceeds 2 across multiple consumer
projects, this trips the D-07 evidence trigger -- revisit D-04 pick or amend
R2 clause (5).

### `menu_efficacy_flag`

Operator sets this to record where the defect was caught in the workflow:
- `caught_at_specify`: The /challenge menu at /io-specify Step E surfaced the
  defect before the architect phase.
- `caught_at_architect`: The defect was caught at the architect phase (after
  /io-specify but before meso-tier execution).
- `caught_at_meso`: The defect surfaced at CDT/CT execution (meso tier).
- `not_applicable`: No defect was caught; target reached PASS on first attempt.

Evidence trigger: If 2 or more targets across the N=5 sample have
`caught_at_architect` AND `roadmap_tier_defect_logged: true` (with confirmation
that the /io-specify /challenge menu would have caught it earlier), this trips
the D-05/D-06 evidence trigger -- consider promoting Path B formal
roadmap-evaluator.

### `roadmap_tier_defect_logged`

Set to `true` if the root cause of any FAIL verdict for this target was
identified as a roadmap-tier defect (NFR gap, missing contract surface, wrong
tier ownership) AND a D-NN entry was logged in `decisions.md` recording the
finding. Default `false`.

Constraint: only set `true` if an actual decisions.md entry exists for this
defect class. Do not set speculatively.

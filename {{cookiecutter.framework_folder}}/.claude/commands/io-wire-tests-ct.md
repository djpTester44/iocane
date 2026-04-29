---
name: io-wire-tests-ct
description: Run the CT (Connectivity Test) wave of wire-tests. Actor-Critic inner loop per seam-edge target. Strictly downstream of /io-wire-tests-cdt -- requires CDT all-PASS convergence per D-20.
---

> **[NO PLAN MODE]**
> Autonomous orchestration. No human approval required between inner-loop turns.
> Human gate fires on AMBIGUOUS or lifetime-ceiling verdicts via FindingFile.

# WORKFLOW: IO-WIRE-TESTS-CT

**Objective:** For each seam edge in `plans/seams.yaml` lacking a CT STATUS=PASS eval, verify
the STRICT precondition (CDT all-PASS for both endpoint components), then run an Actor-Critic
inner loop: Author writes `tests/connectivity/test_<edge>.py`; Critic emits an `EvalReport`
at `.iocane/wire-tests/eval_<edge>.yaml`. Converge to STATUS=PASS / FAIL / AMBIGUOUS per
target. Post-batch: detect parallel write collisions; sweep resolved FindingFiles on
all-PASS targets.

CT is strictly downstream of CDT. The CDT all-PASS requirement (D-20) is structurally
enforced: targets whose CDT evals are absent, non-PASS, or collision-tainted are skipped with
a distinct FindingFile per failure reason. The batch continues with valid targets.

**Position in chain:**

```
/io-architect -> /io-wire-tests-cdt -> [/io-wire-tests-ct]
             -> /io-checkpoint -> /validate-plan -> /io-plan-batch
```

---

## PRECONDITIONS

| Check | Required state |
|-------|----------------|
| `plans/seams.yaml` | Exists and parses via `seam_parser.py` |
| `plans/component-contracts.yaml` | Exists |
| `.claude/iocane.config.yaml` `wire_tests:` block | Present |
| `.iocane/architect-mode` sentinel | Must be absent |
| Per-target: CDT test files | `tests/contracts/test_<src>.py` AND `test_<dst>.py` exist |
| Per-target: CDT eval STATUS | `.iocane/wire-tests/eval_<src>.yaml` AND `eval_<dst>.yaml` STATUS=PASS |
| Per-target: CDT collision markers | Neither `eval_<src>.yaml.collision-tainted` nor `eval_<dst>.yaml.collision-tainted` present |

The first four are batch-level: failure halts the entire run. The last three are per-target:
failure emits a FindingFile for that target and skips it; the batch continues with valid
targets.

---

## INVOCATION

```
/io-wire-tests-ct [--targets edge1,edge2,...]
```

- Without `--targets`: enumerates all DI edges from `plans/seams.yaml`. Edges whose CT eval
  YAML already carries STATUS=PASS are skipped before the precondition gate.
- With `--targets`: restricts to the named comma-separated edge identifiers. Edge IDs use the
  convention `<src>__<dst>` derived from `seam_parser.all_di_edges` (src = dependency
  provider, dst = consuming component).

The slash-command resolves to `.claude/scripts/io-wire-tests-ct.sh`.

---

## BEHAVIOR

### Precondition gate

For each candidate target, the orchestrator resolves src + dst from `plans/seams.yaml` and
checks all three precondition conditions. On failure: a FindingFile is emitted to
`.iocane/findings/` with a distinct `defect_kind` (see Exit States table), and the target is
excluded from the fan-out batch. Targets that pass all three checks proceed to fan-out.

### Fan-out

Valid targets run in parallel up to `wire_tests.parallel.limit` (default 4). Each target
dispatches `.claude/scripts/run_actor_critic_loop.sh --target-type ct`. Per-target logs land
in `.iocane/wire-tests/run-log/<edge_id>.log`. An implicit barrier at the command boundary
collects all results before post-batch steps run.

### Inner-loop bound

Each target runs at most `wire_tests.max_turns` (default 5) Author spawns. AMBIGUOUS verdicts
halt to human via FindingFile and do NOT count against MAX_TURNS. FAIL verdicts trigger Author
retry with `--retry-attempt <N>` + `--prior-eval-path` and count against MAX_TURNS. Empty
`critique_notes` on FAIL or AMBIGUOUS is malformed, caught by `eval_parser.py`, and counts
against MAX_TURNS.

### Post-batch collision detection (D-21 rev 4)

After the barrier, the orchestrator scans `.iocane/wire-tests/spawn-log/` for write-target
paths claimed by more than one session ID. On collision: the CT test file is archived to
`.iocane/wire-tests/archive/collision/`; the CT eval YAML is renamed `.collision-tainted`; a
FindingFile is emitted to `.iocane/findings/`.

### Resolved-suffix sweep

On CT STATUS=PASS + no collision for a target: prior FindingFiles matching that target are
renamed `.resolved`.

---

## EXIT STATES

| State | Defect_kind | Operator next-action |
|-------|-------------|----------------------|
| Precondition: CDT test file missing | `ct_precondition_cdt_missing` | Run `/io-wire-tests-cdt --targets <missing>` first |
| Precondition: CDT not PASS | `ct_precondition_cdt_not_pass` | Resolve CDT FAIL/AMBIGUOUS for the named component before re-running CT |
| Precondition: CDT collision-tainted | `ct_precondition_cdt_collision_tainted` | Archive + re-author + re-run CDT to PASS for tainted component before re-running CT |
| All-PASS | -- | `/io-checkpoint` Phase 5+ S6 may proceed |
| Per-target AMBIGUOUS | `actor_critic_ambiguous` | Review FindingFile + eval YAML; if aggregate >= 3 write `.iocane/wire-tests/lifetime/<target>.reset` before re-invoking |
| Per-target MAX_TURNS exhausted | `actor_critic_max_turns` | Review; revise rubric or Author prompt context; re-invoke with `--targets <edge>` |
| Lifetime ceiling | `actor_critic_lifetime_max` | Write `.iocane/wire-tests/lifetime/<target>.reset`; orchestrator zeroes counter on next invocation |
| Collision detected | `parallel_write_collision` | Investigate concurrent invocations; re-run `--targets <edge>` after cleanup |
| Infrastructure failure | -- (non-zero exit) | Inspect `.iocane/wire-tests/run-log/`; resolve filesystem state; re-invoke |

Non-zero orchestrator exit indicates infrastructure failure only. Terminal inner-loop states
(PASS, FAIL-exhausted, AMBIGUOUS) all exit the inner loop with exit 0.

---

## HANDOFF

- **All-PASS:** `/io-checkpoint` (Phase 5+ S6) reads both `tests/contracts/` and
  `tests/connectivity/` for its slicing heuristic. Both CDT and CT must complete before
  `/io-checkpoint` runs.
- **Calibration:** `run_critic_audit.py` (Step 4.9) consumes N=5 PASS verdicts (CT type) for
  the ship-gate audit pass.

---

## NOTES

- Capability template `io-wire-tests.ct` brackets each Author spawn (write scope:
  `tests/connectivity/test_*.py`). Capability template `io-wire-tests.critic` brackets each
  Critic spawn (write scope: `.iocane/wire-tests/eval_*.yaml`). Grants are issued pre-spawn
  and revoked post-loop.
- Edge identifiers use `<src>__<dst>` convention (double underscore). `src` is the DI
  provider; `dst` is the consuming component. Derived from `seam_parser.all_di_edges` which
  returns `(component, dependency)` tuples -- edge_id = `{dependency}__{component}`.
- Cross-invocation AMBIGUOUS aggregate tracked in `.iocane/wire-tests/lifetime/<edge_id>.json`
  (D-19). Ceiling is 3 across operator re-invocations. Operator resets via explicit sentinel;
  orchestrator deletes sentinel after reading and zeros the counter.
- Canonical spec for CT Author context-payload contract:
  `plans/v5-meso-pivot/wire-tests-payload-contracts.md` (D-09). CT Author read-only paths
  include `tests/contracts/test_<src>.py` + `test_<dst>.py` for mock-factory reuse -- this
  is why CDT all-PASS is a hard structural requirement, not advisory.

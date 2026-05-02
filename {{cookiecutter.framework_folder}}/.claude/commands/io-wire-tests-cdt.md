---
name: io-wire-tests-cdt
description: Run the CDT (Contract-Driven Test) wave of wire-tests. Actor-Critic inner loop per ComponentContract target. Empirical validation site for the architecture authored by /io-architect.
---

> **[NO PLAN MODE]**
> Autonomous orchestration. No human approval required between inner-loop turns.
> Human gate fires on AMBIGUOUS or lifetime-ceiling verdicts via FindingFile.

# WORKFLOW: IO-WIRE-TESTS-CDT

**Objective:** For each CDT target in `plans/component-contracts.yaml` lacking a STATUS=PASS
eval, run an Actor-Critic inner loop: Author writes `tests/contracts/test_<id>.py`; Critic
emits an `EvalReport` at `.iocane/wire-tests/eval_<id>.yaml`. Converge to STATUS=PASS /
FAIL / AMBIGUOUS per target. Post-batch: detect parallel write collisions; sweep resolved
FindingFiles on all-PASS targets.

This is the empirical validation site for the architecture authored in `/io-architect`. CDT
is the root of the wire-tests DAG. `/io-wire-tests-ct` is strictly downstream -- it carries
a hard precondition: CDT all-PASS convergence (D-20).

**Position in chain:**

```
/io-architect -> [/io-wire-tests-cdt] -> /io-wire-tests-ct
             -> /io-checkpoint -> /validate-plan -> /io-plan-batch
```

---

## PRECONDITIONS

| Check | Required state |
|-------|----------------|
| `plans/component-contracts.yaml` | Exists and parses via `contract_parser.py` |
| `plans/symbols.yaml` | Exists |
| `.claude/iocane.config.yaml` `wire_tests:` block | Present |
| `.iocane/architect-mode` sentinel | Must be absent |

If any precondition fails, the orchestrator halts with a message naming the missing
condition.

---

## INVOCATION

```
/io-wire-tests-cdt [--targets id1,id2,...]
                   [--max-turns N]
                   [--max-targets N]
                   [--parallel N]
```

- `--targets` -- without it, enumerates all CDT targets in `plans/component-contracts.yaml`
  whose eval YAML is absent or carries STATUS != PASS (PASS targets are skipped). With it,
  restricts to the named comma-separated IDs regardless of current status.
- `--max-turns N` -- per-target Author/Critic retry ceiling. Overrides
  `wire_tests.max_turns` (default 5). Positive integer.
- `--max-targets N` -- caps the batch to the first N unprocessed targets after PASS-skip.
  Use for manual testing without running the full contract set. Positive integer; default
  unlimited.
- `--parallel N` -- fan-out concurrency. Overrides `wire_tests.parallel.limit`
  (default 4). Positive integer.

The slash-command resolves to `.claude/scripts/io-wire-tests-cdt.sh`.

---

## BEHAVIOR

### Fan-out

Targets run in parallel up to `wire_tests.parallel.limit` (default 4). Each target
dispatches `.claude/scripts/run_actor_critic_loop.sh --target-type cdt`. Per-target logs
land in `.iocane/wire-tests/run-log/<target_id>.log`. An implicit barrier at the command
boundary collects all results before post-batch steps run.

### Inner-loop bound

Each target runs at most `wire_tests.max_turns` (default 5) Author spawns. AMBIGUOUS
verdicts halt to human via FindingFile and do NOT count against MAX_TURNS. FAIL verdicts
trigger Author retry with `--retry-attempt <N>` + `--prior-eval-path` and count against
MAX_TURNS. Empty `critique_notes` on FAIL or AMBIGUOUS is malformed, caught by
`eval_parser.py`, and counts against MAX_TURNS.

### Post-batch collision detection (D-21 rev 4)

After the barrier, the orchestrator scans `.iocane/wire-tests/spawn-log/` for write-target
paths claimed by more than one session ID. On collision: the test file is archived to
`.iocane/wire-tests/archive/collision/`; the eval YAML is renamed `.collision-tainted`; a
FindingFile is emitted to `.iocane/findings/`.

### Resolved-suffix sweep

On STATUS=PASS + no collision for a target: prior FindingFiles matching that target are
renamed `.resolved`.

---

## EXIT STATES

| State | Signal | Operator next-action |
|-------|--------|----------------------|
| Refuse-to-launch (mutex) | stderr error citing running orchestrator's PID/SID/command/start-time; orchestrator exits 75 | Wait for existing run to complete OR force-stop via `wire-tests-panic-stop.ps1` (see CONCURRENCY + ABORTING A RUN) |
| All-PASS | All eval YAMLs STATUS=PASS, no collision | `/io-wire-tests-ct` may proceed |
| Per-target AMBIGUOUS | FindingFile `defect_kind=actor_critic_ambiguous` | Review FindingFile + eval YAML; if aggregate >= 3, write `.iocane/wire-tests/lifetime/<target>.reset` before re-invoking |
| Per-target MAX_TURNS exhausted | FindingFile `defect_kind=actor_critic_max_turns` | Review; revise rubric or Author prompt context; re-invoke with `--targets <id>` |
| Per-target API error envelope | FindingFile `defect_kind=api_error_envelope` (Author or Critic `is_error=true`: 429 rate-limit, 529 overloaded, 401/403 auth, 5xx server, etc.); inner loop exit 64 | Read snapshot in finding `where` field for `api_error_status`. 429/529 -> wait for window reset; 401/403 -> fix credentials; 5xx -> brief backoff. Re-run with `--targets <id>`. Does NOT consume a turn or archive the test file. |
| Per-target infra failure mid-write | FindingFile `defect_kind=spawn_kill_or_infra_failure` (claude -p partial-wrote then exited: network reset, server abort, or other mid-stream failure); inner loop exit 65 | Inspect `run-log/<id>.log` for the failure mode. Re-run with `--targets <id>`. Does NOT consume a turn. Panic-stop kills are recorded separately under `panic_stop_audit` (see below). |
| Panic-stop invoked | FindingFile `defect_kind=panic_stop_audit` written by `wire-tests-panic-stop.ps1` after convergence; one finding per panic-stop invocation listing all killed processes + result-file state | Review the audit FindingFile to see what was killed and which result files have 0-byte / partial state to clean up. Re-run wire-tests with `--targets <id>` for any targets you want to retry. |
| Lifetime ceiling | FindingFile `defect_kind=actor_critic_lifetime_max` (aggregate AMBIGUOUS >= 3) | Author `.iocane/wire-tests/lifetime/<target>.reset`; orchestrator clears counter on next invocation |
| Collision detected | FindingFile `defect_kind=parallel_write_collision`; test + eval archived | Investigate concurrent invocations; re-run `--targets <id>` after cleanup |
| Infrastructure failure | Orchestrator exits non-zero; spawn / archive / lifetime-rename failed | Inspect `.iocane/wire-tests/run-log/`; resolve filesystem state; re-invoke |

Non-zero orchestrator exit indicates infrastructure failure only. Terminal inner-loop states
(PASS, FAIL-exhausted, AMBIGUOUS) all exit the inner loop with exit 0.

---

## HANDOFF

- **All-PASS:** `/io-wire-tests-ct` reads `tests/contracts/` and matches CDT eval YAMLs for
  STATUS=PASS as its entry precondition (D-20). No manual step required between the two
  commands.
- **Downstream checkpoint:** `/io-checkpoint` (Phase 5+ S6) reads both `tests/contracts/`
  and `tests/connectivity/` for its slicing heuristic. Both CDT and CT must complete before
  `/io-checkpoint` runs.
- **Calibration:** `run_critic_audit.py` (Step 4.9) consumes N=5 PASS verdicts per test-type
  for the ship-gate audit pass.

---

## CONCURRENCY

The orchestrator holds an advisory pidfile lock at
`.iocane/wire-tests/.orchestrator.pid` for its lifetime. The lock is
shared between CDT and CT orchestrators (single pidfile path) --
concurrent CDT+CT launches collide intentionally.

If a launch finds the pidfile present AND the recorded PID is alive, it
refuses with exit 75 and prints the running orchestrator's PID, SID,
command, and start-time on stderr. Operators wait for the existing run
to complete or force-stop with `wire-tests-panic-stop.ps1` (see ABORTING
A RUN below).

If the pidfile is present but the recorded PID is dead (e.g. the previous
run was panic-stopped or TaskStop'd), the launch logs a WARN and reclaims
the pidfile.

The pidfile is removed on graceful exit (normal completion, `set -e`
propagation, `exit N`). SIGKILL leaves a stale pidfile that the next
launch reclaims via the liveness check.

## ABORTING A RUN

TaskStop and manual `Stop-Process` of the orchestrator only kill the visible parent. Leaf
`claude -p` children survive, and the inner-loop bash workers respawn replacements in the
gap between leaf-kill and `set -e` propagation. To force-stop a run:

```powershell
powershell -NoProfile -File .claude/scripts/wire-tests-panic-stop.ps1
```

(`pwsh` works too if PowerShell 7+ is installed; `powershell` is the Windows-shipped 5.1
binary, available everywhere.)

Workers-first iterative kill. Each pass: (Stage A) kill bash workers
(`io-wire-tests-{cdt,ct}` orchestrators, `run_actor_critic_loop`,
`spawn-test-{author,critic}`) -- this kills xargs and the dispatcher, so no new `claude -p`
can spawn. Then (Stage B) kill any remaining `claude -p` (now orphaned). 3s settle; recount.
Up to 3 passes; exit 0 on the first pass that finds both pools at 0.

The workers-first ordering eliminates the dispatch race that leaf-first ordering exposed
(killing a leaf caused xargs to dispatch a replacement worker for the next target). The
iterative loop converges on residuals from the smaller race window inside each pass (Stage
A's CIM enumeration is itself synchronous and may miss a mid-spawn child). Exit 1 only
appears after 3 passes have failed -- in normal operation expect exit 0 within 1-2 passes.

## NOTES

- Capability template `io-wire-tests.cdt` brackets each Author spawn (write scope:
  `tests/contracts/test_*.py`). Capability template `io-wire-tests.critic` brackets each
  Critic spawn (write scope: `.iocane/wire-tests/eval_*.yaml`). Grants are issued pre-spawn
  and revoked post-loop.
- Author retry receives `--retry-attempt <N>` + `--prior-eval-path`; the prior test file is
  archived before retry spawn. Author re-authors fresh against contracts + symbols + rubric;
  the prior file is not on disk at retry time (D-18 R5 structural read-window fence).
- Cross-invocation AMBIGUOUS aggregate tracked in `.iocane/wire-tests/lifetime/<target_id>.json`
  (D-19). Ceiling is 3 across operator re-invocations. Operator resets via explicit sentinel;
  orchestrator deletes the sentinel after reading and zeros the counter.
- Canonical spec for Author/Critic context-payload contracts:
  `plans/v5-meso-pivot/wire-tests-payload-contracts.md` (D-09; supersedes `plan-B.md §-1.4`).

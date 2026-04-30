# Workflow Usage Reference

## Scaffolding a New Project

Before any workflow runs, the harness files must be pulled into the target repo. The canonical scaffold command is a `cookiecutter` invocation against the iocane template repo. Add this helper to `~/.bashrc` so the flags are pinned and the template cache is always refreshed:

```bash
iocane-scaffold() {
  rm -rf ~/.cookiecutters/iocane && \
  uvx cookiecutter https://github.com/djpTester44/iocane.git \
    --checkout claude-specific-harnessing -f --no-input "$@"
}
```

Usage:

```bash
iocane-scaffold framework_folder=. project_name=my_project
```

Positional `key=value` pairs are forwarded as cookiecutter context. `rm -rf ~/.cookiecutters/iocane` ensures the template is re-cloned each run; `-f --no-input` makes the call non-interactive and safe to re-run.

### Without the helper

If you prefer not to define the function, run the underlying command directly:

```bash
rm -rf ~/.cookiecutters/iocane
uvx cookiecutter https://github.com/djpTester44/iocane.git \
  --checkout claude-specific-harnessing -f --no-input \
  framework_folder=. project_name=my_project
```

Omit `-f --no-input` if you want cookiecutter to prompt for each variable interactively, and drop the `rm -rf` line if you want to reuse the cached template clone.

---

## Orchestration Chain

```
Primary Path:
/io-clarify -> /io-init -> /io-specify -> /io-architect -> /io-checkpoint -> /validate-plan -> /io-plan-batch -> /validate-tasks -> dispatch-agents.sh [per CP: io-execute (generator) -> evaluator] -> /io-review

Test-authoring runs at state 3 entry via `/io-wire-tests-cdt` and `/io-wire-tests-ct` (see Wire-Tests Command Lifecycle below).


Remediation Path (after /io-backlog-triage routes DESIGN/REFACTOR items):
/io-backlog-triage -> /auto-architect -> /auto-checkpoint -> /validate-plan -> /io-plan-batch

Batch Loop (repeat until all checkpoints complete):
/io-review -> /io-plan-batch -> /validate-tasks -> dispatch-agents.sh -> /io-review

Closeout (after final batch review):
/io-review -> /gap-analysis -> /doc-sync

Recovery Path (only for out-of-band component-contracts.yaml changes):
/io-architect -> /validate-spec -> /io-checkpoint
```

---

## Wire-Tests Command Lifecycle

Wire-tests are the empirical-validation site for component contracts (CDT) and seam edges (CT). Execution follows this sequence per state 3 entry:

1. `/io-wire-tests-cdt` -- enumerates ComponentContract targets from `plans/component-contracts.yaml`; runs per-target Actor-Critic loop authoring `tests/contracts/test_<target>.py`; converges to STATUS=PASS / FAIL / AMBIGUOUS per target. No precondition.

2. `/io-wire-tests-ct` -- enumerates seam edges from `plans/seams.yaml`; **STRICT precondition:** matching CDT eval YAMLs STATUS=PASS + no collision-tainted markers; runs per-target Actor-Critic loop authoring `tests/connectivity/test_<edge>.py`.

3. Calibration ship-gate: `run_critic_audit.py --test-type <cdt|ct> --sample-size 5` audits N=5 PASS verdicts per test-type. State 3 (`/io-checkpoint`) does NOT unblock until both 5-sets clear human review.

**Authoritative spec for Author/Critic context-payload contracts:** `plans/v5-meso-pivot/wire-tests-payload-contracts.md` (D-09 supersedes plan-B.md §-1.4).

### Configuration

Wire-tests obey two configuration knobs in `.claude/iocane.config.yaml`:

- `wire_tests.max_turns` -- per-target inner-loop bound (default 5).
- `wire_tests.parallel.limit` -- per-batch parallelism cap (default 4).

### State Surfaces

Wire-tests emit and read from the following artifact surfaces:

- `tests/contracts/test_<id>.py`, `tests/connectivity/test_<id>.py` -- test files (capability templates `io-wire-tests.cdt` / `io-wire-tests.ct`).
- `.iocane/wire-tests/eval_<id>.yaml` -- Critic verdict per target (capability `io-wire-tests.critic`).
- `.iocane/wire-tests/spawn-log/<sid>/<id>-<role>-<attempt>.json` -- machine-parseable audit log (per-sid scoped).
- `.iocane/wire-tests/archive/<sid>/test_<id>-attempt-<N-1>.py` -- per-attempt test archive (D-18 R5 read-window; per-sid scoped).
- `.iocane/wire-tests/lifetime/<id>.json` -- cross-invocation AMBIGUOUS counter (D-19).
- `.iocane/findings/wire_test_*.yaml` -- FindingFiles emitted on halts.

---

## Dispatching Agents

After `/io-plan-batch` accepts a batch and writes task files, run `/validate-tasks`, then dispatch agents:

```bash
bash .claude/scripts/dispatch-agents.sh
```

### Resuming a Failed Checkpoint

When a sub-agent hits the max-turns ceiling mid-pipeline, its worktree is preserved. To re-enter the pipeline at Phase 3 (generate-evaluate loop) for that checkpoint:

```bash
bash .claude/scripts/dispatch-agents.sh --resume CP-XX
```

Resume mode skips the escalation flag gate, clean-tree gate, batch collection, and CI sidecar pre/post-wave. It validates the worktree exists, the correct branch is checked out, and the task file is present, then enters the generate-evaluate-regen loop directly.

---

## Standalone Scripts (Run Explicitly)

These are operator-facing scripts. Run them directly when you need the behavior.

- `bash .claude/scripts/dispatch-agents.sh [--resume CP-XX]`: dispatches pending checkpoint tasks. With `--resume`, re-enters the pipeline for a single preserved worktree.
- `bash .claude/scripts/ci-sidecar.sh`: full suite regression detection (advisory). Subcommands: `pre-wave`, `post-wave`, `diff`. Config: `ci.timeout` (default 5m), `ci.enabled` (default true). Env overrides: `CI_TIMEOUT`, `CI_ENABLED`. Called automatically by dispatch-agents.sh; can also be run standalone.
- `bash .claude/scripts/reset-failed-checkpoints.sh`: resets failed checkpoints for re-queue.
- `bash .claude/scripts/archive-approved.sh`: archives approved checkpoint artifacts from `plans/tasks/` into `plans/archive/` and updates `plans/plan.yaml` status from `[ ] pending` to `[x] complete`. For remediation CPs, resolves the source backlog item via `Source BL:` lookup.
- `bash .claude/scripts/assign_backlog_ids.py`: assigns `BL-NNN` identifiers to any backlog items missing them. Idempotent -- safe to re-run.
- `bash .claude/scripts/route_backlog_item.py BL-NNN CP-NNR [--prompt TEXT]`: adds a `Routed` annotation (with optional routing prompt) to the specified backlog item. Fails if the item is not found or already routed to that CP.
- `bash .claude/scripts/pre-invoke-validate-tasks.sh` -- internal: pre-invocation gate before /validate-tasks
- `uv run .claude/scripts/merge_pyproject.py`: compares existing `pyproject.toml` against harness-required config and reports or applies only the missing pieces. Union merge for list fields (`ruff select/ignore`, dev packages); add-only for scalars; divergences reported but never auto-corrected. Called automatically by `/io-adopt` (step 1c) and `/io-init` (step C) when `pyproject.toml` already exists.

  ```bash
  uv run .claude/scripts/merge_pyproject.py           # check mode (default) -- exits 1 if gaps found
  uv run .claude/scripts/merge_pyproject.py --write   # apply additions
  uv run .claude/scripts/merge_pyproject.py --path path/to/pyproject.toml  # explicit path
  ```

- `uv run .claude/scripts/sync_dir_claude.py`: regenerates directory-level CLAUDE.md files
  in `src/` subdirectories from component-contracts.yaml, project-spec.md, seams.yaml, and
  pyproject.toml. Called automatically by `/io-architect`, `/auto-architect`, `/io-review`, and `/doc-sync`.
  Can also be run standalone.

  ```bash
  uv run .claude/scripts/sync_dir_claude.py                # all directories
  uv run .claude/scripts/sync_dir_claude.py --dir src/core # single directory
  uv run .claude/scripts/sync_dir_claude.py --dry-run      # preview only
  ```

Do not run `.claude/scripts/setup-worktree.sh` directly. It is an internal helper invoked by `dispatch-agents.sh`.

The following are internal helper scripts. Do not run them directly unless debugging:

- `write-status.sh` -- internal: writes checkpoint status files during /io-execute
- `auto_checkpoint.py` -- internal: backing script for /auto-checkpoint (7-criterion filter + CP generation + backlog routing)
- `auto_architect.py` -- internal: backing script for /auto-architect (5-criterion filter + dependency graph + JSON manifest)
- `backlog_parser.py` -- internal: parses plans/backlog.yaml for programmatic queries
- `plan_parser.py` -- internal: parses plans/plan.yaml for programmatic queries
- `task_parser.py` -- internal: parses plans/tasks/CP-XX.yaml for programmatic queries
- `seam_parser.py` -- internal: parses plans/seams.yaml for programmatic queries
- `extract_structure.py` -- internal: AST-based project structure extraction
- `pre-invoke-io-plan-batch.sh` -- internal: pre-invocation gate before /io-plan-batch
- `check_di_compliance.py` -- internal: DI compliance checker used in REFACTOR gate
- `check_write_target_overlap.py` -- internal: write-target collision detection (includes target-CP CT files) for /io-plan-batch Step C [HARD GATE] / Step E [HARD GATE]
- `check_ct_depends_on.py` -- internal: CT dependency invariant check for /validate-plan Step 9B [HARD GATE]
- `pre-invoke-auto-checkpoint.sh` -- internal: pre-invocation gate before /auto-checkpoint
- `pre-invoke-auto-architect.sh` -- internal: pre-invocation gate before /auto-architect

---

## Autonomous Hooks (Run by Claude)

These are hook-driven and configured in `.claude/settings.json`. They are executed automatically by Claude on matching events. Hooks marked *(async)* run without blocking the tool invocation.

- `SessionStart`: `.claude/hooks/session-start.sh`
- `SessionEnd`: `.claude/hooks/session-end.sh`
- `SubagentStart`: `.claude/hooks/subagent-start.sh`
- `SubagentStop`: `.claude/hooks/subagent-stop.sh`
- `PreCompact`: `.claude/hooks/pre-compact.sh`
- `PostCompact`: `.claude/hooks/post-compact.sh`
- `Stop`: `.claude/hooks/stop-gate.sh`
- `UserPromptSubmit`: `.claude/hooks/prompt-submit.sh`
- `PreToolUse (Edit|Write)`: `.claude/hooks/workflow-state-gate.sh`, `.claude/hooks/write-gate.sh`, `.claude/hooks/secret-scan.sh`, `.claude/hooks/environ-gate.sh`, `.claude/hooks/py-create-context.sh` *(async)*, `.claude/hooks/backslash-path.sh`, `.claude/hooks/emoji-scan.sh`, `.claude/hooks/architect-boundary.sh`
- `PreToolUse (Bash)`: `.claude/hooks/forbidden-tools.sh`, `.claude/hooks/rtk-enforce.sh`
- `PostToolUse (Edit|Write)`: `.claude/hooks/reset-on-prd-write.sh`, `.claude/hooks/reset-on-project-spec-write.sh`, `.claude/hooks/reset-on-plan-write.sh`, `.claude/hooks/reset-on-symbols-write.sh`, `.claude/hooks/backlog-id-assign.sh`, `.claude/hooks/backlog-tag-validate.sh`, `.claude/hooks/archive-sync.sh` *(async)*, `.claude/hooks/validate-yaml.sh`, `.claude/hooks/task-validation-report-write.sh`
- `PostToolUse (Bash)`: `.claude/hooks/escalation-gate.sh`
- `PostToolUseFailure`: `.claude/hooks/tool-failure.sh`

Use hooks as autonomous guardrails. Use standalone scripts as explicit operational commands.

---

## Configuration

Project-level orchestration config lives in `.claude/iocane.config.yaml`.

```yaml
parallel:
  limit: 4   # Maximum number of checkpoints dispatched concurrently in a single batch
```

### `parallel.limit`

Controls how many checkpoints `/io-plan-batch` may include in a single batch. `/io-plan-batch` and `dispatch-agents.sh` both respect this value.

- Default if config file is missing: `1`
- Increase with caution -- parallelization safety is checked per batch, but higher limits increase the blast radius of a bad batch composition.

### `agents.max_turns`

Controls the maximum number of turns a sub-agent may take before the dispatcher terminates it. See `.claude/iocane.config.yaml` for the current value.

- If an agent exhausts its budget mid-run, no `.status` file is written -- the checkpoint remains pending and will be re-picked on the next dispatch, resuming from the last completed `## Step Progress` checkbox.
- If turn exhaustion recurs on a particular checkpoint, increase `agents.max_turns` in `.claude/iocane.config.yaml` before re-dispatching.
- The `IOCANE_MAX_TURNS` environment variable overrides this value for ad-hoc runs.

### Resetting failed checkpoints

```bash
bash .claude/scripts/reset-failed-checkpoints.sh          # reset all FAIL checkpoints
bash .claude/scripts/reset-failed-checkpoints.sh CP-XX    # reset a specific checkpoint
```

Removes the worktree, branch, `.status`, and `.exit` files for each named checkpoint so it can be re-queued by `/io-plan-batch`. Log files are preserved. Run `/io-plan-batch` after reset to generate a fresh task file before dispatching.

---

## Validation Stamps

Tier 1 artifacts carry validation stamps that gate downstream workflows. Any substantive write to these artifacts resets the stamp, requiring re-validation before proceeding.

| Artifact | Stamp | Gating Workflow | Gates |
|----------|-------|-----------------|-------|
| `plans/PRD.md` | `**Clarified:** True/False` (markdown) | `/io-clarify` | `/io-specify` |
| `plans/plan.yaml` | `validated: true/false` (YAML field) | `/validate-plan` Step 13 | `/io-plan-batch` |

Notes:

- `/io-architect` Step G also runs `validate_trust_edge_chain.py`: a cross-artifact validator that enforces the PRD Trust Edges <-> component-contracts raises <-> symbols Settings parameterization chain. Distinct exit codes (1 presence / 2 chain / 3 parameterization) per check; non-zero halts back to Step F. Authoring discipline lives in /io-specify Step B.5 (Trust Edges section requirement).
- `plan.yaml.validated` is set by `/validate-plan` Step 13 under an `io-architect.H`-class capability grant.
- Reset chain: symbols.yaml writes reset plan.yaml. See `docs/enforcement-mapping.md` for the full table.
- `plans/project-spec.md` is retired as a canonical artifact -- no agent reads or writes it. `/validate-spec` is retired with it (Phase 9 of the rebuild plan).

### Exempting a write from stamp reset

Workflow steps that write canonical artifacts (stamps or substantive content) bracket their writes in a **capability grant** that declares the exact paths they will write. Reset hooks consult the per-session cache at `.iocane/sessions/<session_id>.active.txt` and bypass when a matching write pattern is covered. See `.claude/references/capability-gate.md` for the primitive.

#### Pattern

    Step N-pre:  bash: uv run python .claude/scripts/capability.py grant --template <workflow>.<step>
    Step N:      [Edit/Write operations -- strictly sequential, never parallel]
    Step N-post: bash: uv run python .claude/scripts/capability.py revoke --template <workflow>.<step>

The grant covers ALL writes declared in the template. Grant templates live at `.claude/capability-templates/<workflow>.<step>.yaml` and are git-tracked + PR-reviewable (the authoritative catalog of what each step writes).

**Migrated workflows + their templates:**

- `/io-architect` Step H → `io-architect.H`
- `/io-checkpoint` Step H (used_by_cps backfill) → `io-checkpoint.H`
- `/io-clarify` Step 7 (Clarified stamp) → `io-clarify.7`
- `/validate-plan` Step 13 (validated stamp) → `validate-plan.13`
- `/io-design-evaluator` Step A (findings emission) → `io-design-evaluator.A`
- `/auto-architect` Step F (multi-artifact edit batch) → `auto-architect.architect`

**Defense in depth:** explicit revoke is primary. Session-end sweeps revoke any still-live grants. A 24-hour hard TTL ceiling clamps buggy authors as a crash-safety floor.

---

## Workflow Quick Reference

| Workflow | Purpose | Writes to |
|----------|---------|-----------|
| `/io-clarify` | Clarify PRD ambiguities and critique against quality rubric | `plans/PRD.md` |
| `/io-adopt` | Adopt an existing codebase into Iocane with extracted current-state + draft PRD | `plans/current-state.md`, `plans/PRD.md` |
| `/io-init` | Bootstrap project structure and stub roadmap from clarified PRD | `plans/roadmap.md`, `plans/backlog.yaml` |
| `/io-specify` | Propose feature roadmap from clarified PRD; identify Trust Edges (Step B.5) and render Trust Edges / Security Boundaries section in roadmap; offer operator-invokable /challenge menu at Step E pre-approval; populate `catalog.toml` from PRD + roadmap (Step F) for greenfield/brownfield parity with `/io-adopt` Step 4b | `plans/roadmap.md`, `catalog.toml` |
| `/io-architect` | Design CRC cards, component contracts, Interface Registry | `plans/project-spec.md`, `plans/component-contracts.yaml`, `plans/seams.yaml`, `src/*/CLAUDE.md` |
| `/io-replan` | Propagate PRD deltas into roadmap/spec and route impacts | `plans/roadmap.md`, `plans/project-spec.md`, `plans/backlog.yaml` |
| `/io-checkpoint` | Define atomic checkpoints and connectivity tests | `plans/plan.yaml`, `plans/backlog.yaml` (remediation: Routed annotation via script) |
| `/auto-architect` | Resolve DESIGN/REFACTOR backlog items via sub-agent research + evaluator gate | `plans/project-spec.md`, `plans/component-contracts.yaml`, `plans/seams.yaml`, `plans/backlog.yaml`, `src/*/CLAUDE.md` |
| `/auto-checkpoint` | Batch-generate remediation CPs from triage-approved routing prompts | `plans/plan.yaml`, `plans/backlog.yaml` (Routed annotation) |
| `/validate-plan` | Validate `plan.yaml` CDD compliance before batch composition | `plans/plan.yaml` (stamp only) |
| `/io-plan-batch` | Compose dispatch batch, score confidence, get human approval | `plans/tasks/CP-XX.yaml` (on acceptance) |
| `/validate-tasks` | Validate task files against plan.yaml and component-contracts.yaml | `plans/tasks/CP-XX.task.validation`, `plans/validation-reports/task-validation-report.yaml` |
| `/task-recovery` | Regenerate task files for CPs with MECHANICAL findings | `plans/tasks/CP-XX.yaml` (regenerated) |
| `dispatch-agents.sh` | Dispatch agents (run directly via `bash .claude/scripts/dispatch-agents.sh [--resume CP-XX]`) | none |
| `/io-execute` | Tier 3 sub-agent workflow that executes one checkpoint task file | `plans/tasks/CP-XX.status`, checkpoint write targets |
| `/validate-spec` | Detect CRC-contract drift and re-earn `**Approved:** True` (recovery path) | `plans/project-spec.md` (stamp only) |
| `/doc-sync` | Reconcile docs with codebase after feature completion | `plans/project-spec.md`, `plans/roadmap.md`, `plans/seams.yaml`, `README.md`, `src/*/CLAUDE.md` |
| `/io-review` | Post-implementation review | `plans/seams.yaml` (Step F), `src/*/CLAUDE.md` (Step F-post), `plans/review-output.yaml` (via `stage_review_findings.py`) |
| `/io-backlog-triage` | Drain staging + triage open backlog items with approved routing decisions | `plans/backlog.yaml` (reads `plans/review-output.yaml` staging) |
| `/io-ct-remediate` | Remediation flow: create missing connectivity test(s) from CT spec for archived checkpoints. Imports both sides real; runs gate; closes backlog entry. | CT file path from `plans/plan.yaml`, `plans/backlog.yaml` |
| `/gap-analysis` | Identify gaps between implementation and spec | `plans/review-output.yaml` (via `stage_review_findings.py`) |
| `/run-state-snapshot` | Workflow-agnostic mid-run state capture: host-authored draft + mechanical enumeration composed into a snapshot doc | `.iocane/drafts/run-state-draft.yaml`, `.iocane/findings/<datestamp>_<workflow>-state.md` |
| `/lessons-retro` | Manually trigger two-pass lesson extraction (Sonnet -> Opus xhigh) against current session transcript | `.lessons/retro-review/<stamp>-proposal.md`, `.lessons/.pending-review` |
| `/lessons-retro-review` | Review and apply most recent `/lessons-retro` proposal; route lessons to GLOBAL/WORKSPACE rule files | `.claude/rules/learned-rules.md`, `.lessons/workspace-rules/<topic>-learned.md`, `.lessons/deferred.yaml` |

---

## Additional Workflow Paths

These workflows are part of the full lifecycle and are intentionally outside the single linear happy path:

- Brownfield adoption path: `/io-adopt` -> `/io-clarify` -> `/io-init` -> `/io-specify` -> `/io-architect`.
- Execution internals: `dispatch-agents.sh` dispatches Tier 3 sub-agents that run `/io-execute` per checkpoint task file.
- Post-review backlog routing: `/io-review` -> `stage_review_findings.py` (staging) -> `/io-backlog-triage` (drain to backlog) -> (`/auto-architect` | `/auto-checkpoint` | `/validate-plan` | `/io-ct-remediate`) based on tag/risk.
- Archived checkpoint CT recovery: `/io-review` (detect missing CT) -> `/io-ct-remediate` -> backlog item resolved.
- PRD-change replan path (non-linear): `/io-replan` when requirements change after initial planning.

---

## Lesson Capture (manual)

Outside the orchestration chain, the harness provides a manual learning-extraction loop for capturing per-session lessons (corrections, preferences, friction patterns) into rule files. Local-only by design: workspace-scoped lessons live in gitignored `.lessons/` and never propagate via migration. Only items promoted to `.claude/rules/learned-rules.md` (Global section) are committed.

**Pipeline (two slash commands, manual sequence):**

1. `/lessons-retro` -- runs a two-pass extraction pipeline against the current session's JSONL transcript:
   - Pass 1 (Sonnet, standard tier) walks the transcript and emits raw lesson candidates as JSONL records (corrections, preferences, friction, implicit signals).
   - Pass 2 (Opus, extended thinking) classifies each candidate into GLOBAL or WORKSPACE tier, sanitizes source quotes, and writes a Markdown proposal to `.lessons/retro-review/<stamp>-proposal.md`.
   - Pipeline runs synchronously (~1-3 min). Sets `.lessons/.pending-review` flag on completion.

2. `/lessons-retro-review` -- review and apply the most recent proposal:
   - User edits `**Decision:**` checkboxes in the proposal Markdown to mark each item PROMOTE / DEFER / DISCARD (unmarked items are treated as DISCARD by default with a warning at confirmation).
   - Slash command parses decisions, shows summary across the four buckets, asks for a single y/N confirmation.
   - On approval: GLOBAL items appended to `.claude/rules/learned-rules.md`; WORKSPACE items written to `.lessons/workspace-rules/<topic>-learned.md`; DEFER items registered in `.lessons/deferred.yaml`; proposal archived to `.lessons/retro-review/archive/`.
   - At start of every run, prior deferred entries from `.lessons/deferred.yaml` are surfaced as a heads-up.

**State layout (`.lessons/`, gitignored):**

- `tmp/` -- Pass 1 output JSONL (transient; removed by `promote.sh` on finalize)
- `retro-review/` -- live proposals awaiting review
- `retro-review/archive/` -- archived proposals (kept indefinitely; cross-referenced from `deferred.yaml`)
- `workspace-rules/` -- topic-scoped local-only rule files
- `debug/` -- pipeline log + raw `claude -p` envelope JSONs
- `deferred.yaml` -- registry of DEFERRED items pointing into archive
- `.cooldown` -- timestamp file (5 min default; bypassed in manual mode)
- `.skip-log` -- record of cooldown-skipped invocations
- `.pending-review` -- flag file present when a proposal awaits review

**Optional config override:** `.lessons/config.yaml` accepts simple `key: value` overrides for `enabled`, `cooldown_minutes`, `review_reminder_hours`. Defaults are baked into `invoke-retro.sh`. `auto_promote` is hard-coded to `0` and not overridable from config.

**Auto-trigger on `/clear`:** not currently wired. The single-script trigger (modification to `session-start.sh` to fork `invoke-retro.sh` detached on `source==clear` SessionStart) is documented in the build plan and deferred pending operator decision.

---

## Model Allocation

Model assignments are defined in `.claude/iocane.config.yaml` under the `models` key:

```yaml
models:
  tier1: claude-opus-4-6           # Strategic: io-clarify, io-architect, io-checkpoint, review
  tier2: claude-sonnet-4-6         # Orchestration: io-plan-batch, validate-plan, validate-spec
  tier3: claude-haiku-4-5-20251001 # Execution: io-execute sub-agents (dispatch-agents.sh)
```

- **Tier 1 (interactive workflows):** `models.tier1` is documented guidance only. The user selects the active model in their Claude Code session; the config entry communicates intent.
- **Tier 2 (orchestration workflows):** `models.tier2` is documented guidance only. `/io-plan-batch`, `/validate-plan`, and `/validate-spec` run interactively in the user's session.
- **Tier 3 (sub-agents):** `models.tier3` is the value `dispatch-agents.sh` passes to `claude -p --model`. This is the only model setting that is programmatically enforced.
- **Override:** The `IOCANE_MODEL` environment variable overrides `models.tier3` for ad-hoc runs when the config is absent or unreadable.

---

## Workflows that never run as sub-agents (Tier 1 -- interactive only)

The following workflows require human interaction and must never be dispatched headlessly:

- `/io-clarify`
- `/io-specify`
- `/io-architect`
- `/auto-architect`
- `/io-checkpoint`
- `/validate-spec`
- `/io-review`

---

## Notes

- `component-contracts.yaml` writes (out-of-band, outside `/io-architect`) reset both `project-spec.md` approval and `plan.yaml` validation. Always use `/io-architect` to modify contracts. If a `component-contracts.yaml` change is unavoidable, run `/validate-spec` to recover the `**Approved:** True` stamp before proceeding to `/io-checkpoint`.

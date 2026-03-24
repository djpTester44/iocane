# Workflow Usage Reference

## Orchestration Chain

```
Primary Path:
/io-clarify -> /io-init -> /io-specify -> /io-architect -> /io-checkpoint -> /validate-plan -> /io-plan-batch -> /io-orchestrate -> /io-review

Batch Loop (repeat until all checkpoints complete):
/io-review -> /io-plan-batch -> /io-orchestrate -> /io-review

Closeout (after final batch review):
/io-review -> /gap-analysis -> /doc-sync

Recovery Path (only for out-of-band .pyi changes):
/io-architect -> /validate-spec -> /io-checkpoint
```

---

## Dispatching Agents

After `/io-plan-batch` accepts a batch and writes task files, you have two equivalent options to dispatch agents:

**Option A — Workflow alias:**

```
/io-orchestrate
```

**Option B — Direct script invocation:**

```bash
uv run bash .claude/scripts/dispatch-agents.sh
```

Both options are equivalent. `/io-orchestrate` is a thin alias for the script invocation provided for discoverability. Direct invocation is preferred if you are comfortable with the CLI.

---

## Standalone Scripts (Run Explicitly)

These are operator-facing scripts. Run them directly when you need the behavior.

- `uv run bash .claude/scripts/dispatch-agents.sh`: direct alternative to `/io-orchestrate`; dispatches pending checkpoint tasks.
- `bash .claude/scripts/reset-failed-checkpoints.sh`: resets failed checkpoints for re-queue.
- `bash .claude/scripts/archive-approved.sh`: archives approved checkpoint artifacts from `plans/tasks/` into `plans/archive/` and updates `plans/plan.md` status from `[ ] pending` to `[x] complete`. For remediation CPs, resolves the source backlog item via `Source BL:` lookup.
- `bash .claude/scripts/assign-backlog-ids.sh`: assigns `BL-NNN` identifiers to any backlog items missing them. Idempotent -- safe to re-run.
- `bash .claude/scripts/route-backlog-item.sh BL-NNN CP-NNR`: adds a `Routed:` annotation to the specified backlog item. Fails if the item is not found or already routed to that CP.

Do not run `.claude/scripts/setup-worktree.sh` directly. It is an internal helper invoked by `dispatch-agents.sh`.

The following are internal helper scripts. Do not run them directly unless debugging:

- `write-status.sh` -- internal: writes checkpoint status files during /io-execute
- `backlog_parser.py` -- internal: parses plans/backlog.md for programmatic queries
- `extract_structure.py` -- internal: AST-based project structure extraction
- `smart_search.sh` -- internal: targeted codebase search utility
- `pre-invoke-io-plan-batch.sh` -- internal: pre-invocation gate before /io-plan-batch
- `check_di_compliance.py` -- internal: DI compliance checker used in REFACTOR gate

---

## Autonomous Hooks (Run by Claude)

These are hook-driven and configured in `.claude/settings.json`. They are executed automatically by Claude on matching events.

- `SessionStart`: `.claude/hooks/session-start.sh`
- `PreToolUse (Edit|Write)`: `.claude/hooks/write-gate.sh`, `.claude/hooks/di-gate.sh`, `.claude/hooks/secret-scan.sh`, `.claude/hooks/environ-gate.sh`, `.claude/hooks/py-create-context.sh`, `.claude/hooks/backslash-path.sh`, `.claude/hooks/emoji-scan.sh`, `.claude/hooks/architect-boundary.sh`, `.claude/hooks/design-before-contract.sh`
- `PreToolUse (Bash)`: `.claude/hooks/forbidden-tools.sh`
- `PostToolUse (Edit|Write)`: `.claude/hooks/reset-on-prd-write.sh`, `.claude/hooks/reset-on-project-spec-write.sh`, `.claude/hooks/reset-on-plan-write.sh`, `.claude/hooks/reset-on-pyi-write.sh`, `.claude/hooks/backlog-id-assign.sh`, `.claude/hooks/backlog-tag-validate.sh`, `.claude/hooks/archive-sync.sh`
- `PostToolUse (Bash)`: `.claude/hooks/escalation-gate.sh`

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
| `plans/PRD.md` | `**Clarified:** True/False` | `/io-clarify` | `/io-architect` |
| `plans/project-spec.md` | `**Approved:** True/False` | `/io-architect` (primary) or `/validate-spec` (recovery) | `/io-checkpoint` |
| `plans/plan.md` | `**Plan Validated:** PASS/FAIL` | `/validate-plan` | `/io-plan-batch` |

Note: `/io-architect` writes `**Approved:** True` on the primary path. `/validate-spec` is the recovery path -- it re-earns the stamp after an out-of-band `.pyi` change resets it, without requiring a full redesign.

### Exempting a write from stamp reset

Workflows that write stamps (not substantive content) must bracket all writes in the approval step with sentinel file creation and deletion to prevent a reset loop:

    Step N-pre:  bash: mkdir -p .iocane && touch .iocane/validating
    Step N:      [Edit/Write operations -- strictly sequential, never parallel]

The sentinel must cover ALL writes in the approval step, not just the stamp itself. For example, `/io-architect` Step H writes CRC cards, `.pyi` files, AND the Approved stamp -- the sentinel is active for the entire sequence.

**Auto-cleanup:** For workflows that end their sentinel window with a recognized stamp write, the hook auto-deletes the sentinel when it detects that write -- no explicit cleanup step is needed. Workflows with auto-cleanup: `/io-clarify` (`**Clarified:** True`), `/io-architect` (`**Approved:** True`), `/validate-plan` (`**Plan Validated:** PASS/FAIL`).

**Explicit cleanup required:** `/doc-sync` writes factual corrections without a trailing stamp write, so the hook cannot detect completion. The agent must run `bash: rm -f .iocane/validating` after all doc-sync writes. See `plans/backlog.md` for a tracked item to revisit this.

The sentinel is automatically cleared on session start. If it is unexpectedly present at session start, it means a previous session crashed mid-stamp -- the session-start hook clears it.

---

## Workflow Quick Reference

| Workflow | Purpose | Writes to |
|----------|---------|-----------|
| `/io-clarify` | Clarify PRD ambiguities and critique against quality rubric | `plans/PRD.md` |
| `/io-adopt` | Adopt an existing codebase into Iocane with extracted current-state + draft PRD | `plans/current-state.md`, `plans/PRD.md` |
| `/io-init` | Bootstrap project structure and stub roadmap from clarified PRD | `plans/roadmap.md`, `plans/backlog.md` |
| `/io-specify` | Propose feature roadmap from clarified PRD | `plans/roadmap.md` |
| `/io-architect` | Design CRC cards, Protocols, Interface Registry | `plans/project-spec.md`, `interfaces/*.pyi` |
| `/io-replan` | Propagate PRD deltas into roadmap/spec and route impacts | `plans/roadmap.md`, `plans/project-spec.md`, `plans/backlog.md` |
| `/io-checkpoint` | Define atomic checkpoints and connectivity tests | `plans/plan.md`, `plans/backlog.md` (remediation: Routed annotation via script) |
| `/validate-plan` | Validate `plan.md` CDD compliance before batch composition | `plans/plan.md` (stamp only) |
| `/io-plan-batch` | Compose dispatch batch, score confidence, get human approval | `plans/tasks/CP-XX.md` (on acceptance) |
| `/io-orchestrate` | Dispatch agents (alias for `dispatch-agents.sh`) | none |
| `/io-execute` | Tier 3 sub-agent workflow that executes one checkpoint task file | `plans/tasks/CP-XX.status`, checkpoint write targets |
| `/validate-spec` | Detect CRC-Protocol drift and re-earn `**Approved:** True` (recovery path) | `plans/project-spec.md` (stamp only) |
| `/doc-sync` | Reconcile docs with codebase after feature completion | `plans/project-spec.md`, `plans/roadmap.md`, `README.md` |
| `/io-review` | Post-implementation review | `plans/review-output.md` (via `/review-capture`) |
| `/io-backlog-triage` | Drain staging + triage open backlog items with approved routing decisions | `plans/backlog.md` (reads `plans/review-output.md` staging) |
| `/io-ct-remediate` | Create missing connectivity test(s) from CT spec for archived checkpoints | CT file path from `plans/plan.md`, `plans/backlog.md` |
| `/gap-analysis` | Identify gaps between implementation and spec | `plans/review-output.md` (via `/review-capture`) |

---

## Additional Workflow Paths

These workflows are part of the full lifecycle and are intentionally outside the single linear happy path:

- Brownfield adoption path: `/io-adopt` -> `/io-clarify` -> `/io-init` -> `/io-specify` -> `/io-architect`.
- Execution internals: `/io-orchestrate` dispatches Tier 3 sub-agents that run `/io-execute` per checkpoint task file.
- Post-review backlog routing: `/io-review` -> `/review-capture` (staging) -> `/io-backlog-triage` (drain to backlog) -> (`/io-architect` | `/validate-plan` | `/io-ct-remediate`) based on tag/risk.
- Archived checkpoint CT recovery: `/io-review` (detect missing CT) -> `/io-ct-remediate` -> backlog item resolved.
- PRD-change replan path (non-linear): `/io-replan` when requirements change after initial planning.

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
- `/io-checkpoint`
- `/validate-spec`
- `/io-review`

---

## Notes

- `.pyi` writes (out-of-band, outside `/io-architect`) reset both `project-spec.md` approval and `plan.md` validation. Always use `/io-architect` to modify contracts. If a `.pyi` change is unavoidable, run `/validate-spec` to recover the `**Approved:** True` stamp before proceeding to `/io-checkpoint`.

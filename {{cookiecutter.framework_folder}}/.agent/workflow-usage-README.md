# Workflow Usage Reference

## Orchestration Chain

```
/io-clarify -> /io-specify -> /io-architect -> /io-checkpoint -> /validate-plan -> /io-plan-batch -> /io-orchestrate (or direct dispatch)
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
bash .claude/scripts/dispatch-agents.sh
```

Both options are equivalent. `/io-orchestrate` is a thin alias for the script invocation provided for discoverability. Direct invocation is preferred if you are comfortable with the CLI.

---

## Configuration

Project-level orchestration config lives in `.claude/iocane.config.yaml`.

```yaml
parallel:
  limit: 3   # Maximum number of checkpoints dispatched concurrently in a single batch
```

### `parallel.limit`

Controls how many checkpoints `/io-plan-batch` may include in a single batch. `/io-plan-batch` and `dispatch-agents.sh` both respect this value.

- Default if config file is missing: `1`
- Increase with caution — parallelization safety is checked per batch, but higher limits increase the blast radius of a bad batch composition.

---

## Validation Stamps

Tier 1 artifacts carry validation stamps that gate downstream workflows. Any substantive write to these artifacts resets the stamp, requiring re-validation before proceeding.

| Artifact | Stamp | Gating Workflow | Gates |
|----------|-------|-----------------|-------|
| `plans/PRD.md` | `**Clarified:** True/False` | `/io-clarify` | `/io-architect` |
| `plans/project-spec.md` | `**Approved:** True/False` | `/io-architect` | `/io-checkpoint` |
| `plans/plan.md` | `**Plan Validated:** PASS/FAIL` | `/validate-plan` | `/io-plan-batch` |

### Exempting a write from stamp reset

Workflows that write stamps (not substantive content) must bracket all writes in the approval step with sentinel file creation and deletion to prevent a reset loop:

    Step N-pre:  bash: mkdir -p .iocane && touch .iocane/validating
    Step N:      [Edit/Write operations — strictly sequential, never parallel]

The sentinel must cover ALL writes in the approval step, not just the stamp itself. For example, `/io-architect` Step H writes CRC cards, `.pyi` files, AND the Approved stamp — the sentinel is active for the entire sequence.

**Auto-cleanup:** For workflows that end their sentinel window with a recognized stamp write, the hook auto-deletes the sentinel when it detects that write — no explicit cleanup step is needed. Workflows with auto-cleanup: `/io-clarify` (`**Clarified:** True`), `/io-architect` (`**Approved:** True`), `/validate-plan` (`**Plan Validated:** PASS/FAIL`).

**Explicit cleanup required:** `/doc-sync` writes factual corrections without a trailing stamp write, so the hook cannot detect completion. The agent must run `bash: rm -f .iocane/validating` after all doc-sync writes. See `BACKLOG.md` for a tracked item to revisit this.

The sentinel is automatically cleared on session start. If it is unexpectedly present at session start, it means a previous session crashed mid-stamp — the session-start hook clears it.

---

## Workflow Quick Reference

| Workflow | Purpose | Writes to |
|----------|---------|-----------|
| `/io-clarify` | Clarify PRD ambiguities and critique against quality rubric | `plans/PRD.md` |
| `/io-specify` | Propose feature roadmap from clarified PRD | `plans/roadmap.md` |
| `/io-architect` | Design CRC cards, Protocols, Interface Registry | `plans/project-spec.md`, `interfaces/*.pyi` |
| `/io-checkpoint` | Define atomic checkpoints and connectivity tests | `plans/plan.md` |
| `/validate-plan` | Validate `plan.md` CDD compliance before batch composition | `plans/plan.md` (stamp only) |
| `/io-plan-batch` | Compose dispatch batch, score confidence, get human approval | `plans/tasks/CP-XX.md` (on acceptance) |
| `/io-orchestrate` | Dispatch agents (alias for `dispatch-agents.sh`) | none |
| `/doc-sync` | Reconcile docs with codebase after feature completion | `plans/project-spec.md`, `plans/roadmap.md`, `README.md` |
| `/review` | Post-implementation review | `plans/backlog.md` |
| `/gap-analysis` | Identify gaps between implementation and spec | `plans/backlog.md` |

---

## Notes

- `.pyi` writes (out-of-band, outside `/io-architect`) reset both `project-spec.md` approval and `plan.md` validation. Always use `/io-architect` to modify contracts.

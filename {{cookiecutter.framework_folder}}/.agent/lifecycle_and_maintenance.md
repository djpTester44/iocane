# Project Lifecycle and Maintenance

This artifact defines the workflows for bootstrapping projects, executing atomic tasks via the Iocane three-tier architecture, and maintaining the codebase through review, backlog management, and documentation sync.

---

## 1. Project Lifecycle (Strategic Management)

Execution follows a strict chronology. Design is locked before any code is written. Sub-agents execute against pre-verified contracts.

### Canonical Sequence

```
[Tier 1 — Human + Plan Mode]
  1. /io-clarify      — resolve PRD ambiguities, stamp Clarified: True
  2. /io-specify      — PLAN MODE — propose roadmap.md, human approves
  3. /io-architect    — PLAN MODE — propose CRC + Protocols, human approves (contract lock)
  4. /io-checkpoint   — PLAN MODE — propose plan.md + connectivity test signatures, human approves

[Tier 2 — Harness Autonomous]
  5. /io-orchestrate  — score confidence rubric, generate task files + run.sh
  6. bash plans/tasks/run.sh  — human executes; sub-agents run in git worktrees

[Tier 1 — Human Review]
  7. /review          — per-checkpoint behavioral + connectivity review
  8. repeat /io-orchestrate → run.sh → /review for each checkpoint batch

[Full-system close]
  9. /gap-analysis    — integration correctness across entire codebase
 10. /doc-sync        — reconcile project-spec.md + roadmap.md with codebase state
```

### Human Attention Contract

The human is required at these moments and only these:

| Moment | Workflow | Action |
|--------|----------|--------|
| PRD ambiguities | `/io-clarify` | Answer questions, approve stamp |
| Roadmap proposal | `/io-specify` | Approve or correct `roadmap.md` |
| Design proposal | `/io-architect` | Approve CRC + Protocols — contract lock |
| Checkpoint boundaries | `/io-checkpoint` | Approve `plan.md` + connectivity signatures |
| Run sub-agents | post `/io-orchestrate` | `bash plans/tasks/run.sh` |
| Checkpoint review | `/review` | Approve or route findings to backlog |
| Escalation | session start | Review `.iocane/escalation.log`, clear flag |
| Replanning | `/io-replan` | Approve PRD delta propagation |

---

## 2. Atomic Execution: The Iocane Loop (Tier 3)

Sub-agents execute one checkpoint at a time in isolated git worktrees. Each sub-agent receives a self-contained task file and terminates after writing a status file. The loop is the per-checkpoint orchestration cycle — not a single continuous session.

### Red-Green-Refactor State Machine

| State | Goal | Gate |
|-------|------|------|
| **RED** | Write a failing test | `pytest` MUST fail — if it passes, the test is invalid |
| **GREEN** | Write minimum implementation to pass the test | `pytest` passes |
| **GATE** | Run the checkpoint's acceptance gate command | Must pass cleanly |
| **REFACTOR** | DI compliance, type correctness, lint | `check_di_compliance.py`, `mypy`, `ruff`, `lint-imports` all pass |

### Status Reporting

On completion, the sub-agent writes one of:

- `plans/tasks/[CP-ID].status` → `PASS`
- `plans/tasks/[CP-ID].status` → `FAIL: [one-line reason]`

The orchestrator reads status files — never logs.

### Escalation Triggers

Sub-agents do not attempt autonomous remediation for these conditions — they write FAIL and terminate:

- Gate failing after 3 attempts
- Connectivity test goes red
- `# noqa: DI` required with no backlog entry
- Layer violation detected

The `PostToolUse` hook captures failures to `.iocane/escalation.log`. Session start surfaces the flag.

---

## 3. Worktree Isolation

Sub-agents run in dedicated git worktrees to prevent filesystem collisions during concurrent execution.

```
.worktrees/
  CP-01/    ← branch: iocane/CP-01
  CP-02/    ← branch: iocane/CP-02
```

Each worktree is a full checkout. Two checkpoints can run concurrently only if their `write_targets` are completely disjoint — this is enforced at `/io-checkpoint` time, not at runtime.

After a checkpoint batch completes and `/review` approves:

- Merge `iocane/[CP-ID]` branches to main
- Remove worktrees

The merge is a human action at the `/review` boundary. The orchestrator does not perform merges.

---

## 4. Maintenance: Dead Code Deletion Protocol

When removing redundant or dead code, prove unused status before deletion.

1. **Prove dead status:**

   ```bash
   grep -r "from src.path.to.module" src/
   grep -r "import src.path.to.module" src/
   ```

   Verify zero integration test usage.

2. **Delete code:** Remove the `.py` file and corresponding `.pyi` if no other component depends on the Protocol.

3. **Verify integrity:**

   ```bash
   uv run lint-imports       # broken internal references
   uv run mypy .             # type signature drift
   uv run pytest             # behavioral regressions
   ```

4. **Cleanup spec:** Remove the entry from the Interface Registry in `plans/project-spec.md`. Run `/doc-sync` to reconcile.

---

## 5. Backlog Lifecycle

`plans/backlog.md` is the formal tracking record for all `/review` and `/gap-analysis` findings. It is append-only and survives across all sessions.

```
/review or /gap-analysis  --> surfaces findings
/review-capture           --> appends [ ] items to plans/backlog.md with taxonomy tags
/io-orchestrate           --> reads backlog.md, warns on [DESIGN]/[REFACTOR] conflicts
/doc-sync                 --> human marks resolved items [x] after verification
```

**Tags:**

| Tag | Meaning | Blocks orchestration? |
|-----|---------|----------------------|
| `[DESIGN]` | CRC or Protocol gap — requires `/io-architect` | Yes (warning) |
| `[REFACTOR]` | DI, layer, or SOLID violation | Yes (warning) |
| `[CLEANUP]` | Minor improvement | No |
| `[TEST]` | Missing test coverage | No |
| `[DEFERRED]` | Acknowledged, intentionally postponed | No |

**Rules:**

- Items are never deleted — the backlog is a permanent audit trail.
- `[x]` items = resolved history. `[ ]` items = active work queue.

---

## 6. Migration: tasks.json → tasks/[CP-ID].md

Projects created before Session 3 used `plans/tasks.json`. The converter script migrates to the new per-checkpoint format:

```bash
uv run python .agent/scripts/tasks_json_to_md.py --dry-run   # preview
uv run python .agent/scripts/tasks_json_to_md.py             # write
```

After conversion, review each generated `plans/tasks/[CP-ID].md` and fill in `[REQUIRED: fill in]` placeholders:

- Protocol contract path
- Connectivity test signatures
- Gate command (if not inferrable from write targets)

---

## 7. Documentation Synchronization (/doc-sync)

Doc-sync reconciles `project-spec.md` and `roadmap.md` with actual codebase state. It runs after gap analysis closes a feature or full project.

### Verification Checklist

1. **README sync:** Update `README.md` against `.agent/templates/README.md` — identity and quick start only, no checkpoint lists.
2. **Interface Registry reconciliation:** Verify every entry points to an existing file. Remove stale entries. Add entries for new implementations.
3. **CRC card reconciliation:** Verify responsibilities match implementation. Flag unanchored behavior as MEDIUM backlog items.
4. **Roadmap status:** Propose feature status updates (`[COMPLETE]` or `[COMPLETE - PENDING REMEDIATION]`) — human approval required.
5. **Link integrity:** Scan for broken markdown links, auto-fix where target exists at a new path.

**Constraint:** `project-spec.md` reflects current codebase state only. No future-state items, no debt tracking artifacts.

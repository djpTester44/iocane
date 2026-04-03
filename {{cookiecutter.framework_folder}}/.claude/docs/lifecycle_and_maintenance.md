# Project Lifecycle and Maintenance

This artifact defines the workflows for bootstrapping projects, executing atomic tasks via the Iocane three-tier architecture, and maintaining the codebase through review, backlog management, and documentation sync.

---

## 1. Project Lifecycle (Strategic Management)

Execution follows a strict chronology. Design is locked before any code is written. Sub-agents execute against pre-verified contracts.

### Canonical Sequence

```
[Tier 1 -- Human + Plan Mode]
  1. /io-clarify      -- resolve PRD ambiguities, stamp Clarified: True
  2. /io-init         -- bootstrap project structure and stub roadmap from clarified PRD
  3. /io-specify      -- PLAN MODE -- propose roadmap.md, human approves
  4. /io-architect    -- PLAN MODE -- propose CRC + Protocols, human approves (contract lock)
  5. /io-checkpoint   -- PLAN MODE -- propose plan.md + connectivity test signatures, human approves
  6. /validate-plan   -- validate plan.md CDD compliance, stamp Plan Validated: PASS

[Tier 2 -- Harness Autonomous]
  7. /io-plan-batch   -- compose batch, score confidence rubric [HARD GATE], generate task files, human approves [HUMAN GATE]
  8. /validate-tasks  -- validate task files against plan.md before dispatch
  9. bash .claude/scripts/dispatch-agents.sh  -- human executes; sub-agents run in git worktrees

[Tier 1 -- Human Review]
  10. /io-review          -- per-checkpoint behavioral + connectivity review
  11. repeat /io-plan-batch -> /validate-tasks -> dispatch-agents.sh -> /io-review for each checkpoint batch

[Full-system close]
  12. /gap-analysis    -- integration correctness across entire codebase
  13. /doc-sync        -- reconcile project-spec.md + roadmap.md with codebase state
```

### Human Attention Contract

The human is required at these moments and only these:

| Moment | Workflow | Action |
|--------|----------|--------|
| PRD ambiguities | `/io-clarify` | Answer questions, approve stamp |
| Project bootstrap | `/io-init` | Confirm project structure and stub roadmap |
| Roadmap proposal | `/io-specify` | Approve or correct `roadmap.md` |
| Design proposal | `/io-architect` | Approve CRC + Protocols -- contract lock |
| Checkpoint boundaries | `/io-checkpoint` | Approve `plan.md` + connectivity signatures |
| Plan validation | `/validate-plan` | Review `Plan Validated` stamp before batch composition |
| Run sub-agents | post `/io-plan-batch` | `bash .claude/scripts/dispatch-agents.sh` |
| Validate task files | post `/io-plan-batch` | Run `/validate-tasks`; approve or route DESIGN findings |
| Run sub-agents | post `/validate-tasks` | `bash .claude/scripts/dispatch-agents.sh` |
| Checkpoint review | `/io-review` | Approve or route findings to backlog |
| Escalation | session start | Review `.iocane/escalation.log`, clear flag |
| Replanning | `/io-replan` | Approve PRD delta propagation |

---

## 2. Atomic Execution: The Iocane Loop (Tier 3)

Sub-agents execute one checkpoint at a time in isolated git worktrees. Each sub-agent receives a self-contained task file and terminates after writing a status file. The loop is the per-checkpoint orchestration cycle -- not a single continuous session.

### Red-Green-Refactor State Machine

| State | Goal | Gate |
|-------|------|------|
| **RED** | Write a failing test | `pytest` MUST fail -- if it passes, the test is invalid |
| **GREEN** | Write minimum implementation to pass the test | `pytest` passes |
| **GATE** | Run the checkpoint's acceptance gate command | Must pass cleanly |
| **REFACTOR** | DI compliance, type correctness, lint | `.claude/scripts/check_di_compliance.py`, `mypy`, `ruff`, `lint-imports` all pass |

### Status Reporting

On completion, the sub-agent writes one of:

- `plans/tasks/[CP-ID].status` -> `PASS`
- `plans/tasks/[CP-ID].status` -> `FAIL: [one-line reason]`

The orchestrator reads status files -- never logs.

### Escalation Triggers

Sub-agents do not attempt autonomous remediation for these conditions -- they write FAIL and terminate:

- Gate failing after 3 attempts
- Connectivity test goes red
- `# noqa: DI` required with no backlog entry
- Layer violation detected

The `PostToolUse` hook (`escalation-gate.sh`) captures failures to `.iocane/escalation.log`. Session start surfaces the flag. Non-numeric exit codes that indicate infrastructure problems (`PARSE_ERROR`, `EXEC_ERROR`) are logged to `.iocane/hook-debug.log`. Commands with no `exit_code` in the payload (normal for successful runs) are silently skipped.

---

## 3. Worktree Isolation

Sub-agents run in dedicated git worktrees to prevent filesystem collisions during concurrent execution.

```
.worktrees/
  CP-01/    <- branch: iocane/CP-01
  CP-02/    <- branch: iocane/CP-02
```

Each worktree is a full checkout. Two checkpoints can run concurrently only if their `write_targets` are completely disjoint -- this is enforced at `/io-checkpoint` time, not at runtime.

After a checkpoint batch completes and `/io-review` approves:

- Merge `iocane/[CP-ID]` branches to main
- Remove worktrees

The merge is a human action at the `/io-review` boundary. The orchestrator does not perform merges.

### Recovering from Failed Checkpoints

When a sub-agent writes a FAIL status (or exhausts its turn budget without writing any status), the worktree is preserved at `.worktrees/[CP-ID]` for inspection.

**Step Progress resumability:** Task files contain a `## Step Progress` section with checkboxes for each execution step (B-G). The sub-agent marks each step complete as it goes. On re-dispatch, the agent reads the checkboxes and resumes from the first unchecked step -- skipping already-completed work.

**To reset and re-dispatch a failed checkpoint:**

```bash
bash .claude/scripts/reset-failed-checkpoints.sh          # reset all FAIL checkpoints
bash .claude/scripts/reset-failed-checkpoints.sh CP-XX    # reset a specific checkpoint
```

This removes the worktree, deletes the `iocane/CP-XX` branch, clears the `.status` and `.exit` files, and resets the attempt counter. Log files are preserved for post-mortem. After reset, run `/io-plan-batch` to generate a fresh task file, then re-dispatch.

**Turn budget exhaustion:** If an agent hits `agents.max_turns` mid-run without writing a status file, no `.status` file is created -- the checkpoint appears pending and will be picked up on the next dispatch. If the existing worktree is still intact and Step Progress shows partial completion, re-dispatch reuses the worktree and resumes from the last unchecked step. If resumption is not viable, run `reset-failed-checkpoints.sh` first. Adjust `agents.max_turns` in `.claude/iocane.config.yaml` if turn exhaustion recurs on complex checkpoints.

---

## 4. Maintenance: Dead Code Deletion Protocol

When removing redundant or dead code, prove unused status before deletion.

1. **Prove dead status:**

   ```bash
   uv run python .claude/skills/symbol-tracer/scripts/symbol_tracer.py --symbol "<SymbolName1>,<SymbolName2>" --root src/ --summary
   ```

   Zero usages + zero imports = dead. For module-level checks, also verify zero integration test usage with `--include-tests`.

2. **Delete code:** Remove the `.py` file and corresponding `.pyi` if no other component depends on the Protocol.

3. **Verify integrity:**

   ```bash
   uv run rtk lint-imports       # broken internal references (requires import-linter; optional)
   uv run mypy .             # type signature drift
   uv run rtk pytest             # behavioral regressions
   ```

4. **Cleanup spec:** Remove the entry from the Interface Registry in `plans/project-spec.md`. Run `/doc-sync` to reconcile.

---

## 5. Backlog Lifecycle

`plans/backlog.md` is the formal tracking record for all `/io-review` and `/gap-analysis` findings. Findings first land in `plans/review-output.md` (staging) via `/review-capture`, then drain to `backlog.md` via `/io-backlog-triage`. The backlog is append-only and survives across all sessions.

### Item Identifiers

Every backlog item has a unique `**BL-NNN**` identifier (zero-padded 3-digit, monotonically
increasing). IDs are assigned automatically by the `backlog-id-assign.sh` PostToolUse hook
on every write to `plans/backlog.md`. Items are never renumbered.

Format in `plans/backlog.md`:

```
**BL-005**
- [ ] [CLEANUP] ComponentName -- one-line description
  - Source: /io-review CP-06
  - Severity: HIGH
  - Files: `src/lib/component.py`
  - Detail: What to fix and why.
```

To reference a specific item: `grep 'BL-005' plans/backlog.md` -- read downward from the ID line.

### Deterministic Operations

| Operation | Mechanism |
|-----------|-----------|
| Assign BL-IDs to new entries | `backlog-id-assign.sh` PostToolUse hook (auto) |
| Route backlog item to remediation CP | `bash .claude/scripts/route-backlog-item.sh BL-NNN CP-NNR` |
| Mark item remediated + flip checkbox | `bash .claude/scripts/archive-approved.sh CP-NNR` (reads `Source BL:` from plan.md) |

### Flow

```
/io-review or /gap-analysis  --> surfaces findings
/review-capture              --> appends structured findings to plans/review-output.md (staging)
/io-backlog-triage           --> drains staging to plans/backlog.md with BL-NNN IDs,
                                 assesses open items, outputs prioritized routing summary
                                 with explicit prompts per item (Tier 1 -- plan mode)
/io-checkpoint (remediation) --> writes Source BL: BL-NNN in CP section, runs
                                 route-backlog-item.sh to add Routed: annotation
dispatch-agents.sh           --> reads backlog.md, warns on [DESIGN]/[REFACTOR] conflicts
/io-review (remediation CP)  --> archive-approved.sh resolves BL item via Source BL: lookup
/doc-sync                    --> human marks resolved items [x] after verification
```

### Using the Triage Output

`/io-backlog-triage` produces a structured summary with an explicit `Prompt:` block for each
routable item, referenced by BL-ID.

- **Route Immediately items:** copy the `Prompt:` verbatim and run it. The downstream workflow
  receives the full item description from the summary as context.
- **Requires Human Scoping items:** amend `plans/plan.md` manually first -- add the target file
  to a checkpoint's write targets or add a new checkpoint -- then run `/validate-plan`.
- **Likely Resolved items:** confirm by reading the referenced file at the described location.
  If resolved, change `[ ]` to `[x]` in `plans/backlog.md` with a brief resolution note.
- **Deferred items:** triage workflow tags them `[DEFERRED]` in `plans/backlog.md` with a
  reason note on human approval. Deferred items do not block orchestration.

**Tags:**

| Tag | Meaning | Blocks orchestration? | Routing workflow |
|-----|---------|----------------------|-----------------|
| `[DESIGN]` | CRC or Protocol gap -- requires `/io-architect` | Yes (warning) | `/io-architect` |
| `[REFACTOR]` | DI, layer, or SOLID violation | Yes (warning) | `/io-architect` (CRC only) then `/validate-plan` |
| `[CLEANUP]` | Minor improvement | No | `/validate-plan` -> `/io-plan-batch` |
| `[TEST]` | Missing test coverage | No | `/io-ct-remediate` (CT gaps) or checkpoint amendment (unit test gaps) |
| `[DEFERRED]` | Acknowledged, intentionally postponed | No | -- |

**Rules:**

- Items are never deleted -- the backlog is a permanent audit trail.
- `[x]` items = resolved history. `[ ]` items = active work queue.

---

## 6. Documentation Synchronization (/doc-sync)

Doc-sync reconciles `project-spec.md` and `roadmap.md` with actual codebase state. It runs after gap analysis closes a feature or full project.

### Verification Checklist

1. **README sync:** Update `README.md` against `.claude/templates/README.md` -- identity and quick start only, no checkpoint lists.
2. **Interface Registry reconciliation:** Verify every entry points to an existing file. Remove stale entries. Add entries for new implementations.
3. **CRC card reconciliation:** Verify responsibilities match implementation. Flag unanchored behavior as MEDIUM backlog items.
4. **Roadmap status:** Propose feature status updates (`[COMPLETE]` or `[COMPLETE - PENDING REMEDIATION]`) -- human approval required.
5. **Link integrity:** Scan for broken markdown links, auto-fix where target exists at a new path.

**Constraint:** `project-spec.md` reflects current codebase state only. No future-state items, no debt tracking artifacts.

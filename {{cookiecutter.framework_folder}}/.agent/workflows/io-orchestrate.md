---
description: Autonomous orchestration. Reads plan.md, scores confidence rubric, generates per-checkpoint task files, writes run.sh, dispatches sub-agents via git worktrees. Tier 2 — no plan mode.
---

> **[NO PLAN MODE]**
> This workflow is fully autonomous. No proposals, no human approval steps.
> Human has visibility but is not required to intervene unless escalation is triggered.

> **[CRITICAL] CONTEXT LOADING**
>
> 1. `view_file plans/plan.md`
> 2. `view_file plans/project-spec.md`
> 3. `view_file plans/backlog.md` (if exists)
> 4. For each unblocked checkpoint: `view_file interfaces/[protocol].pyi`

# WORKFLOW: IO-ORCHESTRATE

**Objective:** For the current execution cycle, identify all unblocked checkpoints, generate their task files, score the confidence rubric, and dispatch sub-agents via isolated git worktrees.

**Position in chain:**

```
/io-checkpoint -> [/io-orchestrate] -> (sub-agents run) -> /review -> /io-orchestrate (next cycle)
```

---

## 1. STATE INITIALIZATION

Output the following before proceeding:

- **Active feature:** [F-XX from roadmap.md currently in progress]
- **Total checkpoints in feature:** [N]
- **Checkpoints complete:** [N] (gate command passing + status file = PASS)
- **Checkpoints unblocked:** [List CP-IDs where all depends_on are complete]
- **Checkpoints blocked:** [List CP-IDs still waiting on dependencies]
- **Backlog alerts:** [Any open items in backlog.md that overlap with unblocked checkpoints]

---

## 2. PROCEDURE

### Step A: RESOLVE CHECKPOINT STATUS

For each checkpoint in `plans/plan.md`:

- **Check:** Does `plans/tasks/[CP-ID].status` exist?
  - If yes and content is `PASS` → checkpoint is complete
  - If yes and content is `FAIL` → checkpoint failed, check escalation log
  - If not present → checkpoint is pending
- **Derive unblocked set:** A checkpoint is unblocked when all checkpoints in its `depends_on` list are `PASS`.

---

### Step B: BACKLOG GATE

- **Action:** Read `plans/backlog.md` if it exists.
- **Check:** Are there any open `[ ]` items tagged `[DESIGN]` or `[REFACTOR]` that affect the components in the unblocked checkpoint set?
- **Rule:** If yes, output a warning listing the conflicting items. Do not halt — the human is notified at session start via `session-start.sh`. Proceed unless the backlog item explicitly blocks a component the checkpoint writes to.

---

### Step C: GENERATE TASK FILES

For each unblocked checkpoint, generate `plans/tasks/[CP-ID].md`:

```markdown
# Task: [CP-ID] — [Checkpoint Name]

## Objective
[Description from plan.md — one sentence]

## Contract
Protocol: `interfaces/[protocol].pyi`
Read the protocol before writing any code. Build against it exactly.

## Write Targets
[List from plan.md — these are the ONLY files you may write to]
- `src/[path]/[module].py`
- `tests/[path]/test_[module].py`

## Context Files (read-only)
[List from plan.md]
- `interfaces/[protocol].pyi`
- `plans/project-spec.md` — read CRC card for [ComponentName] only

## Connectivity Tests to Keep Green
[List any connectivity tests from plan.md that involve this checkpoint's output]
- CT-[NNN]: `[gate command]`

## Execution Protocol
Follow Red-Green-Refactor strictly:

1. RED: Write a failing test in `tests/[path]/test_[module].py`
   - Test must fail before you write implementation
   - If test passes immediately, it is invalid — rewrite it
2. GREEN: Write minimum implementation in `src/[path]/[module].py` to pass the test
   - Implement against the Protocol signature exactly
   - No methods, no behavior beyond what the test requires
3. GATE: Run `[gate command from plan.md]`
   - Must pass cleanly before proceeding
4. REFACTOR: Clean up for SOLID/DI compliance
   - Run `uv run python .agent/scripts/check_di_compliance.py`
   - Run `uv run mypy src/[path]/[module].py`
   - Run `uv run ruff check --fix src/[path]/[module].py`
   - All checks must pass

## Completion
When all steps pass, write a single line to `../../plans/tasks/[CP-ID].status`:
```

PASS

```

If any step fails after 3 attempts, write:
```

FAIL: [one line describing what failed]

```
Then terminate.

## Constraints
- You have NO access to plan.md, roadmap.md, project-spec.md (beyond the CRC card noted above), or other task files
- You may NOT write to any file not listed in Write Targets
- You may NOT install dependencies — if a dependency is missing, write FAIL and terminate
- You may NOT use `# noqa: DI` without a matching backlog entry — if you need it, write FAIL and terminate
```

---

### Step D: SCORE CONFIDENCE RUBRIC

Before dispatching, score the full task set against the rubric. Required threshold: **85%**.

Score each criterion across ALL task files generated in Step C:

| Criterion | Weight | Check |
|-----------|--------|-------|
| Every task maps to a CRC responsibility | 20% | Each task's Objective traces to a named responsibility in the CRC card |
| Every write target exists in Interface Registry | 20% | Cross-reference `project-spec.md` Interface Registry |
| No task has empty context_files | 15% | Every task lists at least one context file |
| Layer boundaries respected | 15% | No write target imports from a higher layer than its own |
| Gate command specified and runnable | 15% | Gate command is a concrete pytest invocation, not a placeholder |
| Task coverage against checkpoint spec complete | 15% | Every method in the Protocol has at least one test task covering it |

**Scoring:**

For each criterion, score per task as PASS (full weight) or FAIL (zero). Average across all tasks.

```
Criterion score = (tasks passing criterion / total tasks) * weight
Total score = sum of all criterion scores
```

**If total score < 85%:**
- Identify failing criteria
- Revise affected task files to address gaps
- Re-score
- Repeat until ≥ 85% or until 3 iterations exhausted
- If still < 85% after 3 iterations: output "ORCHESTRATION HALTED: Confidence threshold not met after 3 iterations. Review task files in plans/tasks/. Manual intervention required." and terminate.

**If total score ≥ 85%:**
- Output the score breakdown
- Proceed to Step E

---

### Step E: GENERATE RUN.SH

Write `plans/tasks/run.sh` with the following structure:

```bash
#!/usr/bin/env bash
# Generated by /io-orchestrate
# Checkpoint batch: [list of CP-IDs]
# Generated: [timestamp]

set -euo pipefail

AGENT_TIMEOUT=${IOCANE_TIMEOUT:-10m}
MAX_TURNS=${IOCANE_MAX_TURNS:-20}
REPO_ROOT=$(git rev-parse --show-toplevel)
TASKS_DIR="$REPO_ROOT/tasks"

# --- Worktree setup ---
echo "Setting up worktrees..."

[For each checkpoint in batch:]
git worktree add "$REPO_ROOT/.worktrees/[CP-ID]" -b "iocane/[CP-ID]" 2>/dev/null || {
    echo "Branch iocane/[CP-ID] already exists — reusing"
    git worktree add "$REPO_ROOT/.worktrees/[CP-ID]" "iocane/[CP-ID]"
}

# --- Dispatch ---
echo "Dispatching sub-agents..."

[For each checkpoint in batch — all backgrounded:]
(
    cd "$REPO_ROOT/.worktrees/[CP-ID]" && \
    timeout "$AGENT_TIMEOUT" claude -p \
        --max-turns "$MAX_TURNS" \
        --allowedTools "Bash,Read,Write,Edit" \
        "@$TASKS_DIR/[CP-ID].md" \
        > "$TASKS_DIR/[CP-ID].log" 2>&1
    echo $? > "$TASKS_DIR/[CP-ID].exit"
) &
PIDS+=($!)

# --- Wait and collect ---
echo "Waiting for agents to complete..."
FAILED=0

for i in "${!PIDS[@]}"; do
    wait "${PIDS[$i]}"
    # exit code already written to .exit file by subshell
done

[For each checkpoint in batch:]
EXIT_CODE=$(cat "$TASKS_DIR/[CP-ID].exit" 2>/dev/null || echo "1")
if [ "$EXIT_CODE" -eq 0 ]; then
    STATUS=$(cat "$TASKS_DIR/[CP-ID].status" 2>/dev/null || echo "MISSING")
    echo "[CP-ID]: $STATUS"
    if [ "$STATUS" != "PASS" ]; then
        FAILED=$((FAILED + 1))
    fi
else
    echo "[CP-ID]: AGENT ERROR (exit $EXIT_CODE) — see plans/tasks/[CP-ID].log"
    FAILED=$((FAILED + 1))
fi

# --- Summary ---
echo ""
echo "Batch complete."
echo "Passed: $((TOTAL - FAILED)) / TOTAL"
echo ""

if [ "$FAILED" -gt 0 ]; then
    echo "Failures detected. Check plans/tasks/*.log and .iocane/escalation.log"
    exit 1
fi

# --- Cleanup worktrees ---
echo "Cleaning up worktrees..."
[For each checkpoint in batch:]
git worktree remove "$REPO_ROOT/.worktrees/[CP-ID]" --force 2>/dev/null || true

echo "Done. Run /review to verify checkpoint outputs."
exit 0
```

**After writing `plans/tasks/run.sh`:**

```bash
chmod +x plans/tasks/run.sh
```

---

### Step F: OUTPUT AND HANDOFF

```
ORCHESTRATION READY.

Confidence score: [NN]%
Checkpoints in batch: [N] ([CP-ID], [CP-ID], ...)
Parallelizable: [yes/no — all dispatched concurrently]
Task files written: plans/tasks/[CP-ID].md (x N)
Dispatch script: plans/tasks/run.sh

To execute: bash plans/tasks/run.sh

Sub-agents will run in isolated git worktrees on branches iocane/[CP-ID].
Results will appear in plans/tasks/[CP-ID].status and plans/tasks/[CP-ID].log.

After completion, run /review to verify outputs.
```

---

## 3. ESCALATION HANDLING

The `PostToolUse` hook on `Bash` monitors sub-agent exit codes during `run.sh` execution. If escalation triggers fire (untracked `# noqa: DI`, layer violation, cascading failure), the hook:

1. Appends a structured record to `.iocane/escalation.log`
2. Writes `.iocane/escalation.flag`

The orchestrator reads only the flag, not the log. If `.iocane/escalation.flag` exists at the start of this workflow:

- Output: "ESCALATION FLAG DETECTED. Review `.iocane/escalation.log` before proceeding. Clear the flag file after review."
- HALT until flag is cleared.

---

## 4. MERGE STRATEGY

After `/review` approves a checkpoint batch:

Each `iocane/[CP-ID]` branch is merged to main. The orchestrator does not perform merges — this is a human action at the `/review` boundary. Worktrees for approved checkpoints are removed after merge.

---

## 5. CONSTRAINTS

- No plan mode — this workflow writes files and acts autonomously
- Does not read individual task `.log` files — only `.status` and `.exit` files
- Does not modify `plan.md`, `roadmap.md`, `project-spec.md`, or any `.pyi` file
- Does not execute `run.sh` — writes it and instructs the human (or CI) to run it
- If a checkpoint's `depends_on` list contains any non-PASS status, it is not included in the batch under any circumstance

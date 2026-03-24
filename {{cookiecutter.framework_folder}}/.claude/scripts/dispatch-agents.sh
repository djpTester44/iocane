#!/usr/bin/env bash
# .claude/scripts/dispatch-agents.sh
#
# Owns the full batch lifecycle for sub-agent execution:
#   1. Scans plans/tasks/ for pending CP-XX.md files (no matching .status)
#   2. Enforces parallel.limit from .claude/iocane.config.yaml as a safety cap
#   3. Sets up an isolated git worktree per checkpoint via setup-worktree.sh
#   4. Dispatches each sub-agent headlessly via claude -p
#   5. Waits for all agents to complete
#   6. Cleans up worktrees for PASS checkpoints only
#   7. Reports batch summary
#
# Usage:
#   uv run bash .claude/scripts/dispatch-agents.sh
#
# Environment (all optional, override config when config is absent):
#   IOCANE_PARALLEL_LIMIT  -- max concurrent agents (fallback when config unreadable)
#   IOCANE_MODEL           -- claude model string (fallback when config unreadable)
#   IOCANE_TIMEOUT         -- per-agent timeout (default: 10m)
#   IOCANE_MAX_TURNS       -- max agent turns (default: 20)
#   REPO_ROOT              -- auto-detected via git if not set

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- Configuration ---
REPO_ROOT="${REPO_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null)}"
CONFIG_FILE="$REPO_ROOT/.claude/iocane.config.yaml"

# _cfg_read: extract section.key value from YAML config (awk-based, no external deps)
# Usage: _cfg_read "parallel.limit"
# Handles multi-key sections and strips inline comments.
_cfg_read() {
    local key="$1"
    local section="${key%%.*}"
    local subkey="${key#*.}"
    awk "/^${section}:/{found=1; next} found && /^[^ ]/{exit} found && /^  ${subkey}:/{print; exit}" "$CONFIG_FILE" 2>/dev/null \
        | sed 's/^[^:]*:[[:space:]]*//' \
        | sed 's/[[:space:]]*#.*//' \
        | tr -d '\r' \
        | head -1
}

# Read parallel.limit: config -> IOCANE_PARALLEL_LIMIT env -> default 1
_cfg_parallel=$(_cfg_read "parallel.limit")
if [ -n "$_cfg_parallel" ] && [ "$_cfg_parallel" != "null" ]; then
    PARALLEL_LIMIT="$_cfg_parallel"
    PARALLEL_SOURCE="config"
elif [ -n "${IOCANE_PARALLEL_LIMIT:-}" ]; then
    PARALLEL_LIMIT="$IOCANE_PARALLEL_LIMIT"
    PARALLEL_SOURCE="env"
else
    PARALLEL_LIMIT="1"
    PARALLEL_SOURCE="default"
fi

# Read agents.max_turns: config -> IOCANE_MAX_TURNS env -> default 50
_cfg_max_turns=$(_cfg_read "agents.max_turns")
if [ -n "$_cfg_max_turns" ] && [ "$_cfg_max_turns" != "null" ]; then
    MAX_TURNS="${IOCANE_MAX_TURNS:-$_cfg_max_turns}"
else
    MAX_TURNS="${IOCANE_MAX_TURNS:-50}"
fi

# Read agents.timeout: config -> IOCANE_TIMEOUT env -> default 10m
_cfg_timeout=$(_cfg_read "agents.timeout")
if [ -n "$_cfg_timeout" ] && [ "$_cfg_timeout" != "null" ]; then
    AGENT_TIMEOUT="${IOCANE_TIMEOUT:-$_cfg_timeout}"
else
    AGENT_TIMEOUT="${IOCANE_TIMEOUT:-10m}"
fi

# Read models.tier3: config -> IOCANE_MODEL env -> hard default
_cfg_model=$(_cfg_read "models.tier3")
if [ -n "$_cfg_model" ] && [ "$_cfg_model" != "null" ]; then
    MODEL="${IOCANE_MODEL:-$_cfg_model}"
else
    MODEL="${IOCANE_MODEL:-claude-haiku-4-5-20251001}"
fi

TASKS_DIR="$REPO_ROOT/plans/tasks"

if [ -z "$REPO_ROOT" ]; then
    echo "ERROR: Could not determine repo root. Are you inside a git repository?" >&2
    exit 1
fi

# --- Clean-tree gate ---
# Worktrees branch from HEAD; uncommitted changes won't propagate to sub-agents.
if ! git -C "$REPO_ROOT" diff --quiet HEAD 2>/dev/null || \
   ! git -C "$REPO_ROOT" diff --cached --quiet HEAD 2>/dev/null || \
   [ -n "$(git -C "$REPO_ROOT" ls-files --others --exclude-standard 2>/dev/null)" ]; then
    echo "ERROR: Working tree is not clean. Commit or stash changes before dispatching." >&2
    echo "       Worktrees branch from HEAD — uncommitted changes will not reach sub-agents." >&2
    git -C "$REPO_ROOT" status --short >&2
    exit 1
fi

# Capture the branch that was checked out when the user ran this script.
# Completed checkpoint branches are merged back here on PASS.
PARENT_BRANCH=$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD)

# --- Collect pending task files ---
# A task file is pending if CP-XX.md exists but CP-XX.status does not.
PENDING=()

for task_file in "$TASKS_DIR"/CP-*.md; do
    [ -f "$task_file" ] || continue
    CP_ID=$(basename "$task_file" .md)
    STATUS_FILE="$TASKS_DIR/$CP_ID.status"
    if [ ! -f "$STATUS_FILE" ]; then
        PENDING+=("$CP_ID")
    fi
done

if [ ${#PENDING[@]} -eq 0 ]; then
    echo "No pending task files found in $TASKS_DIR."
    echo "Run the task generation workflow to create task files before dispatching."
    exit 0
fi

echo "Pending checkpoints: ${PENDING[*]}"
echo "Parallel limit: $PARALLEL_LIMIT (source: $PARALLEL_SOURCE)"

# --- Enforce parallel limit ---
BATCH=("${PENDING[@]:0:$PARALLEL_LIMIT}")

if [ ${#PENDING[@]} -gt "$PARALLEL_LIMIT" ]; then
    echo "NOTE: ${#PENDING[@]} pending checkpoints found, dispatching first $PARALLEL_LIMIT per parallel.limit in .claude/iocane.config.yaml."
    echo "Remaining: ${PENDING[@]:$PARALLEL_LIMIT}"
fi

echo ""
echo "Dispatching ${#BATCH[@]} sub-agents..."

# --- Dispatch batch concurrently ---
declare -A PIDS

for CP_ID in "${BATCH[@]}"; do
    (
        # Set up worktree
        bash "$SCRIPT_DIR/setup-worktree.sh" --cp "$CP_ID"

        WORKTREE_PATH="$REPO_ROOT/.worktrees/$CP_ID"
        LOG_FILE="$TASKS_DIR/$CP_ID.log"
        EXIT_FILE="$TASKS_DIR/$CP_ID.exit"

        # Deterministic io-execute invocation string -- same for every checkpoint.
        INVOKE_PROMPT="Read and execute the workflow defined in .claude/commands/io-execute.md. Your task file is plans/tasks/${CP_ID}.md. Follow every step exactly. Terminate after writing the status file."

        ATTEMPT_FILE="$REPO_ROOT/.iocane/$CP_ID.attempts"
        ATTEMPT=$(cat "$ATTEMPT_FILE" 2>/dev/null || echo "0")
        ATTEMPT=$((ATTEMPT + 1))
        echo "$ATTEMPT" > "$ATTEMPT_FILE"

        export IOCANE_SUBAGENT=1
        export IOCANE_CP_ID="$CP_ID"
        export IOCANE_ATTEMPT="$ATTEMPT"
        export IOCANE_REPO_ROOT="$REPO_ROOT"
        export IOCANE_LOG_FILE="$LOG_FILE"
        export IOCANE_MODEL_NAME="$MODEL"
        # Unset VIRTUAL_ENV so uv uses the worktree venv, not the parent repo venv.
        unset VIRTUAL_ENV

        cd "$WORKTREE_PATH"

        echo "$INVOKE_PROMPT" | timeout "$AGENT_TIMEOUT" claude -p \
            --model "$MODEL" \
            --max-turns "$MAX_TURNS" \
            --allowedTools "Bash,Read,Write,Edit" \
            --output-format text \
            > "$LOG_FILE" 2>&1
        AGENT_EXIT=$?

        echo "$AGENT_EXIT" > "$EXIT_FILE"
        exit "$AGENT_EXIT"
    ) &
    PIDS[$CP_ID]=$!
done

# --- Wait for all agents ---
echo "Waiting for agents to complete..."
wait

# --- Collect results, log, and clean up ---
echo ""
TOTAL=${#BATCH[@]}
FAILED=0

for CP_ID in "${BATCH[@]}"; do
    EXIT_CODE=$(cat "$TASKS_DIR/$CP_ID.exit" 2>/dev/null || echo "1")
    STATUS=$(cat "$TASKS_DIR/$CP_ID.status" 2>/dev/null || echo "MISSING")

    if [ "$EXIT_CODE" -eq 0 ] && [ "$STATUS" = "PASS" ]; then
        echo "$CP_ID: PASS"

        # Check whether the branch has any new commits to merge.
        AHEAD=$(git -C "$REPO_ROOT" rev-list --count "$PARENT_BRANCH..iocane/$CP_ID" 2>/dev/null || echo "0")
        if [ "$AHEAD" -eq 0 ]; then
            echo "$CP_ID: WARNING — branch iocane/$CP_ID has no new commits. Sub-agent may not have committed its work. Skipping merge." >&2
        else
            git -C "$REPO_ROOT" merge "iocane/$CP_ID" --no-ff -m "Merge checkpoint $CP_ID into $PARENT_BRANCH"
            echo "$CP_ID: Merged into $PARENT_BRANCH."
        fi

        git -C "$REPO_ROOT" worktree remove "$REPO_ROOT/.worktrees/$CP_ID" --force 2>/dev/null || true
        git -C "$REPO_ROOT" worktree prune
        git -C "$REPO_ROOT" branch -d "iocane/$CP_ID" 2>/dev/null || true
        echo "$CP_ID: Worktree and branch removed."

    else
        echo "$CP_ID: $STATUS (exit $EXIT_CODE) -- see $TASKS_DIR/$CP_ID.log"
        FAILED=$((FAILED + 1))

        # Leave worktree intact for inspection
        echo "$CP_ID: Worktree preserved at $REPO_ROOT/.worktrees/$CP_ID for inspection."
    fi
done

# --- Summary ---
echo ""
echo "Batch complete. Passed: $((TOTAL - FAILED))/$TOTAL"
echo ""

if [ "$FAILED" -gt 0 ]; then
    echo "Failures detected. Check plans/tasks/*.log and .iocane/escalation.log"
    exit 1
fi

echo "All checkpoints passed. Run /io-review to verify outputs."
exit 0

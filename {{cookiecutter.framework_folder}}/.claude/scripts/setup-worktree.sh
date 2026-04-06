#!/usr/bin/env bash
# .claude/scripts/setup-worktree.sh
#
# Sets up an isolated git worktree for a sub-agent checkpoint.
# Called internally by dispatch-agent.sh -- not invoked directly.
#
# Usage:
#   bash .claude/scripts/setup-worktree.sh --cp CP-01
#
# Environment:
#   REPO_ROOT  -- auto-detected via git if not set
#
# Exit codes:
#   0  -- worktree ready
#   1  -- setup failed (branch conflict, dirty tree, missing tasks file, etc.)

set -euo pipefail

# --- Argument parsing ---
CP_ID=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --cp)
            CP_ID="$2"
            shift 2
            ;;
        *)
            echo "ERROR: Unknown argument: $1" >&2
            echo "Usage: $0 --cp CP-ID" >&2
            exit 1
            ;;
    esac
done

if [ -z "$CP_ID" ]; then
    echo "ERROR: --cp CP-ID is required." >&2
    exit 1
fi

# --- Resolve repo root ---
REPO_ROOT="${REPO_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null)}"

if [ -z "$REPO_ROOT" ]; then
    echo "ERROR: Could not determine repo root. Are you inside a git repository?" >&2
    exit 1
fi

WORKTREE_PATH="$REPO_ROOT/.worktrees/$CP_ID"
BRANCH_NAME="iocane/$CP_ID"
TASK_FILE="$REPO_ROOT/plans/tasks/$CP_ID.yaml"

# --- Preflight: task file must exist ---
if [ ! -f "$TASK_FILE" ]; then
    echo "ERROR: Task file not found: $TASK_FILE" >&2
    echo "Run /io-plan-batch to generate task files before dispatching." >&2
    exit 1
fi

# --- Set up worktree ---
if [ -d "$WORKTREE_PATH" ]; then
    echo "Worktree already exists at $WORKTREE_PATH -- reusing."
    exit 0
fi

# --- Commit task file in main before creating a fresh worktree ---
# Task files are untracked in main after /io-plan-batch writes them.
# If left untracked, git refuses to merge the sub-agent branch back because
# the committed (checkbox-updated) task file would overwrite the untracked one.
# Skipped when reusing an existing worktree — the merge reconciles the file.
# Only runs in the main working tree (.git is a directory); no-ops in worktrees.
if [ -d "$REPO_ROOT/.git" ]; then
    REL_TASK="plans/tasks/$CP_ID.yaml"
    FILE_STATUS=$(git -C "$REPO_ROOT" status --porcelain -- "$REL_TASK" 2>/dev/null | cut -c1-2)
    if [ -n "$FILE_STATUS" ]; then
        git -C "$REPO_ROOT" add -- "$REL_TASK"
        git -C "$REPO_ROOT" commit -m "chore: track $CP_ID task file before dispatch" -- "$REL_TASK"
        echo "Committed $REL_TASK to main."
    fi
fi

if git -C "$REPO_ROOT" show-ref --verify --quiet "refs/heads/$BRANCH_NAME"; then
    echo "Branch $BRANCH_NAME already exists -- attaching worktree."
    git -C "$REPO_ROOT" worktree add "$WORKTREE_PATH" "$BRANCH_NAME"
else
    echo "Creating branch $BRANCH_NAME and worktree at $WORKTREE_PATH."
    git -C "$REPO_ROOT" worktree add "$WORKTREE_PATH" -b "$BRANCH_NAME"
fi

# --- Copy task file into worktree ---
# Task files are untracked in the main tree and not visible to the fresh branch.
# The sub-agent needs this file to know what to implement.
mkdir -p "$WORKTREE_PATH/plans/tasks"
cp "$TASK_FILE" "$WORKTREE_PATH/plans/tasks/$CP_ID.yaml"

# --- Remove task files and output artifacts that do not belong to this checkpoint ---
# The worktree inherits tracked plans/tasks/CP-XX.yaml files from the parent
# branch. Output artifacts (*.log, *.result.json, *.exit, *.status) can also
# end up in the worktree via a prior run's git add -A commit. Remove all
# foreign CP files to prevent sub-agents from reading or acting on the wrong task.
for f in "$WORKTREE_PATH/plans/tasks"/CP-*; do
    [ -f "$f" ] || continue
    fname=$(basename "$f")
    cp_prefix="${fname%%.*}"
    if [ "$cp_prefix" != "$CP_ID" ]; then
        git -C "$WORKTREE_PATH" update-index --skip-worktree -- "plans/tasks/$fname" 2>/dev/null || true
        rm -f "$f"
    fi
done

# --- Copy untracked project files required for uv ---
# pyproject.toml and uv.lock may be untracked in the parent repo
# (e.g. created by a sub-agent outside its worktree). Copy them so
# the worktree venv and uv run rtk commands work correctly.
for f in pyproject.toml uv.lock; do
    src="$REPO_ROOT/$f"
    dst="$WORKTREE_PATH/$f"
    if [ -f "$src" ] && [ ! -f "$dst" ]; then
        cp "$src" "$dst"
        echo "Copied $f into worktree."
    fi
done

# --- Sync dependencies into the worktree venv ---
# uv creates .venv inside the worktree (not shared with main checkout).
# Syncing here ensures the venv is ready before the sub-agent starts,
# so uv run rtk commands in task files don't incur sync latency mid-execution.
echo "Syncing dependencies in $WORKTREE_PATH..."
uv sync --project "$WORKTREE_PATH" --quiet
echo "Worktree ready: $WORKTREE_PATH (branch: $BRANCH_NAME)"
exit 0

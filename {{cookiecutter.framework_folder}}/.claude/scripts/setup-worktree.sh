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
TASK_FILE="$REPO_ROOT/plans/tasks/$CP_ID.md"

# --- Preflight: task file must exist ---
if [ ! -f "$TASK_FILE" ]; then
    echo "ERROR: Task file not found: $TASK_FILE" >&2
    echo "Run /io-orchestrate to generate task files before dispatching." >&2
    exit 1
fi

# --- Set up worktree ---
if [ -d "$WORKTREE_PATH" ]; then
    echo "Worktree already exists at $WORKTREE_PATH -- reusing."
    exit 0
fi

if git -C "$REPO_ROOT" show-ref --verify --quiet "refs/heads/$BRANCH_NAME"; then
    echo "Branch $BRANCH_NAME already exists -- attaching worktree."
    git -C "$REPO_ROOT" worktree add "$WORKTREE_PATH" "$BRANCH_NAME"
else
    echo "Creating branch $BRANCH_NAME and worktree at $WORKTREE_PATH."
    git -C "$REPO_ROOT" worktree add "$WORKTREE_PATH" -b "$BRANCH_NAME"
fi

echo "Worktree ready: $WORKTREE_PATH (branch: $BRANCH_NAME)"
exit 0

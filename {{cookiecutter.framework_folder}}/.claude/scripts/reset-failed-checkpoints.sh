#!/usr/bin/env bash
# .claude/scripts/reset-failed-checkpoints.sh
#
# Cleans up failed checkpoint worktrees and resets their dispatch state so they
# can be re-queued by /io-plan-batch and dispatched again.
#
# Preserved: plans/tasks/CP-XX.log (kept for post-mortem)
# Removed:   worktree, branch, .status, .exit, .iocane/CP-XX.attempts
#
# Usage:
#   bash .claude/scripts/reset-failed-checkpoints.sh           # reset all FAIL checkpoints
#   bash .claude/scripts/reset-failed-checkpoints.sh CP-04     # reset specific checkpoint(s)
#   bash .claude/scripts/reset-failed-checkpoints.sh CP-04 CP-07
#
# Exits non-zero if any checkpoint could not be fully reset.

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null)}"
TASKS_DIR="$REPO_ROOT/plans/tasks"
IOCANE_DIR="$REPO_ROOT/.iocane"

if [ -z "$REPO_ROOT" ]; then
    echo "ERROR: Could not determine repo root. Are you inside a git repository?" >&2
    exit 1
fi

# --- Collect targets ---

TARGETS=()

if [ $# -gt 0 ]; then
    for CP_ID in "$@"; do
        TARGETS+=("$CP_ID")
    done
else
    # Auto-detect all FAIL status checkpoints
    for status_file in "$TASKS_DIR"/CP-*.status; do
        [ -f "$status_file" ] || continue
        if grep -q "^FAIL" "$status_file" 2>/dev/null; then
            TARGETS+=("$(basename "$status_file" .status)")
        fi
    done
fi

if [ ${#TARGETS[@]} -eq 0 ]; then
    echo "No failed checkpoints found. Nothing to reset."
    exit 0
fi

echo "Checkpoints to reset: ${TARGETS[*]}"
echo ""

RESET=0
ERRORS=0

for CP_ID in "${TARGETS[@]}"; do
    STATUS_FILE="$TASKS_DIR/$CP_ID.status"
    echo "--- $CP_ID ---"

    # Safety check: refuse to reset a PASS checkpoint unless explicitly named
    if [ -f "$STATUS_FILE" ] && grep -q "^PASS" "$STATUS_FILE" 2>/dev/null; then
        if [ $# -gt 0 ]; then
            echo "  WARNING: $CP_ID has PASS status. Skipping — will not reset a passing checkpoint."
        else
            echo "  $CP_ID is PASS — skipping."
        fi
        echo ""
        continue
    fi

    CHECKPOINT_ERRORS=0

    # 1. Remove worktree
    WORKTREE="$REPO_ROOT/.worktrees/$CP_ID"
    if [ -d "$WORKTREE" ]; then
        if git -C "$REPO_ROOT" worktree remove "$WORKTREE" --force 2>/dev/null; then
            git -C "$REPO_ROOT" worktree prune 2>/dev/null || true
            echo "  [ok] worktree removed"
        else
            echo "  [warn] could not remove worktree at $WORKTREE — remove manually if needed" >&2
            CHECKPOINT_ERRORS=$((CHECKPOINT_ERRORS + 1))
        fi
    else
        echo "  [skip] no worktree found at $WORKTREE"
    fi

    # 2. Delete branch
    BRANCH="iocane/$CP_ID"
    if git -C "$REPO_ROOT" rev-parse --verify "$BRANCH" &>/dev/null; then
        if git -C "$REPO_ROOT" branch -D "$BRANCH" 2>/dev/null; then
            echo "  [ok] branch deleted: $BRANCH"
        else
            echo "  [warn] could not delete branch $BRANCH" >&2
            CHECKPOINT_ERRORS=$((CHECKPOINT_ERRORS + 1))
        fi
    else
        echo "  [skip] no branch found: $BRANCH"
    fi

    # 3. Remove .status file
    if [ -f "$STATUS_FILE" ]; then
        rm "$STATUS_FILE"
        echo "  [ok] status file removed"
    else
        echo "  [skip] no status file found"
    fi

    # 4. Remove .exit file
    EXIT_FILE="$TASKS_DIR/$CP_ID.exit"
    if [ -f "$EXIT_FILE" ]; then
        rm "$EXIT_FILE"
        echo "  [ok] exit file removed"
    fi

    # 5. Reset attempt counter
    ATTEMPT_FILE="$IOCANE_DIR/$CP_ID.attempts"
    if [ -f "$ATTEMPT_FILE" ]; then
        rm "$ATTEMPT_FILE"
        echo "  [ok] attempt counter reset"
    fi

    if [ "$CHECKPOINT_ERRORS" -eq 0 ]; then
        echo "  $CP_ID is ready for re-dispatch."
        RESET=$((RESET + 1))
    else
        echo "  $CP_ID reset with $CHECKPOINT_ERRORS warning(s) — inspect above before re-dispatching."
        ERRORS=$((ERRORS + 1))
    fi
    echo ""
done

# --- Summary ---

echo "Reset complete: $RESET checkpoint(s) reset cleanly, $ERRORS with warnings."
echo ""
echo "Note: .log files are preserved at $TASKS_DIR/CP-XX.log for post-mortem."
echo ""
echo "Next steps:"
echo "  1. Run /io-plan-batch to generate fresh task files for the reset checkpoints."
echo "  2. Run: bash .claude/scripts/dispatch-agents.sh"

if [ "$ERRORS" -gt 0 ]; then
    exit 1
fi

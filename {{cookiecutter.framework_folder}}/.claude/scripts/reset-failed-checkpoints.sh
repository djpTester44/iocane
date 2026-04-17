#!/usr/bin/env bash
# .claude/scripts/reset-failed-checkpoints.sh
#
# Cleans up failed checkpoint worktrees and resets their dispatch state so they
# can be re-queued by /io-plan-batch and dispatched again.
#
# Preserved: plans/tasks/CP-XX.log, CP-XX.result.json (kept for post-mortem)
# Removed:   worktree, branch, .status, .exit, .eval.json, .eval-result.json, .iocane/CP-XX.attempts
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
        if ! grep -q "^PASS" "$status_file" 2>/dev/null; then
            TARGETS+=("$(basename "$status_file" .status)")
        fi
    done

    # Auto-detect orphaned worktrees (agent died without writing .status)
    for wt_dir in "$REPO_ROOT"/.worktrees/CP-*/; do
        [ -d "$wt_dir" ] || continue
        CP_ID="$(basename "$wt_dir")"
        STATUS_FILE="$TASKS_DIR/$CP_ID.status"
        # Skip if already collected or has a PASS status
        if [ -f "$STATUS_FILE" ]; then
            continue
        fi
        # No status file + worktree exists = orphaned
        TARGETS+=("$CP_ID")
    done
fi

# --- Global escalation state cleanup (runs regardless of CP targets) ---
# Manual `rm .iocane/escalation.flag` remains valid for clearing without this script.
ESCALATION_CLEARED=""
if [ -f "$IOCANE_DIR/escalation.flag" ]; then
    rm "$IOCANE_DIR/escalation.flag"
    echo "[ok] escalation flag cleared"
    ESCALATION_CLEARED="yes"
fi
if [ -f "$IOCANE_DIR/escalation.log" ]; then
    rm "$IOCANE_DIR/escalation.log"
    echo "[ok] escalation log cleared (per-CP logs preserved in plans/tasks/)"
fi
STATE_FILE="$IOCANE_DIR/workflow-state.json"
if [ -f "$STATE_FILE" ]; then
    STATE=$(uv run python -c "
import json
try:
    d = json.load(open('$STATE_FILE', encoding='utf-8'))
    print((d.get('next') or '') + '|' + (d.get('trigger') or ''))
except Exception:
    print('|')
" 2>/dev/null || echo "|")
    EXISTING_NEXT="${STATE%|*}"
    EXISTING_TRIGGER="${STATE#*|}"
    printf '{"next":"%s","trigger":"%s","escalation":false,"timestamp":"%s"}\n' \
        "${EXISTING_NEXT:-unknown}" "${EXISTING_TRIGGER:-reset-failed-checkpoints}" \
        "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" > "$STATE_FILE"
    echo "[ok] workflow-state.json: escalation -> false"
fi
[ -n "$ESCALATION_CLEARED" ] && echo ""

if [ ${#TARGETS[@]} -eq 0 ]; then
    if [ -n "$ESCALATION_CLEARED" ]; then
        echo "No failed checkpoints to reset. Escalation state cleared."
    else
        echo "No failed checkpoints found. Nothing to reset."
    fi
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

    # 4b. Remove eval artifacts
    for eval_artifact in "$TASKS_DIR/$CP_ID.eval.json" "$TASKS_DIR/$CP_ID.eval-result.json"; do
        if [ -f "$eval_artifact" ]; then
            rm "$eval_artifact"
            echo "  [ok] $(basename "$eval_artifact") removed"
        fi
    done

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
echo "Note: Escalation state (flag, log, workflow-state.json) was cleared at script start."
echo ""
echo "Next steps:"
echo "  1. Run /io-plan-batch to generate fresh task files for the reset checkpoints."
echo "  2. Run: bash .claude/scripts/dispatch-agents.sh"

if [ "$ERRORS" -gt 0 ]; then
    exit 1
fi

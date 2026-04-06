#!/usr/bin/env bash
# .claude/scripts/archive-approved.sh
#
# Archives completed checkpoint artifacts out of the active working tree.
# Called by /io-review Step J after human approval.
#
# For remediation checkpoints (CP-NNR, identified by remediates field in plan.yaml),
# also marks corresponding backlog items as resolved with a Remediated annotation.
#
# Moved to archive:  plans/tasks/CP-XX.{log,exit,status,yaml}
#                    plans/tasks/CP-XX.{result,eval,eval-result}.json
#                    plans/tasks/CP-XX.task.validation
#                    .iocane/CP-XX.attempts
# Archive location:  plans/archive/CP-XX/
# Also updates:      plans/backlog.yaml (remediation checkpoints only)
#
# Note: plan.yaml completion status is set by dispatch-agents.sh at merge time.
# This script handles post-review artifact cleanup only.
#
# Usage:
#   bash .claude/scripts/archive-approved.sh CP-01     # archive specific checkpoint(s)
#   bash .claude/scripts/archive-approved.sh CP-01 CP-02
#
# Exits non-zero if any checkpoint could not be fully archived.

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null)}"
TASKS_DIR="$REPO_ROOT/plans/tasks"
ARCHIVE_DIR="$REPO_ROOT/plans/archive"
IOCANE_DIR="$REPO_ROOT/.iocane"
TODAY=$(date +%Y-%m-%d)

if [ -z "$REPO_ROOT" ]; then
    echo "ERROR: Could not determine repo root. Are you inside a git repository?" >&2
    exit 1
fi

# --- Collect targets ---

if [ $# -eq 0 ]; then
    echo "ERROR: At least one CP-ID argument is required." >&2
    echo "Usage: bash .claude/scripts/archive-approved.sh CP-01 [CP-02 ...]" >&2
    exit 1
fi

TARGETS=()
for CP_ID in "$@"; do
    TARGETS+=("$CP_ID")
done

echo "Checkpoints to archive: ${TARGETS[*]}"
echo ""

ARCHIVED=0
ERRORS=0

for CP_ID in "${TARGETS[@]}"; do
    echo "--- $CP_ID ---"

    DEST="$ARCHIVE_DIR/$CP_ID"
    mkdir -p "$DEST"

    CHECKPOINT_ERRORS=0

    # Move each artifact if it exists
    for ext in log exit status yaml; do
        SRC="$TASKS_DIR/$CP_ID.$ext"
        if [ -f "$SRC" ]; then
            mv "$SRC" "$DEST/$CP_ID.$ext"
            echo "  [ok] $CP_ID.$ext -> plans/archive/$CP_ID/"
        fi
    done

    # Move compound-extension artifacts (handled separately from simple extensions)
    for compound_ext in result.json eval.json eval-result.json task.validation; do
        SRC="$TASKS_DIR/$CP_ID.$compound_ext"
        if [ -f "$SRC" ]; then
            mv "$SRC" "$DEST/$CP_ID.$compound_ext"
            echo "  [ok] $CP_ID.$compound_ext -> plans/archive/$CP_ID/"
        fi
    done

    # Move attempt counter from .iocane/
    ATTEMPT_FILE="$IOCANE_DIR/$CP_ID.attempts"
    if [ -f "$ATTEMPT_FILE" ]; then
        mv "$ATTEMPT_FILE" "$DEST/$CP_ID.attempts"
        echo "  [ok] $CP_ID.attempts -> plans/archive/$CP_ID/"
    fi

    # For remediation checkpoints: mark corresponding backlog items as remediated
    PLAN_FILE="$REPO_ROOT/plans/plan.yaml"
    BACKLOG_FILE="$REPO_ROOT/plans/backlog.yaml"
    if [ -f "$PLAN_FILE" ] && [ -f "$BACKLOG_FILE" ]; then
        IS_REMEDIATION=$(uv run python -c "
import sys
sys.path.insert(0, '${REPO_ROOT}/.claude/scripts')
from plan_parser import load_plan, find_checkpoint
plan = load_plan(sys.argv[1])
cp = find_checkpoint(plan, sys.argv[2])
print('yes' if cp and cp.remediates is not None else 'no')
" "$PLAN_FILE" "$CP_ID" 2>/dev/null || echo "no")

        if [ "$IS_REMEDIATION" = "yes" ]; then
            if uv run python -c "
import sys
sys.path.insert(0, '${REPO_ROOT}/.claude/scripts')
from plan_parser import load_plan, find_checkpoint
from backlog_parser import (
    load_backlog, save_backlog, find_item, mark_resolved, add_annotation,
)
from schemas import Annotation

backlog_path = sys.argv[1]
plan_path = sys.argv[2]
cp_id = sys.argv[3]
today = sys.argv[4]

# Step 1: Read CP from plan.yaml, extract source_bl
plan = load_plan(plan_path)
cp = find_checkpoint(plan, cp_id)
if not cp:
    print(f'ERROR: {cp_id} not found in plan.yaml', file=sys.stderr)
    sys.exit(1)
bl_ids = cp.source_bl or []
if not bl_ids:
    print(f'ERROR: No source_bl field in {cp_id}', file=sys.stderr)
    sys.exit(1)

# Step 2: Load backlog and mark items
backlog = load_backlog(backlog_path)
marked = 0
for bl_id in bl_ids:
    item = find_item(backlog, bl_id)
    if item is None:
        print(f'  WARN: {bl_id} not found in backlog.yaml, skipping.', file=sys.stderr)
        continue
    if item.status.value != 'open':
        print(f'  SKIP: {bl_id} is not an open item (already resolved or deferred).', file=sys.stderr)
        continue
    ann = Annotation(type='Remediated', value=cp_id, date=today)
    backlog = add_annotation(backlog, bl_id, ann)
    backlog = mark_resolved(backlog, bl_id)
    marked += 1
    print(f'  Marked {bl_id} as remediated via {cp_id}.')

if marked == 0:
    print(f'ERROR: No BL items could be marked for {cp_id}', file=sys.stderr)
    sys.exit(1)
save_backlog(backlog_path, backlog)
" "$BACKLOG_FILE" "$PLAN_FILE" "$CP_ID" "$TODAY" 2>/dev/null; then
                echo "  [ok] backlog.yaml items marked remediated"
            else
                echo "  WARN: Could not resolve Source BL for $CP_ID in backlog.yaml." >&2
            fi
        fi
    fi

    if [ "$CHECKPOINT_ERRORS" -eq 0 ]; then
        echo "  $CP_ID archived."
        ARCHIVED=$((ARCHIVED + 1))
    else
        echo "  $CP_ID archived with $CHECKPOINT_ERRORS warning(s)."
        ERRORS=$((ERRORS + 1))
    fi
    echo ""
done

# --- Summary ---

echo "Archive complete: $ARCHIVED checkpoint(s) archived cleanly, $ERRORS with errors."
echo ""
echo "Archived files are at plans/archive/ and remain in git history."

if [ "$ERRORS" -gt 0 ]; then
    exit 1
fi

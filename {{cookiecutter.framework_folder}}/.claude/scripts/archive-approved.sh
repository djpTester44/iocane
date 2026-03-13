#!/usr/bin/env bash
# .claude/scripts/archive-approved.sh
#
# Archives completed, approved checkpoints out of the active working tree.
# A checkpoint is eligible when plans/tasks/CP-XX.approved exists (written by
# /review Step I when the human selects option 1).
#
# Moved to archive:  plans/tasks/CP-XX.{approved,log,exit,status,md}
#                    .iocane/CP-XX.attempts
# Archive location:  plans/archive/CP-XX/
#
# Usage:
#   bash .claude/scripts/archive-approved.sh           # archive all approved checkpoints
#   bash .claude/scripts/archive-approved.sh CP-01     # archive specific checkpoint(s)
#   bash .claude/scripts/archive-approved.sh CP-01 CP-02
#
# Exits non-zero if any checkpoint could not be fully archived.

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null)}"
TASKS_DIR="$REPO_ROOT/plans/tasks"
ARCHIVE_DIR="$REPO_ROOT/plans/archive"
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
    # Auto-detect all checkpoints with an .approved marker
    for approved_file in "$TASKS_DIR"/CP-*.approved; do
        [ -f "$approved_file" ] || continue
        TARGETS+=("$(basename "$approved_file" .approved)")
    done
fi

if [ ${#TARGETS[@]} -eq 0 ]; then
    echo "No approved checkpoints found. Nothing to archive."
    exit 0
fi

echo "Checkpoints to archive: ${TARGETS[*]}"
echo ""

ARCHIVED=0
ERRORS=0

for CP_ID in "${TARGETS[@]}"; do
    APPROVED_FILE="$TASKS_DIR/$CP_ID.approved"
    echo "--- $CP_ID ---"

    # Safety check: must have an .approved marker
    if [ ! -f "$APPROVED_FILE" ]; then
        echo "  ERROR: $CP_ID has no .approved marker — refusing to archive an unapproved checkpoint." >&2
        ERRORS=$((ERRORS + 1))
        echo ""
        continue
    fi

    DEST="$ARCHIVE_DIR/$CP_ID"
    mkdir -p "$DEST"

    CHECKPOINT_ERRORS=0

    # Move each artifact if it exists
    for ext in approved log exit status md; do
        SRC="$TASKS_DIR/$CP_ID.$ext"
        if [ -f "$SRC" ]; then
            mv "$SRC" "$DEST/$CP_ID.$ext"
            echo "  [ok] $CP_ID.$ext -> plans/archive/$CP_ID/"
        fi
    done

    # Move attempt counter from .iocane/
    ATTEMPT_FILE="$IOCANE_DIR/$CP_ID.attempts"
    if [ -f "$ATTEMPT_FILE" ]; then
        mv "$ATTEMPT_FILE" "$DEST/$CP_ID.attempts"
        echo "  [ok] $CP_ID.attempts -> plans/archive/$CP_ID/"
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

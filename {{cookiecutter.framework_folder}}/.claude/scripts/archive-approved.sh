#!/usr/bin/env bash
# .claude/scripts/archive-approved.sh
#
# Archives completed checkpoint artifacts out of the active working tree.
# Called by /io-review Step J after human approval.
#
# For remediation checkpoints (CP-NNR, identified by **Remediates:** in plan.md),
# also marks corresponding backlog items as [x] with a Remediated annotation.
#
# Moved to archive:  plans/tasks/CP-XX.{log,exit,status,md}
#                    .iocane/CP-XX.attempts
# Archive location:  plans/archive/CP-XX/
# Also updates:      plans/plan.md status from [ ] pending to [x] complete
#                    plans/backlog.md (remediation checkpoints only)
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
    for ext in log exit status md; do
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

    # Update plan.md status from [ ] pending to [x] complete
    PLAN_FILE="$REPO_ROOT/plans/plan.md"
    if [ -f "$PLAN_FILE" ]; then
        if uv run python -c "
import re, sys
sys.path.insert(0, '${REPO_ROOT}/.claude/scripts')
from backlog_parser import extract_cp_section
path = sys.argv[1]
cp_id = sys.argv[2]
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()
pattern = r'(### ' + re.escape(cp_id) + r':.*?\n(?:(?!###).*?\n)*?\*\*Status:\*\*) \[ \] pending'
updated, count = re.subn(pattern, r'\1 [x] complete', text)
if count == 0:
    sys.exit(1)
with open(path, 'w', encoding='utf-8') as f:
    f.write(updated)
" "$PLAN_FILE" "$CP_ID" 2>/dev/null; then
            echo "  [ok] plan.md status -> [x] complete"
        else
            echo "  WARN: Could not update $CP_ID status in plan.md (already complete or not found)." >&2
        fi
    fi

    # For remediation checkpoints: mark corresponding backlog items as remediated
    BACKLOG_FILE="$REPO_ROOT/plans/backlog.md"
    if [ -f "$PLAN_FILE" ] && [ -f "$BACKLOG_FILE" ]; then
        IS_REMEDIATION=$(uv run python -c "
import sys
sys.path.insert(0, '${REPO_ROOT}/.claude/scripts')
from backlog_parser import extract_cp_section
path = sys.argv[1]
cp_id = sys.argv[2]
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()
section = extract_cp_section(text, cp_id)
print('yes' if section and '**Remediates:**' in section else 'no')
" "$PLAN_FILE" "$CP_ID" 2>/dev/null || echo "no")

        if [ "$IS_REMEDIATION" = "yes" ]; then
            if uv run python -c "
import re, sys
sys.path.insert(0, '${REPO_ROOT}/.claude/scripts')
from backlog_parser import (
    read_lines, write_lines, extract_cp_section, extract_bl_ids_from_text,
    build_bl_index, find_summary_line, walk_subfields, insert_subfield, shift_bl_index,
)

backlog_path = sys.argv[1]
plan_path = sys.argv[2]
cp_id = sys.argv[3]
today = sys.argv[4]

# Step 1: Read CP section from plan.md, extract Source BL field
with open(plan_path, 'r', encoding='utf-8') as f:
    plan_text = f.read()
section = extract_cp_section(plan_text, cp_id)
if not section:
    print(f'ERROR: {cp_id} section not found in plan.md', file=sys.stderr)
    sys.exit(1)
source_bl_line = section.split('**Source BL:**')[-1].split('\n')[0] if '**Source BL:**' in section else ''
bl_ids = extract_bl_ids_from_text(source_bl_line)
if not bl_ids:
    print(f'ERROR: No **Source BL:** field in {cp_id} section', file=sys.stderr)
    sys.exit(1)

# Step 2: Build BL-ID index from backlog
lines = read_lines(backlog_path)
bl_index = build_bl_index(lines)

marked = 0
for bl_id in bl_ids:
    if bl_id not in bl_index:
        print(f'  WARN: {bl_id} not found in backlog.md, skipping.', file=sys.stderr)
        continue

    anchor = bl_index[bl_id]
    summary_idx = find_summary_line(lines, anchor)
    if summary_idx is None or not re.match(r'^- \[ \]', lines[summary_idx]):
        print(f'  SKIP: {bl_id} is not an open item (already resolved or malformed).', file=sys.stderr)
        continue
    lines[summary_idx] = '- [x]' + lines[summary_idx][5:]

    insert_after = walk_subfields(lines, summary_idx)
    insert_subfield(lines, insert_after, f'  - Remediated: {cp_id} ({today})\n')
    shift_bl_index(bl_index, insert_after)
    marked += 1
    print(f'  Marked {bl_id} as remediated via {cp_id}.')

if marked == 0:
    print(f'ERROR: No BL items could be marked for {cp_id}', file=sys.stderr)
    sys.exit(1)
write_lines(backlog_path, lines)
" "$BACKLOG_FILE" "$PLAN_FILE" "$CP_ID" "$TODAY" 2>/dev/null; then
                echo "  [ok] backlog.md items marked remediated"
            else
                echo "  WARN: Could not resolve Source BL for $CP_ID in backlog.md." >&2
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

#!/usr/bin/env bash
# .claude/scripts/route-backlog-item.sh
#
# Annotates a backlog item with a Routed: annotation.
# Deterministic replacement for instruction-based routing in io-checkpoint.
#
# Usage:
#   bash .claude/scripts/route-backlog-item.sh BL-NNN CP-NNR
#
# Fails if BL-NNN not found or already routed to the given CP.

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null)}"
BACKLOG_FILE="$REPO_ROOT/plans/backlog.md"

if [ $# -ne 2 ]; then
    echo "Usage: bash .claude/scripts/route-backlog-item.sh BL-NNN CP-NNR" >&2
    exit 1
fi

BL_ID="$1"
CP_ID="$2"
TODAY=$(date +%Y-%m-%d)

if [ ! -f "$BACKLOG_FILE" ]; then
    echo "ERROR: $BACKLOG_FILE not found." >&2
    exit 1
fi

uv run python -c "
import sys
sys.path.insert(0, '${REPO_ROOT}/.claude/scripts')
from backlog_parser import read_lines, write_lines, find_bl_anchor, find_summary_line, walk_subfields, insert_subfield

backlog_path = sys.argv[1]
bl_id = sys.argv[2]
cp_id = sys.argv[3]
today = sys.argv[4]

lines = read_lines(backlog_path)

anchor = find_bl_anchor(lines, bl_id)
if anchor < 0:
    print(f'ERROR: {bl_id} not found in {backlog_path}', file=sys.stderr)
    sys.exit(1)

summary_idx = find_summary_line(lines, anchor)
if summary_idx is None:
    print(f'ERROR: No summary line found after {bl_id}', file=sys.stderr)
    sys.exit(1)

# Walk sub-fields, checking for duplicate Routed: annotation
insert_after = summary_idx
i = summary_idx + 1
while i < len(lines):
    stripped = lines[i].rstrip('\n')
    if stripped.startswith('  - '):
        if f'Routed: {cp_id} ' in stripped or f'Routed: {cp_id}' in stripped.rstrip():
            print(f'ERROR: {bl_id} already has a Routed annotation for {cp_id}', file=sys.stderr)
            sys.exit(1)
        insert_after = i
        i += 1
    else:
        break

annotation = f'  - Routed: {cp_id} ({today})\n'
insert_subfield(lines, insert_after, annotation)
write_lines(backlog_path, lines)

print(f'Routed {bl_id} -> {cp_id} ({today})')
" "$BACKLOG_FILE" "$BL_ID" "$CP_ID" "$TODAY"

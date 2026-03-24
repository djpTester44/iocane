#!/usr/bin/env bash
# .claude/scripts/assign-backlog-ids.sh
#
# Assigns BL-NNN identifiers to backlog items in plans/backlog.md.
# Idempotent -- safe to re-run. Skips items that already have IDs.
#
# Usage:
#   bash .claude/scripts/assign-backlog-ids.sh

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null)}"
BACKLOG_FILE="$REPO_ROOT/plans/backlog.md"

if [ ! -f "$BACKLOG_FILE" ]; then
    echo "ERROR: $BACKLOG_FILE not found." >&2
    exit 1
fi

uv run python -c "
import re
import sys
sys.path.insert(0, '${REPO_ROOT}/.claude/scripts')
from backlog_parser import read_lines, write_lines, find_max_bl_id

backlog_path = sys.argv[1]
lines = read_lines(backlog_path)

max_id = find_max_bl_id(lines)
next_id = max_id + 1

# Walk through lines and insert IDs where needed
result: list[str] = []
assigned = 0
for line in lines:
    if re.match(r'^- \[[ x]\]', line):
        # Check if previous non-empty line is already a BL-NNN header
        has_id = False
        for j in range(len(result) - 1, -1, -1):
            prev = result[j].strip()
            if prev:
                if re.fullmatch(r'\*\*BL-\d{3}\*\*', prev):
                    has_id = True
                break
        if not has_id:
            bl_id = f'BL-{next_id:03d}'
            result.append(f'**{bl_id}**\n')
            assigned += 1
            next_id += 1
    result.append(line)

if assigned > 0:
    write_lines(backlog_path, result)
    print(f'Assigned {assigned} new backlog ID(s). Range: BL-{max_id + 1:03d} to BL-{next_id - 1:03d}')
else:
    print('No new IDs needed -- backlog is already fully tagged.')
" "$BACKLOG_FILE"

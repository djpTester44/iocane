#!/usr/bin/env bash
# PostToolUse hook: Edit | Write
# Auto-assigns BL-NNN identifiers to new backlog items after any write to
# plans/backlog.yaml. Delegates to assign_backlog_ids.py (idempotent).
#
# NOTE: Designed to run from a generated project root.
# This script is a harness template artifact.

INPUT=$(cat)

FILE_PATH=$(uv run python -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('tool_input', {}).get('file_path', ''))
except Exception:
    print('')
" <<< "$INPUT")

if [ -z "$FILE_PATH" ]; then
    exit 0
fi

MATCH=$(FILE_PATH="$FILE_PATH" uv run python -c "
import os, sys
p = os.path.normpath(os.environ['FILE_PATH']).replace('\\\\', '/')
print('yes' if p.endswith('plans/backlog.yaml') else 'no')
")

if [ "$MATCH" = "yes" ] && [ -f "plans/backlog.yaml" ]; then
    uv run python .claude/scripts/assign_backlog_ids.py
fi

exit 0

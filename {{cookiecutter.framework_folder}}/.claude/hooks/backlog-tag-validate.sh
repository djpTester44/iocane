#!/usr/bin/env bash
# PostToolUse hook: Edit | Write
# Validates backlog.yaml items against Pydantic schema on every write.
# Replaces grep-based tag validation with full schema enforcement.

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

if [ "$MATCH" != "yes" ] || [ ! -f "plans/backlog.yaml" ]; then
    exit 0
fi

# Validate via Pydantic schema -- load_backlog raises on invalid data
uv run python -c "
import sys
sys.path.insert(0, '.claude/scripts')
from backlog_parser import load_backlog
try:
    backlog = load_backlog('plans/backlog.yaml')
    print(f'backlog-tag-validate: {len(backlog.items)} item(s) validated OK.')
except Exception as e:
    print(f'WARNING: backlog.yaml schema validation failed: {e}')
"

exit 0

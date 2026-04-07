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

# Validate via Pydantic schema -- load_backlog raises on invalid data.
# Pydantic ValidationError = blocking (exit 2). Other errors = advisory (exit 0).
RESULT=$(uv run python -c "
import sys
sys.path.insert(0, '.claude/scripts')
from backlog_parser import load_backlog
try:
    backlog = load_backlog('plans/backlog.yaml')
    print(f'PASS:{len(backlog.items)}')
except Exception as e:
    etype = type(e).__name__
    if 'ValidationError' in etype:
        print(f'SCHEMA_FAIL:{e}')
    else:
        print(f'WARN:{e}')
" 2>/dev/null) || RESULT="WARN:backlog_parser unavailable"

case "$RESULT" in
    PASS:*)
        COUNT="${RESULT#PASS:}"
        echo "backlog-tag-validate: $COUNT item(s) validated OK."
        exit 0
        ;;
    SCHEMA_FAIL:*)
        DETAIL="${RESULT#SCHEMA_FAIL:}"
        echo "BLOCKED: backlog.yaml schema validation failed: $DETAIL" >&2
        exit 2
        ;;
    *)
        DETAIL="${RESULT#WARN:}"
        echo "WARNING: backlog.yaml validation: $DETAIL"
        exit 0
        ;;
esac

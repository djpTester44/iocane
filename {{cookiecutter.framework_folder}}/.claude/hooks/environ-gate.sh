#!/usr/bin/env bash
# PreToolUse hook: Edit | Write
# Blocks os.environ/os.getenv usage outside the entrypoint layer.
# Allowed files: config.py, main.py, jobs/*.py

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | uv run python -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('tool_input', {}).get('file_path', ''))
except Exception:
    print('')
")

# Only gate on Python files
if [[ "$FILE_PATH" != *.py ]]; then
    exit 0
fi

# Allow entrypoint layer files
if echo "$FILE_PATH" | grep -qE '(^|/)config\.py$|(^|/)main\.py$|(^|/)jobs/[^/]+\.py$'; then
    exit 0
fi

CONTENT=$(echo "$INPUT" | uv run python -c "
import sys, json
try:
    d = json.load(sys.stdin)
    ti = d.get('tool_input', {})
    print(ti.get('new_string', '') or ti.get('content', ''))
except Exception:
    print('')
")

if [ -z "$CONTENT" ]; then
    exit 0
fi

if echo "$CONTENT" | grep -qE 'os\.environ|os\.getenv'; then
    echo "BLOCKED: os.environ/os.getenv used outside the entrypoint layer ($FILE_PATH)." >&2
    echo "         Inject config via a typed Settings object. Only config.py, main.py, and jobs/*.py may access os.environ." >&2
    exit 2
fi

exit 0

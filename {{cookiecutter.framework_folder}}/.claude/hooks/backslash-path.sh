#!/usr/bin/env bash
# PreToolUse hook: Edit | Write
# Blocks writes where file_path contains a literal backslash.
# Forward slashes are required on all platforms per the engineering constitution.

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | uv run python -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('tool_input', {}).get('file_path', ''))
except Exception:
    print('')
")

if [[ "$FILE_PATH" == *\\* ]]; then
    echo "BLOCKED: Backslash in file path. Use forward slashes."
    exit 2
fi

exit 0

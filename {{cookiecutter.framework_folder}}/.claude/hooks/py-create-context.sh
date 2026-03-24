#!/usr/bin/env bash
# PreToolUse hook: Edit | Write
# When a new .py file is created, echo key standards as a context reminder.
# Advisory only -- exits 0 (non-blocking).

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | uv run python -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('tool_input', {}).get('file_path', ''))
except Exception:
    print('')
")

if [[ "$FILE_PATH" != *.py ]]; then
    exit 0
fi

echo "[context] New .py file: ensure module docstring (D100), pathlib for paths, custom exceptions not sentinels, DI compliance if class has collaborators."

exit 0

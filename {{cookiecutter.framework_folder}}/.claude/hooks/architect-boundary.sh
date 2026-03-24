#!/usr/bin/env bash
# PreToolUse hook: Edit | Write
# Blocks .py file writes while .iocane/architect-mode sentinel is active.
# The sentinel is created by /io-architect on entry and removed on exit.
# NOTE: /io-architect command does not yet manage this sentinel automatically.
#       Until it does, the sentinel must be managed manually:
#         touch .iocane/architect-mode   # enter design phase
#         rm .iocane/architect-mode      # exit design phase

# Only active when the sentinel exists
if [ ! -f ".iocane/architect-mode" ]; then
    exit 0
fi

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | uv run python -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('tool_input', {}).get('file_path', ''))
except Exception:
    print('')
")

if [[ "$FILE_PATH" == *.py ]]; then
    echo "BLOCKED: /io-architect is active. Python implementation files cannot be written during design phase."
    exit 2
fi

exit 0

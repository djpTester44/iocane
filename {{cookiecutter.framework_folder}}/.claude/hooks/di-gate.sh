#!/usr/bin/env bash
# PreToolUse hook: Edit | Write
# Before any .py write, ensures the codebase passes DI compliance.
#
# NOTE: Designed to run from a generated project root where plans/ and src/ exist.
# This script is a harness template artifact and will not function correctly
# when invoked from the iocane harness repo itself.

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | uv run python -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('tool_input', {}).get('file_path', ''))
except Exception:
    print('')
")

# Only gate on Python files.
if [[ "$FILE_PATH" != *.py ]]; then
    exit 0
fi

# Only gate in haiku sub-agent sessions; interactive sessions have a human present.
SESSION_MODEL=$(cat .iocane/session-model 2>/dev/null || echo "")
if [[ "$SESSION_MODEL" != *"haiku"* ]]; then
    exit 0
fi

# Compliance script must exist to run the gate.
if [ ! -f ".agent/scripts/check_di_compliance.py" ]; then
    exit 0
fi

OUTPUT=$(uv run python .agent/scripts/check_di_compliance.py 2>&1)
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo "BLOCKED: DI compliance check failed for $FILE_PATH."
    echo ""
    echo "$OUTPUT"
    exit 2
fi

exit 0

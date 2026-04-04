#!/usr/bin/env bash
# PostToolUse hook: Edit | Write
# Resets the Clarified stamp in plans/PRD.md after any substantive write.
#
# Exempt: if .iocane/validating sentinel file exists, the write is a stamp-only
# update (e.g. /io-clarify setting Clarified: True) and must NOT be reset.
# The sentinel is created before the stamp write and deleted after. It persists
# across tool calls within a session because it is shared filesystem state.
#
# NOTE: Designed to run from a generated project root.
# This script is a harness template artifact.

INPUT=$(cat)

if [ -f ".iocane/validating" ]; then
    # If this write IS the Clarified stamp itself, the sentinel's job is done.
    # Auto-delete so the agent does not need an explicit cleanup step.
    NEW_CONTENT=$(printf '%s' "$INPUT" | uv run python -c "
import sys, json
try:
    d = json.load(sys.stdin)
    ti = d.get('tool_input', {})
    print(ti.get('new_string', '') or ti.get('content', ''))
except Exception:
    print('')
")
    if echo "$NEW_CONTENT" | grep -q "\*\*Clarified:\*\* True"; then
        rm -f .iocane/validating
    fi
    exit 0
fi

FILE_PATH=$(printf '%s' "$INPUT" | uv run python -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('tool_input', {}).get('file_path', ''))
except Exception:
    print('')
")

if [ -z "$FILE_PATH" ]; then
    exit 0
fi

# Normalize and check if target is plans/PRD.md
MATCH=$(FILE_PATH="$FILE_PATH" uv run python -c "
import os, sys
p = os.path.normpath(os.environ['FILE_PATH']).replace('\\\\', '/')
print('yes' if p.endswith('plans/PRD.md') else 'no')
")

if [ "$MATCH" = "yes" ] && [ -f "plans/PRD.md" ]; then
    sed -i 's/\*\*Clarified:\*\* True/\*\*Clarified:\*\* False/g' "plans/PRD.md"
fi

exit 0

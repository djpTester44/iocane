#!/usr/bin/env bash
# PostToolUse hook: Edit | Write
# Resets the Plan Validated stamp in plans/plan.md after any substantive write.
#
# Exempt: if .iocane/validating sentinel file exists, the write is a stamp-only
# update (e.g. /validate-plan setting Plan Validated: PASS) and must NOT be reset.
# The sentinel is created before the stamp write and deleted after. It persists
# across tool calls within a session because it is shared filesystem state.
#
# NOTE: Designed to run from a generated project root.
# This script is a harness template artifact.

if [ -f ".iocane/validating" ]; then
    # If this write IS the Plan Validated stamp itself, the sentinel's job is done.
    # Auto-delete so the agent does not need an explicit cleanup step.
    NEW_CONTENT=$(python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    ti = d.get('tool_input', {})
    print(ti.get('new_string', '') or ti.get('content', ''))
except Exception:
    print('')
" <<< "$INPUT")
    if echo "$NEW_CONTENT" | grep -qE "\*\*Plan Validated:\*\* (PASS|FAIL)"; then
        rm -f .iocane/validating
    fi
    exit 0
fi

INPUT=$(cat)

FILE_PATH=$(python3 -c "
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

MATCH=$(python3 -c "
import os, sys
p = os.path.normpath('$FILE_PATH').replace('\\\\', '/')
print('yes' if p.endswith('plans/plan.md') else 'no')
")

if [ "$MATCH" = "yes" ] && [ -f "plans/plan.md" ]; then
    sed -i 's/\*\*Plan Validated:\*\* PASS/\*\*Plan Validated:\*\* FAIL/g' "plans/plan.md"
fi

exit 0

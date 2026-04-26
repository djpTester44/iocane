#!/usr/bin/env bash
# PostToolUse hook: Edit | Write
# Resets the Clarified stamp in plans/PRD.md after any substantive write.
#
# Bypass: if a capability grant covers write:plans/PRD.md for this
# session, the write is authored (e.g. /io-clarify Step 7 setting
# **Clarified:** True) and must NOT be reset.
#
# NOTE: Designed to run from a generated project root.
# This script is a harness template artifact.

INPUT=$(cat)

EXTRACT=$(printf '%s' "$INPUT" | uv run python -c "
import sys, json
try:
    d = json.load(sys.stdin)
except Exception:
    print('\\n'); sys.exit(0)
sid = d.get('session_id', '') or ''
fp = (d.get('tool_input') or {}).get('file_path', '') or ''
print(sid)
print(fp)
" 2>/dev/null)

SID=$(printf '%s' "$EXTRACT" | sed -n '1p')
FILE_PATH=$(printf '%s' "$EXTRACT" | sed -n '2p')

if [ -n "$SID" ] && [ -n "$FILE_PATH" ]; then
    if bash .claude/scripts/capability-covers.sh "$SID" "write" "$FILE_PATH"; then
        exit 0
    fi
fi

if [ -z "$FILE_PATH" ]; then
    exit 0
fi

MATCH=$(FILE_PATH="$FILE_PATH" uv run python -c "
import os, sys
p = os.path.normpath(os.environ['FILE_PATH']).replace('\\\\', '/')
print('yes' if p.endswith('plans/PRD.md') else 'no')
")

if [ "$MATCH" = "yes" ] && [ -f "plans/PRD.md" ]; then
    sed -i 's/\*\*Clarified:\*\* True/\*\*Clarified:\*\* False/g' "plans/PRD.md"
fi

exit 0

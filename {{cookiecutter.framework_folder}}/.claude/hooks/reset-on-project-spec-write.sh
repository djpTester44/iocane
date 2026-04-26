#!/usr/bin/env bash
# PostToolUse hook: Edit | Write
# Resets the Approved stamp in plans/project-spec.md after any substantive write.
#
# Bypass: if a capability grant covers write:plans/project-spec.md for
# this session, the write is authored (e.g. /validate-spec Step F or
# /auto-architect Step F.9 setting **Approved:** True). Inside the
# bypass, content detection drives the workflow-state transition --
# legitimate state-machine logic, not a sentinel workaround.
#
# NOTE: Designed to run from a generated project root.
# This script is a harness template artifact.

INPUT=$(cat)

EXTRACT=$(printf '%s' "$INPUT" | uv run python -c "
import sys, json
try:
    d = json.load(sys.stdin)
except Exception:
    print('\\n\\n'); sys.exit(0)
sid = d.get('session_id', '') or ''
ti = d.get('tool_input') or {}
fp = ti.get('file_path', '') or ''
content = ti.get('new_string', '') or ti.get('content', '') or ''
print(sid)
print(fp)
print(content)
" 2>/dev/null)

SID=$(printf '%s' "$EXTRACT" | sed -n '1p')
FILE_PATH=$(printf '%s' "$EXTRACT" | sed -n '2p')
NEW_CONTENT=$(printf '%s' "$EXTRACT" | sed -n '3,$p')

if [ -n "$SID" ] && [ -n "$FILE_PATH" ]; then
    if bash .claude/scripts/capability-covers.sh "$SID" "write" "$FILE_PATH"; then
        # Authored write. If this is the Approved:True stamp, drive
        # the workflow-state transition toward io-checkpoint.
        if echo "$NEW_CONTENT" | grep -q "\*\*Approved:\*\* True"; then
            TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date +"%Y-%m-%dT%H:%M:%SZ")
            mkdir -p .iocane
            printf '{"next":"io-checkpoint","trigger":"project-spec.md (Approved: True)","timestamp":"%s"}\n' \
                "$TIMESTAMP" > .iocane/workflow-state.json
        fi
        exit 0
    fi
fi

if [ -z "$FILE_PATH" ]; then
    exit 0
fi

MATCH=$(FILE_PATH="$FILE_PATH" uv run python -c "
import os, sys
p = os.path.normpath(os.environ['FILE_PATH']).replace('\\\\', '/')
print('yes' if p.endswith('plans/project-spec.md') else 'no')
")

if [ "$MATCH" = "yes" ] && [ -f "plans/project-spec.md" ]; then
    sed -i 's/\*\*Approved:\*\* True/\*\*Approved:\*\* False/g' "plans/project-spec.md"

    # State derivation: Approved reset -> needs architect review
    TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date +"%Y-%m-%dT%H:%M:%SZ")
    mkdir -p .iocane
    printf '{"next":"io-architect","trigger":"project-spec.md (Approved: False)","timestamp":"%s"}\n' \
        "$TIMESTAMP" > .iocane/workflow-state.json
fi

exit 0

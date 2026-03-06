#!/usr/bin/env bash
# SessionStart hook: inject execution handoff bundle into session context.
#
# NOTE: Designed to run from a generated project root where plans/ exists.
# This script is a harness template artifact and will not function correctly
# when invoked from the iocane harness repo itself.

BUNDLE="plans/execution-handoff-bundle.md"

if [ -f "$BUNDLE" ] && [ -s "$BUNDLE" ]; then
    CONTENT=$(cat "$BUNDLE")
    uv run python -c "
import json, sys
content = sys.stdin.read()
print(json.dumps({'systemPrompt': content}))
" <<< "$CONTENT"
else
    echo '{"systemPrompt": "No active handoff bundle found. If starting an execution session, run /io-handoff first."}'
fi

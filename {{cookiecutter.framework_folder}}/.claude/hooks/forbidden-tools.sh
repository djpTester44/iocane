#!/usr/bin/env bash
# PreToolUse hook: Bash
# Blocks pip/pip3/python -m pip invocations per AGENTS.md rule #1.
#
# NOTE: Designed to run from a generated project root where plans/ and src/ exist.
# This script is a harness template artifact and will not function correctly
# when invoked from the iocane harness repo itself.

INPUT=$(cat)

COMMAND=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('tool_input', {}).get('command', ''))
except Exception:
    print('')
")

if echo "$COMMAND" | grep -qE '(^|[[:space:];&|])(pip3?[[:space:]]|python[0-9.]* -m pip|uv pip[[:space:]])'; then
    echo "BLOCKED: Use uv add or uv run instead. Direct pip invocations and uv pip are forbidden — they bypass the lockfile."
    exit 2
fi

exit 0

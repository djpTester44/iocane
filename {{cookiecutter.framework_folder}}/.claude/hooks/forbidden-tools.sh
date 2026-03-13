#!/usr/bin/env bash
# PreToolUse hook: Bash
# Blocks pip/pip3/python -m pip invocations per AGENTS.md rule #1.
#
# NOTE: Designed to run from a generated project root where plans/ and src/ exist.
# This script is a harness template artifact and will not function correctly
# when invoked from the iocane harness repo itself.

INPUT=$(cat)

COMMAND=$(echo "$INPUT" | uv run rtk python -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('tool_input', {}).get('command', ''))
except Exception:
    print('')
")

# Block upward directory traversal for sub-agents.
if [ "${IOCANE_SUBAGENT:-0}" = "1" ]; then
    if echo "$COMMAND" | grep -qE 'cd[[:space:]]+(\.\.|[^[:space:]]*\.\.[^[:space:]]*)|(&&|;|\|)[[:space:]]*cd[[:space:]]+\.\.'; then
        echo "BLOCKED: cd .. traversal is forbidden in sub-agent context. If a file is missing, you wrote it to the wrong path � fix the write, not the directory." >&2
        exit 2
    fi
fi

if echo "$COMMAND" | grep -qE '(^|[[:space:];&|])(pip3?[[:space:]]|python[0-9.]* -m pip|uv pip[[:space:]])'; then
    echo "BLOCKED: Use uv add or uv run rtk instead. Direct pip invocations and uv pip are forbidden — they bypass the lockfile."
    exit 2
fi

# Block bare python/python3 invocations — use uv run rtk python instead (AGENTS.md rule #10).
# Strip all 'uv run rtk python' occurrences first so they are not matched as bare python.
STRIPPED=$(echo "$COMMAND" | sed 's/uv run rtk python[0-9.]*//g')
if echo "$STRIPPED" | grep -qE '(^|[[:space:];&|])(python3?[[:space:]]|python3?\.[0-9]+[[:space:]])'; then
    echo "BLOCKED: Use uv run rtk python instead of bare python/python3. Naked interpreter calls resolve to the wrong environment on Windows." >&2
    exit 2
fi

exit 0

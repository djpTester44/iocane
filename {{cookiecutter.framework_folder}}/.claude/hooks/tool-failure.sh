#!/usr/bin/env bash
# PostToolUseFailure hook: capture tool execution failures across all tool types.
#
# Input fields:
#   tool_name    -- name of the tool that failed
#   tool_input   -- input passed to the tool (object)
#   error        -- error message string
#   is_interrupt -- true if the failure was caused by user interrupt
#
# Output: corrective feedback to stdout (Claude receives this as context).
# Logs all failures to .iocane/tool-failure.log.
#
# Source: hooks.md:1112-1114 (Claude Code docs -- PostToolUseFailure input schema)

set -euo pipefail

INPUT=$(cat)
mkdir -p .iocane

PARSED=$(printf '%s' "$INPUT" | uv run python -c "
import sys, json
raw = sys.stdin.read()
d = json.loads(raw) if raw.strip() else {}
print(d.get('tool_name', 'unknown'))
print(str(d.get('is_interrupt', False)).lower())
# Truncate error to avoid log bloat
print(d.get('error', '')[:500])
" 2>/dev/null || printf 'unknown\nfalse\nunknown error\n')

TOOL_NAME=$(echo "$PARSED" | sed -n '1p')
IS_INTERRUPT=$(echo "$PARSED" | sed -n '2p')
ERROR_MSG=$(echo "$PARSED" | sed -n '3p')

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
printf '%s tool=%s interrupt=%s error=%s\n' \
    "$TIMESTAMP" "$TOOL_NAME" "$IS_INTERRUPT" "$ERROR_MSG" \
    >> .iocane/tool-failure.log

# Don't emit corrective feedback for user interrupts -- the user knows what happened
if [ "$IS_INTERRUPT" = "true" ]; then
    exit 0
fi

# Emit corrective feedback for Claude
printf 'Tool failure: %s failed -- %s\nDo not retry the same call without diagnosing the root cause.\n' \
    "$TOOL_NAME" "$ERROR_MSG"

exit 0

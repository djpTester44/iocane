#!/usr/bin/env bash
# PostToolUse hook: Bash
# Captures non-zero exit codes from Bash tool calls made by headless sub-agents.
# Appends a structured failure record to .iocane/escalation.log and writes
# .iocane/escalation.flag to signal the orchestrator.
#
# SCOPING: Only fires when IOCANE_SUBAGENT=1 is set in the environment.
# dispatch-agents.sh sets this variable before invoking each `claude -p` sub-agent.
# Interactive sessions never set it, so this hook is a no-op in plan mode.
#
# NOTE: Designed to run from a generated project root.
# This script is a harness template artifact.

# --- Guard: only active inside a sub-agent invocation ---
if [ "${IOCANE_SUBAGENT:-0}" != "1" ]; then
    exit 0
fi

INPUT=$(cat)

# --- Extract all fields in a single Python call ---
# NUL-delimited to survive newlines in command/stderr values.
# On any parse failure the raw payload is written so there is always
# something useful in the log.
PARSED=$(printf '%s' "$INPUT" | uv run rtk python -c "
import sys, json, os

raw = sys.stdin.read()
NUL = chr(0)
try:
    d = json.loads(raw)
    resp = d.get('tool_response', {})
    code = resp.get('exit_code', d.get('exit_code', 'UNKNOWN'))
    tool = d.get('tool_name', 'Bash')
    cmd  = d.get('tool_input', {}).get('command', '(unknown command)')
    err  = resp.get('stderr', '') or resp.get('output', '') or ''
    print(str(code) + NUL + tool + NUL + cmd[:500] + NUL + err[:3000].strip())
except Exception as e:
    print('PARSE_ERROR' + NUL + 'Bash' + NUL + '(parse failed: ' + str(e) + ')' + NUL + raw[:2000])
" 2>/dev/null || printf 'EXEC_ERROR\0Bash\0(uv run rtk python failed in hook)\0%s' "$INPUT")

EXIT_CODE=$(printf '%s' "$PARSED" | cut -d$'\0' -f1)
TOOL_NAME=$(printf '%s' "$PARSED" | cut -d$'\0' -f2)
COMMAND=$(printf '%s'   "$PARSED" | cut -d$'\0' -f3)
STDERR_SNIPPET=$(printf '%s' "$PARSED" | cut -d$'\0' -f4-)

[ -z "$EXIT_CODE" ] && EXIT_CODE="UNKNOWN"
[ -z "$TOOL_NAME" ] && TOOL_NAME="Bash"
[ -z "$COMMAND"   ] && COMMAND="(unknown command)"

# --- Only act on non-zero exits ---
if [ "$EXIT_CODE" -eq 0 ] 2>/dev/null; then
    exit 0
fi
# UNKNOWN / PARSE_ERROR / EXEC_ERROR cannot be compared numerically — treat as non-zero and log it

# CP-ID is injected by dispatch-agents.sh into the sub-agent environment
CP_ID="${IOCANE_CP_ID:-unknown}"
ATTEMPT="${IOCANE_ATTEMPT:-1}"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date +"%Y-%m-%dT%H:%M:%SZ")

# --- Write to parent repo .iocane/, not the worktree ---
# IOCANE_REPO_ROOT is exported by dispatch-agents.sh so the escalation
# log and flag land in the same place session-start.sh reads them from.
PARENT_ROOT="${IOCANE_REPO_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null)}"
mkdir -p "$PARENT_ROOT/.iocane"

# --- Dump raw payload for schema inspection on every invocation ---
printf '%s' "$INPUT" > "$PARENT_ROOT/.iocane/hook-debug-last-payload.json"

LOG_FILE="$PARENT_ROOT/.iocane/escalation.log"
FLAG_FILE="$PARENT_ROOT/.iocane/escalation.flag"
DEBUG_LOG="$PARENT_ROOT/.iocane/hook-debug.log"

# --- Route non-numeric / non-positive exit codes to debug log only ---
if ! printf '%s' "$EXIT_CODE" | grep -qE '^[1-9][0-9]*$'; then
    printf '%s exit_code=%s tool=%s command=%s\n' "$TIMESTAMP" "$EXIT_CODE" "$TOOL_NAME" "$COMMAND" >> "$DEBUG_LOG"
    exit 0
fi

# --- Append structured failure record (append-only, never truncated) ---
cat >> "$LOG_FILE" << EOF
---
timestamp: $TIMESTAMP
cp_id: $CP_ID
attempt: $ATTEMPT
tool: $TOOL_NAME
exit_code: $EXIT_CODE
full_log: ${IOCANE_LOG_FILE:-unknown}
command: $COMMAND
error_summary: |
$(printf '%s' "$STDERR_SNIPPET" | sed 's/^/  /')
EOF

# --- Write sentinel flag only when escalation log received a real entry ---
echo "$TIMESTAMP" > "$FLAG_FILE"

exit 0

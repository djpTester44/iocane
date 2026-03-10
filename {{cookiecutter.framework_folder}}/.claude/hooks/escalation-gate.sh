#!/usr/bin/env bash
# PostToolUse hook: Bash
# Captures non-zero exit codes from Bash tool calls made by headless sub-agents.
# Appends a structured failure record to .iocane/escalation.log and writes
# .iocane/escalation.flag to signal the orchestrator.
#
# SCOPING: Only fires when IOCANE_SUBAGENT=1 is set in the environment.
# run.sh sets this variable before invoking each `claude -p` sub-agent.
# Interactive sessions never set it, so this hook is a no-op in plan mode.
#
# NOTE: Designed to run from a generated project root.
# This script is a harness template artifact.

# --- Guard: only active inside a sub-agent invocation ---
if [ "${IOCANE_SUBAGENT:-0}" != "1" ]; then
    exit 0
fi

INPUT=$(cat)

# --- Extract exit_code and tool metadata from hook payload ---
EXIT_CODE=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    # PostToolUse payload shape: {tool_name, tool_input, tool_response}
    # exit_code may be in tool_response or at top level depending on Claude Code version
    resp = d.get('tool_response', {})
    code = resp.get('exit_code', d.get('exit_code', None))
    print(code if code is not None else '')
except Exception:
    print('')
" 2>/dev/null || echo "")

if [ -z "$EXIT_CODE" ] || [ "$EXIT_CODE" = "null" ]; then
    echo "[escalation-gate] WARNING: could not extract exit code from payload. Known variance: payload shape may differ by Claude Code version. Logging as exit_code=UNKNOWN." >&2
    EXIT_CODE="UNKNOWN"
fi

# --- Only act on non-zero exits ---
if [ "$EXIT_CODE" -eq 0 ] 2>/dev/null; then
    exit 0
fi
# UNKNOWN cannot be compared numerically — treat as non-zero and log it

# --- Extract useful fields for the log record ---
TOOL_NAME=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('tool_name', 'Bash'))
except Exception:
    print('Bash')
" 2>/dev/null || echo "Bash")

COMMAND=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    cmd = d.get('tool_input', {}).get('command', '')
    # Truncate long commands for log readability
    print(cmd[:200] + ('...' if len(cmd) > 200 else ''))
except Exception:
    print('(unknown command)')
" 2>/dev/null || echo "(unknown command)")

STDERR_SNIPPET=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    resp = d.get('tool_response', {})
    # Capture first 300 chars of stderr for the error summary
    err = resp.get('stderr', '') or resp.get('output', '')
    print(err[:300].strip())
except Exception:
    print('')
" 2>/dev/null || echo "")

# CP-ID is injected by run.sh into the sub-agent environment
CP_ID="${IOCANE_CP_ID:-unknown}"
ATTEMPT="${IOCANE_ATTEMPT:-1}"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date +"%Y-%m-%dT%H:%M:%SZ")

# --- Ensure .iocane/ directory exists ---
mkdir -p .iocane

LOG_FILE=".iocane/escalation.log"
FLAG_FILE=".iocane/escalation.flag"

# --- Append structured failure record (append-only, never truncated) ---
cat >> "$LOG_FILE" << EOF
---
timestamp: $TIMESTAMP
cp_id: $CP_ID
attempt: $ATTEMPT
tool: $TOOL_NAME
exit_code: $EXIT_CODE
command: $COMMAND
error_summary: |
$(echo "$STDERR_SNIPPET" | sed 's/^/  /')
EOF

# --- Write sentinel flag (orchestrator and session-start.sh read this only) ---
# The flag is a simple marker file. Its content is not read by the harness.
# The human clears it manually after reviewing escalation.log.
echo "$TIMESTAMP" > "$FLAG_FILE"

exit 0

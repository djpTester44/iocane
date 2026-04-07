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
# --- Parse payload with Python; output one field per line for Git Bash compat ---
PARSED=$(printf '%s' "$INPUT" | uv run python -c "
import sys, json

raw = sys.stdin.read()
SEP = '<<<FIELD>>>'
try:
    d = json.loads(raw)
    resp = d.get('tool_response', {})
    code = resp.get('exit_code', d.get('exit_code', None))
    tool = d.get('tool_name', 'Bash')
    cmd  = d.get('tool_input', {}).get('command', '(unknown command)')
    err  = resp.get('stderr', '') or resp.get('output', '') or ''
    if code is None:
        # exit_code absent from payload = normal successful command; skip silently
        print('SKIP')
        sys.exit(0)
    print(str(code) + SEP + tool + SEP + cmd[:500] + SEP + err[:3000].strip())
except Exception as e:
    print('PARSE_ERROR' + SEP + 'Bash' + SEP + '(parse failed: ' + str(e) + ')' + SEP + raw[:2000])
" 2>/dev/null || echo "EXEC_ERROR<<<FIELD>>>Bash<<<FIELD>>>(uv run python failed in hook)<<<FIELD>>>$INPUT")

# --- Silent skip when exit_code was absent (normal for successful commands) ---
if [ "$PARSED" = "SKIP" ]; then
    exit 0
fi

EXIT_CODE=$(printf '%s' "$PARSED" | awk -F'<<<FIELD>>>' '{print $1}')
TOOL_NAME=$(printf '%s' "$PARSED" | awk -F'<<<FIELD>>>' '{print $2}')
COMMAND=$(printf '%s'   "$PARSED" | awk -F'<<<FIELD>>>' '{print $3}')
STDERR_SNIPPET=$(printf '%s' "$PARSED" | awk -F'<<<FIELD>>>' '{for(i=4;i<=NF;i++){printf "%s",$i;if(i<NF)printf "<<<FIELD>>>"}}')

[ -z "$EXIT_CODE" ] && EXIT_CODE="UNKNOWN"
[ -z "$TOOL_NAME" ] && TOOL_NAME="Bash"
[ -z "$COMMAND"   ] && COMMAND="(unknown command)"

# --- Only act on non-zero exits ---
if [ "$EXIT_CODE" -eq 0 ] 2>/dev/null; then
    exit 0
fi
# PARSE_ERROR / EXEC_ERROR cannot be compared numerically — treat as non-zero and log it

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

# --- Route non-numeric exit codes to debug log only ---
# PARSE_ERROR / EXEC_ERROR = hook infrastructure problem.
# Written to hook-debug.log but never trigger escalation.flag.
# UNKNOWN (absent exit_code) is already handled above via SKIP.
if ! printf '%s' "$EXIT_CODE" | grep -qE '^[1-9][0-9]*$'; then
    printf '%s exit_code=%s tool=%s command=%s detail=%s\n' "$TIMESTAMP" "$EXIT_CODE" "$TOOL_NAME" "$COMMAND" "$STDERR_SNIPPET" >> "$DEBUG_LOG"
    exit 0
fi

# --- Allowlist: benign exit-code-1 commands ---
# grep/rg return 1 for "no match", test/[ return 1 for "false",
# diff returns 1 for "files differ". rtk variants included because
# rtk-enforce.sh requires the prefix in sub-agent contexts.
if [ "$EXIT_CODE" -eq 1 ]; then
    case "$COMMAND" in
        grep\ *|egrep\ *|fgrep\ *|rg\ *|rtk\ grep\ *|test\ *|\[\ *|diff\ *|git\ diff*|rtk\ git\ diff*)
            exit 0
            ;;
    esac
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

# --- Set escalation in workflow state ---
# The state gate reads this field and blocks implementation writes.
STATE_FILE="$PARENT_ROOT/.iocane/workflow-state.json"
if [ -f "$STATE_FILE" ]; then
    # Merge escalation:true into existing state (preserve next/trigger)
    EXISTING_NEXT=$(grep -o '"next":"[^"]*"' "$STATE_FILE" | cut -d'"' -f4)
    EXISTING_TRIGGER=$(grep -o '"trigger":"[^"]*"' "$STATE_FILE" | cut -d'"' -f4)
    printf '{"next":"%s","trigger":"%s","escalation":true,"timestamp":"%s"}\n' \
        "${EXISTING_NEXT:-unknown}" "${EXISTING_TRIGGER:-escalation.flag written}" "$TIMESTAMP" \
        > "$STATE_FILE"
else
    printf '{"next":"unknown","trigger":"escalation.flag written","escalation":true,"timestamp":"%s"}\n' \
        "$TIMESTAMP" > "$STATE_FILE"
fi

exit 0

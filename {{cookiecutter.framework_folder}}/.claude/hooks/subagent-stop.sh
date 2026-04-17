#!/usr/bin/env bash
# SubagentStop hook: log sub-agent exit and guard against continuation loops.
#
# Input fields:
#   agent_transcript_path  -- path to the sub-agent's transcript file
#   last_assistant_message -- final message from the sub-agent
#   agent_type             -- type of sub-agent (e.g., Explore, Plan, io-execute)
#   stop_hook_active       -- true when already continuing from a stop hook (loop guard)
#
# Output: none (logging only).
#
# Source: hooks.md:1249-1251 (Claude Code docs -- SubagentStop input schema)

set -euo pipefail

INPUT=$(cat)
# CWD-scoped intentionally: subagent-stop artifacts are per-session
# debug dumps with no cross-session reader. Parent-scoping would
# collide across concurrent sub-agents writing the same log.
mkdir -p .iocane

# Guard: stop_hook_active prevents infinite continuation loop
STOP_HOOK_ACTIVE=$(printf '%s' "$INPUT" | uv run python -c "
import sys, json
raw = sys.stdin.read()
d = json.loads(raw) if raw.strip() else {}
print(str(d.get('stop_hook_active', False)).lower())
" 2>/dev/null || echo "false")

if [ "$STOP_HOOK_ACTIVE" = "true" ]; then
    exit 0
fi

# Parse agent metadata in a single Python call
PARSED=$(printf '%s' "$INPUT" | uv run python -c "
import sys, json
raw = sys.stdin.read()
d = json.loads(raw) if raw.strip() else {}
print(d.get('agent_type', 'unknown'))
print(d.get('agent_transcript_path', ''))
" 2>/dev/null || printf 'unknown\n\n')

AGENT_TYPE=$(echo "$PARSED" | sed -n '1p')
TRANSCRIPT_PATH=$(echo "$PARSED" | sed -n '2p')

# Log sub-agent exit
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
printf '%s agent_type=%s transcript=%s\n' "$TIMESTAMP" "$AGENT_TYPE" "$TRANSCRIPT_PATH" \
    >> .iocane/subagent-stop.log

# Dump raw payload for schema debugging
printf '%s' "$INPUT" > .iocane/subagent-stop-payload.json

exit 0

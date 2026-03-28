#!/usr/bin/env bash
# Stop hook: end-of-turn gate that blocks when unresolved escalation is present.
#
# Input fields:
#   last_assistant_message -- Claude's final response for this turn
#   stop_hook_active       -- true if already continuing from a stop hook (loop guard)
#
# Output: JSON with decision 'block' + reason to force continuation, or exits 0 to allow stop.
#
# Source: hooks.md:1387-1389 (Claude Code docs -- Stop input schema)

set -euo pipefail

INPUT=$(cat)

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

# Block if escalation flag is present -- sub-agent failure requires explicit resolution
if [ -f ".iocane/escalation.flag" ]; then
    uv run python -c "
import json
print(json.dumps({
    'decision': 'block',
    'reason': (
        'Escalation flag is set. A sub-agent failed in a previous batch. '
        'Read .iocane/escalation.log and resolve before proceeding. '
        'Clear .iocane/escalation.flag after review to re-enable orchestration.'
    )
}))
"
    exit 0
fi

exit 0

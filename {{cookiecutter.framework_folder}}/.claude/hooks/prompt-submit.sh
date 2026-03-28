#!/usr/bin/env bash
# UserPromptSubmit hook: inject per-turn dynamic harness state before Claude processes a prompt.
#
# Input fields: user prompt content (varies by implementation)
#
# Output: JSON with additionalContext (injected discretely) if meaningful state exists,
# or exits 0 with no output when state is empty (no noise on quiet turns).
#
# Supplements session-start.sh orientation with dynamic state that changes between
# session open and the current turn (active task, escalation flag).
#
# Source: hooks.md:801-803 (Claude Code docs -- UserPromptSubmit input schema)

set -euo pipefail

# Only inject if meaningful state exists -- avoid adding noise on every turn
ACTIVE_TASK=""
ESCALATION_NOTE=""

if [ -f ".iocane/active-task" ]; then
    ACTIVE_TASK=$(cat .iocane/active-task 2>/dev/null || echo "")
fi

if [ -f ".iocane/escalation.flag" ]; then
    ESCALATION_NOTE="ESCALATION FLAG SET -- resolve before running dispatch-agents.sh."
fi

# Exit cleanly with no output when there is nothing to inject
if [ -z "$ACTIVE_TASK" ] && [ -z "$ESCALATION_NOTE" ]; then
    exit 0
fi

CONTEXT="${ESCALATION_NOTE:+$ESCALATION_NOTE
}${ACTIVE_TASK:+Active task: $ACTIVE_TASK}"

printf '%s' "$CONTEXT" | uv run python -c "
import sys, json
content = sys.stdin.read().strip()
if content:
    print(json.dumps({'additionalContext': content}))
"

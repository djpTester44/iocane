#!/usr/bin/env bash
# SubagentStart hook: inject harness orientation context into spawned sub-agents.
#
# Input fields:
#   agent_type -- type of sub-agent being spawned (e.g., Explore, Plan, io-execute)
#
# Output: JSON with additionalContext string injected before sub-agent begins.
# Cannot block sub-agent creation.
#
# Source: hooks.md:1215-1217 (Claude Code docs -- SubagentStart input schema)

set -euo pipefail

INPUT=$(cat)
mkdir -p .iocane

AGENT_TYPE=$(printf '%s' "$INPUT" | uv run python -c "
import sys, json
raw = sys.stdin.read()
d = json.loads(raw) if raw.strip() else {}
print(d.get('agent_type', 'unknown'))
" 2>/dev/null || echo "unknown")

# Log spawn event
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
printf '%s agent_type=%s\n' "$TIMESTAMP" "$AGENT_TYPE" >> .iocane/subagent-start.log

# Read dynamic state for injection
ACTIVE_TASK=$(cat .iocane/active-task 2>/dev/null || echo "")
SESSION_MODEL=$(cat .iocane/session-model 2>/dev/null || echo "unknown")

CONTEXT="Harness sub-agent context:
- Agent type: $AGENT_TYPE
- Session model: $SESSION_MODEL
${ACTIVE_TASK:+- Active task: $ACTIVE_TASK
}
- Scope rule: Never exceed the explicit scope of the spawning prompt.
- Rules reference: .claude/rules/
- Do not read .iocane/ or .claude/ unless the task explicitly requires it."

printf '%s' "$CONTEXT" | uv run python -c "
import sys, json
content = sys.stdin.read()
print(json.dumps({'additionalContext': content}))
"

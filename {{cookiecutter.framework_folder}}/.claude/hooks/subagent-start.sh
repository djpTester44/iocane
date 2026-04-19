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

# --- gen_protocols role-leak warning (SubagentStart parity with SessionStart) ---
# IOCANE_ROLE=gen_protocols is a single-subprocess scope set by
# /io-gen-protocols when it invokes gen_protocols.py. There is no
# spawn-gen-protocols.sh; the role is never a legitimate subagent
# dispatch mode (unlike tester / ct_author). SubagentStart cannot
# refuse the spawn (per the hook contract it only injects context),
# so warn loudly in additionalContext and log the anomaly. Honest-
# agent trust model: if the subagent sees this warning it must not
# proceed with interfaces/ writes.
ROLE_LEAK_WARNING=""
if [ "${IOCANE_ROLE:-}" = "gen_protocols" ]; then
    printf '%s role_leak=IOCANE_ROLE=gen_protocols agent_type=%s\n' \
        "$TIMESTAMP" "$AGENT_TYPE" >> .iocane/subagent-start.log
    ROLE_LEAK_WARNING="
## ROLE LEAK DETECTED

IOCANE_ROLE=gen_protocols was inherited into this sub-agent's environment.
As of the current harness, no spawn-gen-protocols.sh dispatches sub-agents
with this role, so inheritance here is suspicious unless the spawning
context is a /io-gen-protocols extension that legitimately delegates. If
you are not executing inside /io-gen-protocols, do not write into
interfaces/; halt with a structured finding naming
root_cause_layer=interfaces_codegen and re-entry /io-gen-protocols so the
human can investigate the leak source."
fi

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
- Do not read .iocane/ or .claude/ unless the task explicitly requires it.
${ROLE_LEAK_WARNING}"

printf '%s' "$CONTEXT" | uv run python -c "
import sys, json
content = sys.stdin.read()
print(json.dumps({'additionalContext': content}))
"

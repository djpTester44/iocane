#!/usr/bin/env bash
# PreCompact hook: snapshot workflow state before compaction truncates it.
#
# Input fields:
#   trigger             -- 'auto' or 'manual'
#   custom_instructions -- user-supplied compaction instructions (if any)
#
# Output: none. Compaction cannot be blocked; this hook only writes state to disk.
# State is consumed by post-compact.sh to restore orientation after compaction.
#
# Source: hooks.md:1731-1733 (Claude Code docs -- PreCompact input schema)

set -euo pipefail

INPUT=$(cat)
mkdir -p .iocane

TRIGGER=$(printf '%s' "$INPUT" | uv run python -c "
import sys, json
raw = sys.stdin.read()
d = json.loads(raw) if raw.strip() else {}
print(d.get('trigger', 'unknown'))
" 2>/dev/null || echo "unknown")

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Capture active checkpoint from plan.md before compaction discards context
PLAN_FILE="plans/plan.md"
ACTIVE_CHECKPOINT=""
PENDING_CHECKPOINTS=""

if [ -f "$PLAN_FILE" ]; then
    ACTIVE_CHECKPOINT=$(grep -E "^\*\*Status:\*\* \[~\] in-progress" "$PLAN_FILE" -B5 \
        | grep "^### CP-" | sed 's/### //' || echo "")
    if [ -z "$ACTIVE_CHECKPOINT" ]; then
        ACTIVE_CHECKPOINT=$(grep -E "^\*\*Status:\*\* \[ \] pending" "$PLAN_FILE" -B5 \
            | grep "^### CP-" | head -1 | sed 's/### //' || echo "")
    fi
    PENDING_CHECKPOINTS=$(grep -E "^\*\*Status:\*\* \[ \] pending" "$PLAN_FILE" -B5 \
        | grep "^### CP-" | sed 's/### //' | tr '\n' ',' | sed 's/,$//' || echo "")
fi

ESCALATION_FLAG=""
if [ -f ".iocane/escalation.flag" ]; then
    ESCALATION_FLAG="present"
fi

# Write state snapshot for post-compact.sh to consume
uv run python -c "
import json, sys
state = {
    'timestamp': sys.argv[1],
    'trigger': sys.argv[2],
    'active_checkpoint': sys.argv[3],
    'pending_checkpoints': sys.argv[4],
    'escalation_flag': sys.argv[5],
}
open('.iocane/pre-compact-state.json', 'w').write(json.dumps(state, indent=2))
" "$TIMESTAMP" "$TRIGGER" "$ACTIVE_CHECKPOINT" "$PENDING_CHECKPOINTS" "$ESCALATION_FLAG"

printf '%s trigger=%s active=%s\n' "$TIMESTAMP" "$TRIGGER" "$ACTIVE_CHECKPOINT" \
    >> .iocane/compact.log

exit 0

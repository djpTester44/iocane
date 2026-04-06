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

# Capture active checkpoint from plan.yaml before compaction discards context
PLAN_FILE="plans/plan.yaml"
ACTIVE_CHECKPOINT=""
PENDING_CHECKPOINTS=""

if [ -f "$PLAN_FILE" ]; then
    eval "$(uv run python -c "
import sys
sys.path.insert(0, '.claude/scripts')
from plan_parser import load_plan, pending_checkpoints, in_progress_checkpoints
plan = load_plan('plans/plan.yaml')
pend = pending_checkpoints(plan)
prog = in_progress_checkpoints(plan)
active = ''
if prog:
    active = f'{prog[0].id}: {prog[0].title}'
elif pend:
    active = f'{pend[0].id}: {pend[0].title}'
pend_str = ','.join(cp.id for cp in pend)
print(f'ACTIVE_CHECKPOINT=\"{active}\"')
print(f'PENDING_CHECKPOINTS=\"{pend_str}\"')
" 2>/dev/null)" || {
        ACTIVE_CHECKPOINT=""
        PENDING_CHECKPOINTS=""
    }
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

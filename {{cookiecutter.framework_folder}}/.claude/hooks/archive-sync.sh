#!/usr/bin/env bash
# PostToolUse hook: Edit | Write
# Self-healing guard: if the agent writes Remediated: annotations directly to
# plans/backlog.yaml without running archive-approved.sh, this hook detects the
# drift and runs archive-approved.sh to sync plan.yaml.
#
# NOTE: Designed to run from the project root.
# This script is a harness template artifact.

INPUT=$(cat)

FILE_PATH=$(uv run python -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('tool_input', {}).get('file_path', ''))
except Exception:
    print('')
" <<< "$INPUT")

if [ -z "$FILE_PATH" ]; then
    exit 0
fi

MATCH=$(FILE_PATH="$FILE_PATH" uv run python -c "
import os, sys
p = os.path.normpath(os.environ['FILE_PATH']).replace('\\\\', '/')
print('yes' if p.endswith('plans/backlog.yaml') else 'no')
")

if [ "$MATCH" != "yes" ] || [ ! -f "plans/backlog.yaml" ] || [ ! -f "plans/plan.yaml" ]; then
    exit 0
fi

# Find CP-IDs with Remediated: annotations in backlog.yaml where plan.yaml still
# shows pending status — these are stale due to bypassing archive-approved.sh.
STALE_CPS=$(uv run python -c "
import sys
sys.path.insert(0, '.claude/scripts')
from backlog_parser import load_backlog
from plan_parser import load_plan, find_checkpoint
from schemas import CheckpointStatus

backlog = load_backlog('plans/backlog.yaml')
plan = load_plan('plans/plan.yaml')

stale = []
seen = set()
for item in backlog.items:
    for ann in item.annotations:
        if ann.type == 'Remediated' and ann.value not in seen:
            cp_id = ann.value
            seen.add(cp_id)
            cp = find_checkpoint(plan, cp_id)
            if cp and cp.status == CheckpointStatus.PENDING:
                stale.append(cp_id)

print(' '.join(stale))
")

if [ -z "$STALE_CPS" ]; then
    exit 0
fi

CORRECTED=()
for CP_ID in $STALE_CPS; do
    if bash .claude/scripts/archive-approved.sh "$CP_ID" > /dev/null 2>&1; then
        CORRECTED+=("$CP_ID")
    fi
done

if [ ${#CORRECTED[@]} -gt 0 ]; then
    JOINED="${CORRECTED[*]}"
    MSG="archive-sync: ran archive-approved.sh for ${JOINED// /, } (plan.yaml was stale)"
    echo "{\"type\": \"systemPrompt\", \"content\": \"$MSG\"}"
fi

# --- State derivation: check if pending CPs remain after archive sync ---
if [ -f "plans/plan.yaml" ]; then
    PENDING_COUNT=$(uv run python -c "
import sys
sys.path.insert(0, '.claude/scripts')
from plan_parser import load_plan, pending_checkpoints
plan = load_plan('plans/plan.yaml')
print(len(pending_checkpoints(plan)))
" 2>/dev/null) || PENDING_COUNT=""

    if [ -n "$PENDING_COUNT" ]; then
        TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date +"%Y-%m-%dT%H:%M:%SZ")
        mkdir -p .iocane
        if [ "$PENDING_COUNT" -gt 0 ] 2>/dev/null; then
            printf '{"next":"io-plan-batch","trigger":"archive-sync (pending CPs: %s)","timestamp":"%s"}\n' \
                "$PENDING_COUNT" "$TIMESTAMP" > .iocane/workflow-state.json
        else
            printf '{"next":"closeout","trigger":"archive-sync (all CPs complete)","timestamp":"%s"}\n' \
                "$TIMESTAMP" > .iocane/workflow-state.json
        fi
    fi
fi

exit 0

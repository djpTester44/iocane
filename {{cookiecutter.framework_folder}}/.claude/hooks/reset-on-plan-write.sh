#!/usr/bin/env bash
# PostToolUse hook: Edit | Write
# Resets the validated stamp in plans/plan.yaml after any substantive write.
#
# Exempt: if .iocane/validating sentinel file exists, the write is a stamp-only
# update (e.g. /validate-plan setting validated: true) and must NOT be reset.
# The sentinel is created before the stamp write and deleted after. It persists
# across tool calls within a session because it is shared filesystem state.
#
# Uses raw yaml.safe_load/yaml.dump -- NO Pydantic. This hook fires on every
# Edit/Write; full load_plan/save_plan is a performance hit and risks re-trigger.
#
# NOTE: Designed to run from a generated project root.
# This script is a harness template artifact.

INPUT=$(cat)

if [ -f ".iocane/validating" ]; then
    # If this write IS the validated stamp itself, the sentinel's job is done.
    # Auto-delete so the agent does not need an explicit cleanup step.
    NEW_CONTENT=$(printf '%s' "$INPUT" | uv run python -c "
import sys, json
try:
    d = json.load(sys.stdin)
    ti = d.get('tool_input', {})
    print(ti.get('new_string', '') or ti.get('content', ''))
except Exception:
    print('')
")
    if echo "$NEW_CONTENT" | grep -qE "^validated:[[:space:]]*(true|True)[[:space:]]*$"; then
        rm -f .iocane/validating
        # State derivation: validated stamp just set -> ready for batch generation
        TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date +"%Y-%m-%dT%H:%M:%SZ")
        mkdir -p .iocane
        printf '{"next":"io-plan-batch","trigger":"plan.yaml (validated: true)","timestamp":"%s"}\n' \
            "$TIMESTAMP" > .iocane/workflow-state.json
    fi
    exit 0
fi

FILE_PATH=$(printf '%s' "$INPUT" | uv run python -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('tool_input', {}).get('file_path', ''))
except Exception:
    print('')
")

if [ -z "$FILE_PATH" ]; then
    exit 0
fi

MATCH=$(FILE_PATH="$FILE_PATH" uv run python -c "
import os, sys
p = os.path.normpath(os.environ['FILE_PATH']).replace('\\\\', '/')
print('yes' if p.endswith('plans/plan.yaml') else 'no')
")

if [ "$MATCH" = "yes" ] && [ -f "plans/plan.yaml" ]; then
    # Single python invocation: mutate the plan file AND derive post-reset
    # state. Raw yaml.safe_load (not Pydantic) per the header-comment
    # performance guard; the state-derivation read is piggybacked on the
    # mutation read, so there is no extra file open.
    STATE=$(uv run python -c "
import yaml
path = 'plans/plan.yaml'
with open(path, 'r', encoding='utf-8') as f:
    data = yaml.safe_load(f) or {}
if data.get('validated') is True:
    data['validated'] = False
    data.pop('validated_date', None)
    data.pop('validated_note', None)
    with open(path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
v = 'true' if data.get('validated') is True else ''
cps = data.get('checkpoints') or []
h = 'true' if any(cp.get('status') == 'complete' for cp in cps) else ''
print(f'{v}|{h}')
" 2>/dev/null || echo "|")
    VALIDATED="${STATE%|*}"
    HAS_COMPLETE="${STATE#*|}"

    if [ -n "$HAS_COMPLETE" ]; then
        # dispatch-agents.sh just merged a CP and updated status
        NEXT="io-review"
        TRIGGER="plan.yaml (CP status: complete)"
    elif [ -n "$VALIDATED" ]; then
        # /validate-plan just stamped the plan (shouldn't reach here due to sentinel)
        NEXT="io-plan-batch"
        TRIGGER="plan.yaml (validated: true)"
    else
        # plan.yaml written or validation reset
        NEXT="validate-plan"
        TRIGGER="plan.yaml (validated: false)"
    fi

    TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date +"%Y-%m-%dT%H:%M:%SZ")
    mkdir -p .iocane
    printf '{"next":"%s","trigger":"%s","timestamp":"%s"}\n' \
        "$NEXT" "$TRIGGER" "$TIMESTAMP" > .iocane/workflow-state.json
fi

exit 0

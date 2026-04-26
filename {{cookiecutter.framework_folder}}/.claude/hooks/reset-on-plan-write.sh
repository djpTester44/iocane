#!/usr/bin/env bash
# PostToolUse hook: Edit | Write
# Resets the validated stamp in plans/plan.yaml after any substantive write.
#
# Bypass: if a capability grant covers write:plans/plan.yaml for this
# session, the write is authored (e.g. /validate-plan Step 13 setting
# validated: true). Inside the bypass, content detection drives the
# workflow-state transition toward io-plan-batch -- legitimate state-
# machine logic.
#
# Uses raw yaml.safe_load/yaml.dump -- NO Pydantic. This hook fires on every
# Edit/Write; full load_plan/save_plan is a performance hit and risks re-trigger.
#
# NOTE: Designed to run from a generated project root.
# This script is a harness template artifact.

INPUT=$(cat)

EXTRACT=$(printf '%s' "$INPUT" | uv run python -c "
import sys, json
try:
    d = json.load(sys.stdin)
except Exception:
    print('\\n\\n'); sys.exit(0)
sid = d.get('session_id', '') or ''
ti = d.get('tool_input') or {}
fp = ti.get('file_path', '') or ''
content = ti.get('new_string', '') or ti.get('content', '') or ''
print(sid)
print(fp)
print(content)
" 2>/dev/null)

SID=$(printf '%s' "$EXTRACT" | sed -n '1p')
FILE_PATH=$(printf '%s' "$EXTRACT" | sed -n '2p')
NEW_CONTENT=$(printf '%s' "$EXTRACT" | sed -n '3,$p')

if [ -n "$SID" ] && [ -n "$FILE_PATH" ]; then
    if bash .claude/scripts/capability-covers.sh "$SID" "write" "$FILE_PATH"; then
        # Authored write. If this is the validated:true stamp, drive
        # the workflow-state transition toward io-plan-batch.
        if echo "$NEW_CONTENT" | grep -qE "^validated:[[:space:]]*(true|True)[[:space:]]*$"; then
            TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date +"%Y-%m-%dT%H:%M:%SZ")
            mkdir -p .iocane
            printf '{"next":"io-plan-batch","trigger":"plan.yaml (validated: true)","timestamp":"%s"}\n' \
                "$TIMESTAMP" > .iocane/workflow-state.json
        fi
        exit 0
    fi
fi

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
    # state.
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
        NEXT="io-review"
        TRIGGER="plan.yaml (CP status: complete)"
    elif [ -n "$VALIDATED" ]; then
        NEXT="io-plan-batch"
        TRIGGER="plan.yaml (validated: true)"
    else
        NEXT="validate-plan"
        TRIGGER="plan.yaml (validated: false)"
    fi

    TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date +"%Y-%m-%dT%H:%M:%SZ")
    mkdir -p .iocane
    printf '{"next":"%s","trigger":"%s","timestamp":"%s"}\n' \
        "$NEXT" "$TRIGGER" "$TIMESTAMP" > .iocane/workflow-state.json
fi

exit 0

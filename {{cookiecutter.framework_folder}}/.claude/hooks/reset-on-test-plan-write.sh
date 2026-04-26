#!/usr/bin/env bash
# PostToolUse hook: Edit | Write
# Resets plan.yaml validated stamp after any write to plans/test-plan.yaml.
#
# Rationale: test-plan.yaml declares the behavioral invariants the Test
# Author translates into contract tests. A change to invariants can
# invalidate plan.yaml because checkpoints declare gate commands that
# run the contract tests -- if the invariant set changed, the gate is
# stale until validate-plan re-verifies test-plan completeness.
#
# Bypass: if a capability grant covers write:plans/test-plan.yaml for
# this session, the write is authored (e.g. /io-architect Step F) and
# the plan.yaml stamp must not reset.
#
# NOTE: Designed to run from a generated project root.
# This script is a harness template artifact.

INPUT=$(cat)

EXTRACT=$(printf '%s' "$INPUT" | uv run python -c "
import sys, json
try:
    d = json.load(sys.stdin)
except Exception:
    print('\\n'); sys.exit(0)
sid = d.get('session_id', '') or ''
fp = (d.get('tool_input') or {}).get('file_path', '') or ''
print(sid)
print(fp)
" 2>/dev/null)

SID=$(printf '%s' "$EXTRACT" | sed -n '1p')
FILE_PATH=$(printf '%s' "$EXTRACT" | sed -n '2p')

if [ -n "$SID" ] && [ -n "$FILE_PATH" ]; then
    if bash .claude/scripts/capability-covers.sh "$SID" "write" "$FILE_PATH"; then
        exit 0
    fi
fi

if [ -z "$FILE_PATH" ]; then
    exit 0
fi

IS_TEST_PLAN=$(FILE_PATH="$FILE_PATH" uv run python -c "
import os, re
p = os.path.normpath(os.environ['FILE_PATH']).replace('\\\\', '/')
print('yes' if re.search(r'(^|/)plans/test-plan\.yaml$', p) else 'no')
")

if [ "$IS_TEST_PLAN" = "yes" ]; then
    if [ -f "plans/plan.yaml" ]; then
        uv run python -c "
import yaml
path = 'plans/plan.yaml'
with open(path, 'r', encoding='utf-8') as f:
    data = yaml.safe_load(f)
if data and data.get('validated') is True:
    data['validated'] = False
    data.pop('validated_date', None)
    data.pop('validated_note', None)
    with open(path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
"
    fi
fi

exit 0

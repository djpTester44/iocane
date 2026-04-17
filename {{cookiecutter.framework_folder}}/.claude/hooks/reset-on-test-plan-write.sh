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
# Exempt: if .iocane/validating sentinel file exists, the write originates
# from /io-architect or another validating workflow that manages stamps
# explicitly.
#
# NOTE: Designed to run from a generated project root.
# This script is a harness template artifact.

if bash .claude/scripts/check-validating-sentinel.sh; then
    exit 0
fi

INPUT=$(cat)

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

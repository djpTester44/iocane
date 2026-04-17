#!/usr/bin/env bash
# PostToolUse hook: Edit | Write
# Resets plan.yaml and test-plan.yaml validated stamps after any write
# to plans/symbols.yaml.
#
# Rationale: symbols.yaml declares every cross-CP identifier. A change
# to a symbol name, env var, type, fixture, or error message invalidates:
#   - plan.yaml: CPs that reference the renamed/retyped symbol may no
#     longer be coherent
#   - test-plan.yaml: invariants whose pass_criteria reference the symbol
#     may no longer be enforceable as written
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

IS_SYMBOLS=$(FILE_PATH="$FILE_PATH" uv run python -c "
import os, re
p = os.path.normpath(os.environ['FILE_PATH']).replace('\\\\', '/')
print('yes' if re.search(r'(^|/)plans/symbols\.yaml$', p) else 'no')
")

if [ "$IS_SYMBOLS" = "yes" ]; then
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
    if [ -f "plans/test-plan.yaml" ]; then
        uv run python -c "
import yaml
path = 'plans/test-plan.yaml'
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

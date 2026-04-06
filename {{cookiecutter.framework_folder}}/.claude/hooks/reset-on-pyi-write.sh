#!/usr/bin/env bash
# PostToolUse hook: Edit | Write
# Resets both the project-spec.md Approved stamp and plan.yaml validated stamp
# after any write to an interfaces/*.pyi contract file.
#
# Rationale: .pyi changes are binding contract changes. Both the architecture
# approval and the plan validation are invalidated because:
#   - project-spec.md: the approved CRC cards may no longer match the contracts
#   - plan.yaml: checkpoints that depend on the old contract signatures are stale
#
# Exempt: if .iocane/validating sentinel file exists, the write originates from
# /io-architect or another validating workflow that manages stamps explicitly.
# The sentinel is created before the first write and deleted after the last write.
# It persists across tool calls within a session because it is shared filesystem state.
#
# NOTE: Designed to run from a generated project root.
# This script is a harness template artifact.

if [ -f ".iocane/validating" ]; then
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

IS_PYI=$(FILE_PATH="$FILE_PATH" uv run python -c "
import os, sys, re
p = os.path.normpath(os.environ['FILE_PATH']).replace('\\\\', '/')
# Match interfaces/*.pyi (any depth under an 'interfaces' directory)
print('yes' if re.search(r'(^|/)interfaces/[^/]+\.pyi$', p) else 'no')
")

if [ "$IS_PYI" = "yes" ]; then
    if [ -f "plans/project-spec.md" ]; then
        sed -i 's/\*\*Approved:\*\* True/\*\*Approved:\*\* False/g' "plans/project-spec.md"
    fi
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

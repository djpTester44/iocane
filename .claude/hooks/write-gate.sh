#!/usr/bin/env bash
# PreToolUse hook: Edit | Write
# Blocks writes to files outside the active task's context_files.
#
# NOTE: Designed to run from a generated project root where plans/ and src/ exist.
# This script is a harness template artifact and will not function correctly
# when invoked from the iocane harness repo itself.

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | uv run python -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('tool_input', {}).get('file_path', ''))
except Exception:
    print('')
")

# No file path extracted — let the tool proceed.
if [ -z "$FILE_PATH" ]; then
    exit 0
fi

# No tasks.json — not in an execution loop, allow freely.
if [ ! -f "plans/tasks.json" ]; then
    exit 0
fi

RESULT=$(uv run python -c "
import json, os, sys

file_path = '''$FILE_PATH'''

try:
    with open('plans/tasks.json') as f:
        data = json.load(f)
except Exception:
    print('ALLOW')
    sys.exit(0)

task_list = data if isinstance(data, list) else data.get('tasks', [])

pending = next((t for t in task_list if t.get('status') == 'pending'), None)
if pending is None:
    print('ALLOW')
    sys.exit(0)

context_files = pending.get('context_files', [])
task_id = pending.get('id', pending.get('task_id', 'unknown'))

def normalize(p):
    return os.path.normpath(p).replace('\\\\', '/')

norm_target = normalize(file_path)
for cf in context_files:
    norm_cf = normalize(cf)
    if norm_target == norm_cf or norm_target.endswith('/' + norm_cf) or norm_cf.endswith('/' + norm_target):
        print('ALLOW')
        sys.exit(0)

print('BLOCKED:' + task_id)
")

if [[ "$RESULT" == BLOCKED:* ]]; then
    TASK_ID="${RESULT#BLOCKED:}"
    echo "BLOCKED: $FILE_PATH is not in context_files for task $TASK_ID. Update tasks.json or run /io-handoff."
    exit 2
fi

exit 0

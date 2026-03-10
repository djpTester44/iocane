#!/usr/bin/env bash
# PreToolUse hook: Edit | Write
# Blocks writes to files outside the active task's write_targets.
#
# v2: reads write_targets from plans/tasks/[CP-ID].md (three-tier format).
# v1 fallback: if plans/tasks/ does not exist, falls back to plans/tasks.json
#              for backward compatibility with pre-migration projects.
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

# -----------------------------------------------------------------------
# PATH RESOLUTION: v2 (tasks/ directory) or v1 (tasks.json) or free pass
# -----------------------------------------------------------------------

TASKS_DIR="plans/tasks"
TASKS_JSON="plans/tasks.json"

# --- v2: tasks/ directory present — use CP-ID.md format ---
if [ -d "$TASKS_DIR" ]; then

    RESULT=$(uv run python -c "
import os, sys, re

file_path = '''$FILE_PATH'''
tasks_dir = '$TASKS_DIR'

def normalize(p):
    return os.path.normpath(p).replace('\\\\', '/')

# Identify the active CP-ID: first CP-ID.md with no matching CP-ID.status
active_cp_id = None
try:
    def cp_sort_key(f):
        m = re.search(r'(\d+)', f)
        return int(m.group(1)) if m else 0

    md_files = sorted(
        (f for f in os.listdir(tasks_dir)
        if f.endswith('.md') and not f.startswith('.')),
        key=cp_sort_key
    )
    for md_file in md_files:
        cp_id = md_file[:-3]  # strip .md
        status_path = os.path.join(tasks_dir, cp_id + '.status')
        if not os.path.exists(status_path):
            active_cp_id = cp_id
            break
except Exception:
    pass

if active_cp_id is None:
    # All checkpoints have status files — not in an active execution window.
    print('ALLOW')
    sys.exit(0)

# Parse write_targets from the active CP-ID.md
task_file = os.path.join(tasks_dir, active_cp_id + '.md')
write_targets = []
try:
    with open(task_file) as f:
        content = f.read()
    # Find the ## Write Targets section and extract bullet list entries
    section_match = re.search(
        r'##\s+Write Targets\s*\n(.*?)(?=\n##|\Z)',
        content,
        re.DOTALL | re.IGNORECASE
    )
    if section_match:
        section = section_match.group(1)
        for line in section.splitlines():
            line = line.strip()
            # Match lines like: - \`path/to/file.py\` or - path/to/file.py
            m = re.match(r'^-\s+\`?([^\`\s]+)\`?', line)
            if m:
                write_targets.append(m.group(1))
except Exception:
    pass

if not write_targets:
    # Task is command-only or write_targets section is empty — allow freely.
    print('ALLOW')
    sys.exit(0)

norm_target = normalize(file_path)
for wt in write_targets:
    norm_wt = normalize(wt)
    if norm_target == norm_wt or norm_target.endswith('/' + norm_wt) or norm_wt.endswith('/' + norm_target):
        print('ALLOW')
        sys.exit(0)

print('BLOCKED:' + active_cp_id)
")

    if [[ "$RESULT" == BLOCKED:* ]]; then
        CP_ID="${RESULT#BLOCKED:}"
        echo "BLOCKED: $FILE_PATH is not in write_targets for checkpoint $CP_ID. Update plans/tasks/$CP_ID.md or run /io-orchestrate to regenerate."
        exit 2
    fi

    exit 0
fi

# --- v1 fallback: tasks.json present ---
if [ -f "$TASKS_JSON" ]; then

    RESULT=$(uv run python -c "
import json, os, sys

file_path = '''$FILE_PATH'''

try:
    with open('$TASKS_JSON') as f:
        data = json.load(f)
except Exception:
    print('ALLOW')
    sys.exit(0)

task_list = data if isinstance(data, list) else data.get('tasks', [])

pending = next((t for t in task_list if t.get('status') == 'pending'), None)
if pending is None:
    print('ALLOW')
    sys.exit(0)

write_targets = pending.get('write_targets', [])
task_id = pending.get('id', pending.get('task_id', 'unknown'))

if not write_targets:
    print('ALLOW')
    sys.exit(0)

def normalize(p):
    return os.path.normpath(p).replace('\\\\', '/')

norm_target = normalize(file_path)
for wt in write_targets:
    norm_wt = normalize(wt)
    if norm_target == norm_wt or norm_target.endswith('/' + norm_wt) or norm_wt.endswith('/' + norm_target):
        print('ALLOW')
        sys.exit(0)

print('BLOCKED:' + task_id)
")

    if [[ "$RESULT" == BLOCKED:* ]]; then
        TASK_ID="${RESULT#BLOCKED:}"
        echo "BLOCKED: $FILE_PATH is not in write_targets for task $TASK_ID. Update tasks.json or run /io-orchestrate."
        exit 2
    fi

    exit 0
fi

# --- Neither tasks/ nor tasks.json present: not in execution mode, allow freely ---
exit 0
#!/usr/bin/env bash
# PreToolUse hook: Edit | Write
# Blocks writes to files outside the active task's write_targets.
#
# v2: reads write_targets from plans/tasks/[CP-ID].yaml (YAML with Pydantic validation).
# v1 fallback: if plans/tasks/ does not exist, falls back to plans/tasks.json
#              for backward compatibility with pre-migration projects.
#
# NOTE: Designed to run from a generated project root where plans/ and src/ exist.
# This script is a harness template artifact and will not function correctly
# when invoked from the iocane harness repo itself.

INPUT=$(cat)

# Extract file_path, absolute CWD, and absolute file path in a single Python call.
# Output is NUL-delimited: FILE_PATH\0ABS_CWD\0ABS_FILE
PARSED=$(printf '%s' "$INPUT" | uv run python -c "
import sys, json, os

raw = sys.stdin.read()
NUL = chr(0)
try:
    d = json.loads(raw)
    fp = d.get('tool_input', {}).get('file_path', '')
except Exception:
    fp = ''

cwd = os.path.normpath(os.getcwd()).replace('\\\\', '/')
if fp:
    abs_fp = os.path.normpath(os.path.abspath(fp)).replace('\\\\', '/')
else:
    abs_fp = ''

print(fp + NUL + cwd + NUL + abs_fp, end='')
" 2>/dev/null || printf '\0\0')

FILE_PATH=$(printf '%s' "$PARSED" | cut -d$'\0' -f1)
ABS_CWD=$(printf '%s' "$PARSED"  | cut -d$'\0' -f2)
ABS_FILE=$(printf '%s' "$PARSED" | cut -d$'\0' -f3)

# No file path extracted — let the tool proceed.
if [ -z "$FILE_PATH" ]; then
    exit 0
fi

# Exempt interactive sessions: only haiku sub-agents are gated.
SESSION_MODEL=$(cat .iocane/session-model 2>/dev/null || echo "")
if [[ "$SESSION_MODEL" != *"haiku"* ]]; then
    exit 0
fi

# Enforce worktree boundary: block any write that escapes the current working directory.
if [ -n "$ABS_FILE" ] && [[ "$ABS_FILE" != "$ABS_CWD"* ]]; then
    echo "BLOCKED: $FILE_PATH is outside the worktree boundary ($ABS_CWD). Sub-agents must not write to the parent repository." >&2
    exit 2
fi

# -----------------------------------------------------------------------
# PATH RESOLUTION: v2 (tasks/ directory) or free pass
# -----------------------------------------------------------------------

TASKS_DIR="plans/tasks"

# --- Always allow workflow control files ---
# .status/.exit: written by sub-agents (Tier 3) to signal completion.
# .yaml: written by /io-plan-batch (Tier 2 orchestration) to generate task files.
# write-gate must never block these.
if echo "$FILE_PATH" | grep -qE '(plans/tasks/CP-[^/]+\.(status|exit|yaml|eval\.json)|\.iocane/(escalation\.log|escalation\.flag|validating))'; then
    exit 0
fi

# --- v2: tasks/ directory present — use CP-ID.yaml format ---
if [ -d "$TASKS_DIR" ]; then

    RESULT=$(FILE_PATH="$FILE_PATH" TASKS_DIR="$TASKS_DIR" uv run python -c "
import os, sys, re

file_path = os.environ.get('FILE_PATH', '')
tasks_dir = os.environ.get('TASKS_DIR', 'plans/tasks')

def normalize(p):
    return os.path.normpath(p).replace('\\\\', '/')

# Identify the active CP-ID: first CP-ID.yaml with no matching CP-ID.status
active_cp_id = None
try:
    def cp_sort_key(f):
        m = re.search(r'(\d+)', f)
        return int(m.group(1)) if m else 0

    yaml_files = sorted(
        (f for f in os.listdir(tasks_dir)
        if f.endswith('.yaml') and not f.startswith('.')),
        key=cp_sort_key
    )
    for yaml_file in yaml_files:
        cp_id = yaml_file[:-5]  # strip .yaml
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

# Parse write_targets from the active CP-ID.yaml via task_parser
task_path = os.path.join(tasks_dir, active_cp_id + '.yaml')
write_targets = []
try:
    sys.path.insert(0, '.claude/scripts')
    from task_parser import load_task
    task = load_task(task_path)
    write_targets = list(task.write_targets)
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
        echo "BLOCKED: $FILE_PATH is not in write_targets for checkpoint $CP_ID. Update plans/tasks/$CP_ID.yaml or run /io-plan-batch to regenerate. Sub-agents may only write within their worktree." >&2
        exit 2
    fi

    exit 0
fi

# --- tasks/ not present: not in execution mode, allow freely ---
exit 0
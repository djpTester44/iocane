#!/usr/bin/env bash
# PostToolUse hook: validate YAML files against Pydantic schemas after Write/Edit.
# Routes by file path to the correct parser. Exit 0 = pass, exit 2 = validation failure.

set -euo pipefail

# Extract file_path from tool input JSON (passed via $CLAUDE_TOOL_INPUT)
FILE_PATH=$(echo "$CLAUDE_TOOL_INPUT" | uv run python -c "
import sys, json
data = json.load(sys.stdin)
print(data.get('file_path', ''))
")

# Skip if no file path extracted
if [[ -z "$FILE_PATH" ]]; then
  exit 0
fi

# Route by path pattern
case "$FILE_PATH" in
  */plans/tasks/CP-*.yaml)
    uv run python -c "
import sys
sys.path.insert(0, '.claude/scripts')
from task_parser import load_task
load_task('$FILE_PATH')
" 2>&1 || { echo "YAML validation failed for $FILE_PATH" >&2; exit 2; }
    ;;
  */plans/plan.yaml)
    uv run python -c "
import sys
sys.path.insert(0, '.claude/scripts')
from plan_parser import load_plan
load_plan('$FILE_PATH')
" 2>&1 || { echo "YAML validation failed for $FILE_PATH" >&2; exit 2; }
    ;;
  */plans/backlog.yaml)
    uv run python -c "
import sys
sys.path.insert(0, '.claude/scripts')
from backlog_parser import load_backlog
load_backlog('$FILE_PATH')
" 2>&1 || { echo "YAML validation failed for $FILE_PATH" >&2; exit 2; }
    ;;
  */plans/seams.yaml)
    uv run python -c "
import sys
sys.path.insert(0, '.claude/scripts')
from seam_parser import load_seams
load_seams('$FILE_PATH')
" 2>&1 || { echo "YAML validation failed for $FILE_PATH" >&2; exit 2; }
    ;;
  *)
    # Not a schema-validated YAML file -- pass through
    exit 0
    ;;
esac

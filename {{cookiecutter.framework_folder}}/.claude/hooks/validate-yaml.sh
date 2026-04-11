#!/usr/bin/env bash
# PostToolUse hook: validate YAML files against Pydantic schemas after Write/Edit.
# Routes by file path to the correct parser. Exit 0 = pass, exit 2 = validation failure.

set -euo pipefail

# Skip if hook runtime didn't inject the tool input variable
TOOL_INPUT="${CLAUDE_TOOL_INPUT:-}"
if [[ -z "$TOOL_INPUT" ]]; then
  exit 0
fi

# Extract file_path from tool input JSON
FILE_PATH=$(echo "$TOOL_INPUT" | uv run python -c "
import sys, json
data = json.load(sys.stdin)
print(data.get('file_path', ''))
")

# Skip if no file path extracted or not a YAML file
if [[ -z "$FILE_PATH" || "$FILE_PATH" != *.yaml ]]; then
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
  */plans/component-contracts.yaml)
    uv run python -c "
import sys
sys.path.insert(0, '.claude/scripts')
from contract_parser import load_contracts
load_contracts('$FILE_PATH')
" 2>&1 || { echo "YAML validation failed for $FILE_PATH" >&2; exit 2; }
    ;;
  *)
    # Not a schema-validated YAML file -- pass through
    exit 0
    ;;
esac

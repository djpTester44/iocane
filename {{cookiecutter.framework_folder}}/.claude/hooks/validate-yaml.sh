#!/usr/bin/env bash
# PostToolUse hook: validate YAML files against Pydantic schemas after Write/Edit.
# Routes by file path to the correct parser. Exit 0 = pass, exit 2 = validation failure.
#
# Reads hook payload from stdin (matches every other Edit|Write hook in the
# harness). Earlier revisions read CLAUDE_TOOL_INPUT from the env and
# parsed `file_path` at the JSON root -- both wrong for the Claude Code
# hook protocol, which delivers the payload on stdin with file_path
# nested under tool_input.

set -uo pipefail

INPUT=$(cat)

FILE_PATH=$(printf '%s' "$INPUT" | uv run python -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('tool_input', {}).get('file_path', ''))
except Exception:
    print('')
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
  */plans/symbols.yaml)
    uv run python -c "
import sys
sys.path.insert(0, '.claude/scripts')
from symbols_parser import load_symbols
load_symbols('$FILE_PATH')
" 2>&1 || { echo "YAML validation failed for $FILE_PATH" >&2; exit 2; }
    ;;
  */plans/test-plan.yaml)
    uv run python -c "
import sys
sys.path.insert(0, '.claude/scripts')
from test_plan_parser import load_test_plan
load_test_plan('$FILE_PATH')
" 2>&1 || { echo "YAML validation failed for $FILE_PATH" >&2; exit 2; }
    ;;
  *)
    # Not a schema-validated YAML file -- pass through
    exit 0
    ;;
esac

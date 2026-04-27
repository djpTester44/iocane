#!/usr/bin/env bash
# PostToolUse hook: validate YAML files against Pydantic schemas after Write/Edit.
# Routes by file path to the correct parser. Exit 0 = pass, exit 2 = validation failure.
#
# Reads hook payload from stdin (matches every other Edit|Write hook in the
# harness). Earlier revisions read CLAUDE_TOOL_INPUT from the env and
# parsed `file_path` at the JSON root -- both wrong for the Claude Code
# hook protocol, which delivers the payload on stdin with file_path
# nested under tool_input.
#
# Validation is delegated to .claude/scripts/validate_yaml_helper.py which
# loads the YAML with line-tracking and reformats Pydantic ValidationError
# with the offending field's YAML line + current value. Without line
# context the agent retry-loops on the same Pydantic error.

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

# Normalize Windows backslashes to forward slashes before pattern matching.
# Without this, `plans\symbols.yaml` (Claude Code on Win32) falls through to
# the no-op branch and validation never runs -- the Phase 2.5 Test 3 drift.
FILE_PATH="${FILE_PATH//\\//}"

# Skip if no file path extracted or not a YAML file
if [[ -z "$FILE_PATH" || "$FILE_PATH" != *.yaml ]]; then
  exit 0
fi

HELPER="uv run python .claude/scripts/validate_yaml_helper.py"

# Route by path pattern -> (module, function) pair handed to the helper.
case "$FILE_PATH" in
  plans/tasks/CP-*.yaml | */plans/tasks/CP-*.yaml)
    $HELPER --path "$FILE_PATH" --module task_parser --function load_task || exit 2
    ;;
  plans/plan.yaml | */plans/plan.yaml)
    $HELPER --path "$FILE_PATH" --module plan_parser --function load_plan || exit 2
    ;;
  plans/backlog.yaml | */plans/backlog.yaml)
    $HELPER --path "$FILE_PATH" --module backlog_parser --function load_backlog || exit 2
    ;;
  plans/seams.yaml | */plans/seams.yaml)
    $HELPER --path "$FILE_PATH" --module seam_parser --function load_seams || exit 2
    ;;
  plans/component-contracts.yaml | */plans/component-contracts.yaml)
    $HELPER --path "$FILE_PATH" --module contract_parser --function load_contracts || exit 2
    ;;
  plans/symbols.yaml | */plans/symbols.yaml)
    $HELPER --path "$FILE_PATH" --module symbols_parser --function load_symbols || exit 2
    ;;
  plans/test-plan.yaml | */plans/test-plan.yaml)
    $HELPER --path "$FILE_PATH" --module test_plan_parser --function load_test_plan || exit 2
    ;;
  .iocane/findings/*.yaml | */.iocane/findings/*.yaml)
    $HELPER --path "$FILE_PATH" --module schemas --function FindingFile.model_validate || exit 2
    ;;
  *)
    # Not a schema-validated YAML file -- pass through
    exit 0
    ;;
esac

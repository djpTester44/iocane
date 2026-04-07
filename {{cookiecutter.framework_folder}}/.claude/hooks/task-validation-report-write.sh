#!/usr/bin/env bash
# PostToolUse hook: Edit | Write
# State derivation from task validation report writes.
# Routes workflow state based on the latest pass result:
#   PASS       -> next=dispatch
#   MECHANICAL -> next=task-recovery
#   DESIGN     -> next=escalate (blocks all progression)
#
# NOTE: Designed to run from a generated project root.
# This script is a harness template artifact.

INPUT=$(cat)

FILE_PATH=$(uv run python -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('tool_input', {}).get('file_path', ''))
except Exception:
    print('')
" <<< "$INPUT")

if [ -z "$FILE_PATH" ]; then
    exit 0
fi

MATCH=$(FILE_PATH="$FILE_PATH" uv run python -c "
import os, sys
p = os.path.normpath(os.environ['FILE_PATH']).replace('\\\\', '/')
print('yes' if p.endswith('plans/validation-reports/task-validation-report.yaml') else 'no')
")

if [ "$MATCH" != "yes" ]; then
    exit 0
fi

REPORT_FILE="plans/validation-reports/task-validation-report.yaml"
if [ ! -f "$REPORT_FILE" ]; then
    exit 0
fi

# Parse the latest pass entry and derive next workflow state
RESULT=$(uv run python -c "
import yaml, sys

with open('$REPORT_FILE', 'r', encoding='utf-8') as f:
    data = yaml.safe_load(f)

if not data or 'passes' not in data or not data['passes']:
    print('none')
    sys.exit(0)

last_pass = data['passes'][-1]
result = last_pass.get('result', 'UNKNOWN')
findings = last_pass.get('findings', []) or []

has_design = any(f.get('severity') == 'DESIGN' for f in findings)
has_mechanical = any(f.get('severity') == 'MECHANICAL' for f in findings)

if has_design:
    print('escalate')
elif has_mechanical:
    print('task-recovery')
elif result == 'PASS':
    print('dispatch')
else:
    print('validate-tasks')
" 2>/dev/null) || RESULT="none"

if [ "$RESULT" = "none" ]; then
    exit 0
fi

# Write workflow state
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date +"%Y-%m-%dT%H:%M:%SZ")
mkdir -p .iocane
printf '{"next":"%s","trigger":"task-validation-report.yaml (result: %s)","timestamp":"%s"}\n' \
    "$RESULT" "$RESULT" "$TIMESTAMP" > .iocane/workflow-state.json

exit 0

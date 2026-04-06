#!/usr/bin/env bash
# .claude/scripts/pre-invoke-auto-checkpoint.sh
# Pre-invocation gate for /auto-checkpoint.
# Validates preconditions before the workflow runs.

PLAN_FILE="plans/plan.yaml"
BACKLOG_FILE="plans/backlog.yaml"
SCRIPT_FILE=".claude/scripts/auto_checkpoint.py"

errors=0

if [ ! -f "$SCRIPT_FILE" ]; then
  echo "ERROR: Backing script not found: $SCRIPT_FILE" >&2
  errors=$((errors + 1))
fi

if [ ! -f "$BACKLOG_FILE" ]; then
  echo "ERROR: Backlog file not found: $BACKLOG_FILE" >&2
  errors=$((errors + 1))
fi

if [ ! -f "$PLAN_FILE" ]; then
  echo "ERROR: Plan file not found: $PLAN_FILE -- run /io-checkpoint first." >&2
  errors=$((errors + 1))
else
  HAS_CTS=$(uv run python -c "
import sys
sys.path.insert(0, '.claude/scripts')
from plan_parser import load_plan
plan = load_plan('$PLAN_FILE')
print('yes' if plan.connectivity_tests else 'no')
" 2>/dev/null || echo "no")
  if [ "$HAS_CTS" != "yes" ]; then
    echo "ERROR: $PLAN_FILE has no connectivity_tests -- plan has not been through /io-checkpoint yet." >&2
    errors=$((errors + 1))
  fi
fi

if [ $errors -gt 0 ]; then
  echo "Pre-invocation gate FAILED ($errors error(s)). /auto-checkpoint cannot proceed." >&2
  exit 1
fi

exit 0

#!/usr/bin/env bash
# .claude/scripts/pre-invoke-auto-checkpoint.sh
# Pre-invocation gate for /auto-checkpoint.
# Validates preconditions before the workflow runs.

PLAN_FILE="plans/plan.md"
BACKLOG_FILE="plans/backlog.md"
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
elif ! grep -q "## Connectivity Tests" "$PLAN_FILE"; then
  echo "ERROR: $PLAN_FILE lacks '## Connectivity Tests' section -- plan has not been through /io-checkpoint yet." >&2
  errors=$((errors + 1))
fi

if [ $errors -gt 0 ]; then
  echo "Pre-invocation gate FAILED ($errors error(s)). /auto-checkpoint cannot proceed." >&2
  exit 1
fi

exit 0

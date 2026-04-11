#!/usr/bin/env bash
# .claude/scripts/pre-invoke-validate-tasks.sh
# Blocks /validate-tasks if required upstream artifacts are missing.

set -euo pipefail

PLAN_FILE="plans/plan.yaml"
CONTRACTS_FILE="plans/component-contracts.yaml"
TASKS_DIR="plans/tasks"

if [ ! -f "$PLAN_FILE" ]; then
  echo "ERROR: $PLAN_FILE not found. Run /io-checkpoint before /validate-tasks." >&2
  exit 1
fi

if [ ! -f "$CONTRACTS_FILE" ]; then
  echo "ERROR: $CONTRACTS_FILE not found. Run /io-architect before /validate-tasks." >&2
  exit 1
fi

if ! ls "$TASKS_DIR"/CP-*.yaml 1> /dev/null 2>&1; then
  echo "ERROR: No task files found in $TASKS_DIR/. Run /io-plan-batch before /validate-tasks." >&2
  exit 1
fi

exit 0

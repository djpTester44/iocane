#!/usr/bin/env bash
# .claude/hooks/pre-invoke-io-plan-batch.sh
# Blocks /io-plan-batch if plans/plan.md does not carry a PASS stamp from review-plan.

PLAN_FILE="plans/plan.md"

if [ ! -f "$PLAN_FILE" ]; then
  echo "ERROR: $PLAN_FILE not found. Run /io-checkpoint before /io-plan-batch." >&2
  exit 1
fi

if ! grep -q "\*\*Plan Validated:\*\* PASS" "$PLAN_FILE"; then
  echo "ERROR: $PLAN_FILE has not passed validate-plan validation." >&2
  echo "       Run /validate-plan and ensure a 'Plan Validated: PASS' stamp is present before invoking /io-plan-batch." >&2
  exit 1
fi

exit 0

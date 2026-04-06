#!/usr/bin/env bash
# .claude/hooks/pre-invoke-io-plan-batch.sh
# Blocks /io-plan-batch if plans/plan.yaml does not carry a PASS stamp from review-plan.

PLAN_FILE="plans/plan.yaml"

if [ ! -f "$PLAN_FILE" ]; then
  echo "ERROR: $PLAN_FILE not found. Run /io-checkpoint before /io-plan-batch." >&2
  exit 1
fi

IS_VALIDATED=$(uv run python -c "
import sys
sys.path.insert(0, '.claude/scripts')
from plan_parser import load_plan
plan = load_plan('$PLAN_FILE')
print('yes' if plan.validated else 'no')
" 2>/dev/null || echo "no")

if [ "$IS_VALIDATED" != "yes" ]; then
  echo "ERROR: $PLAN_FILE has not passed validate-plan validation." >&2
  echo "       Run /validate-plan and ensure validated: true before invoking /io-plan-batch." >&2
  exit 1
fi

BACKLOG_FILE="plans/backlog.yaml"

if [ -f "$BACKLOG_FILE" ]; then
  HAS_OPEN_DR=$(uv run python -c "
import sys
sys.path.insert(0, '.claude/scripts')
from backlog_parser import load_backlog, open_items
backlog = load_backlog('$BACKLOG_FILE')
dr = [i for i in open_items(backlog) if i.tag.value in ('DESIGN', 'REFACTOR')]
print('yes' if dr else 'no')
" 2>/dev/null || echo "no")
  if [ "$HAS_OPEN_DR" = "yes" ]; then
    echo "ERROR: Open [DESIGN] or [REFACTOR] backlog items exist. Run /io-architect before /io-plan-batch." >&2
    exit 1
  fi
fi

exit 0

#!/usr/bin/env bash
# .claude/scripts/pre-invoke-auto-architect.sh
# Pre-invocation gate for /auto-architect.
# Validates preconditions before the workflow runs.

BACKLOG_FILE="plans/backlog.yaml"
PROJECT_SPEC="plans/project-spec.md"
ROADMAP_FILE="plans/roadmap.md"
SCRIPT_FILE=".claude/scripts/auto_architect.py"

errors=0

if [ ! -f "$SCRIPT_FILE" ]; then
  echo "ERROR: Backing script not found: $SCRIPT_FILE" >&2
  errors=$((errors + 1))
fi

if [ ! -f "$BACKLOG_FILE" ]; then
  echo "ERROR: $BACKLOG_FILE not found." >&2
  errors=$((errors + 1))
fi

# Incremental mode only -- greenfield must run /io-architect manually.
if [ ! -f "$PROJECT_SPEC" ]; then
  echo "ERROR: $PROJECT_SPEC not found. Greenfield projects must run /io-architect manually." >&2
  errors=$((errors + 1))
fi

if [ ! -f "$ROADMAP_FILE" ]; then
  echo "ERROR: $ROADMAP_FILE not found. Run /io-specify first." >&2
  errors=$((errors + 1))
elif grep -qi "Draft" "$ROADMAP_FILE" 2>/dev/null; then
  echo "ERROR: $ROADMAP_FILE is still marked Draft. Finalize the roadmap before running /auto-architect." >&2
  errors=$((errors + 1))
fi

# At least one open DESIGN/REFACTOR item with a Routed annotation prompt containing /io-architect.
if [ -f "$BACKLOG_FILE" ]; then
  CHECK_RESULT=$(uv run python -c "
import sys
sys.path.insert(0, '.claude/scripts')
from backlog_parser import load_backlog, open_items
backlog = load_backlog('$BACKLOG_FILE')
opened = open_items(backlog)
dr_items = [i for i in opened if i.tag.value in ('DESIGN', 'REFACTOR')]
if not dr_items:
    print('no_items')
elif not any((rp := i.get_routing_prompt()) and '/io-architect' in rp for i in dr_items):
    print('no_routed')
else:
    print('ok')
" 2>/dev/null || echo "error")
  if [ "$CHECK_RESULT" = "no_items" ]; then
    echo "ERROR: No open [DESIGN] or [REFACTOR] items found in $BACKLOG_FILE." >&2
    errors=$((errors + 1))
  elif [ "$CHECK_RESULT" = "no_routed" ]; then
    echo "ERROR: No open [DESIGN/REFACTOR] items have /io-architect routing prompts. Run /io-backlog-triage first." >&2
    errors=$((errors + 1))
  fi
fi

if [ $errors -gt 0 ]; then
  echo "Pre-invocation gate FAILED ($errors error(s)). /auto-architect cannot proceed." >&2
  exit 1
fi

exit 0

#!/usr/bin/env bash
# PostToolUse hook: Edit | Write
# Auto-assigns BL-NNN identifiers to new backlog items after any write to
# plans/backlog.yaml. Delegates to assign_backlog_ids.py (idempotent).
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
print('yes' if p.endswith('plans/backlog.yaml') else 'no')
")

if [ "$MATCH" = "yes" ] && [ -f "plans/backlog.yaml" ]; then
    uv run python .claude/scripts/assign_backlog_ids.py

    # --- State derivation: route based on open backlog items ---
    NEXT=$(uv run python -c "
import sys
sys.path.insert(0, '.claude/scripts')
from backlog_parser import load_backlog, open_items

backlog = load_backlog('plans/backlog.yaml')
opened = open_items(backlog)

has_design = any(i.tag.value in ('DESIGN', 'REFACTOR') for i in opened)
has_ct_gap = any(
    i.tag.value == 'TEST' and 'CT gap' in (i.title or '') for i in opened
)
has_cleanup = any(i.tag.value in ('CLEANUP', 'TEST') for i in opened)

if has_design:
    print('auto-architect')
elif has_ct_gap:
    print('io-ct-remediate')
elif has_cleanup:
    print('auto-checkpoint')
else:
    print('')
" 2>/dev/null) || NEXT=""

    if [ -n "$NEXT" ]; then
        TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date +"%Y-%m-%dT%H:%M:%SZ")
        mkdir -p .iocane
        printf '{"next":"%s","trigger":"backlog.yaml (open items routed)","timestamp":"%s"}\n' \
            "$NEXT" "$TIMESTAMP" > .iocane/workflow-state.json
    fi
fi

exit 0

#!/usr/bin/env bash
# PostToolUse hook: Edit | Write
# Self-healing guard: if the agent writes Remediated: annotations directly to
# plans/backlog.md without running archive-approved.sh, this hook detects the
# drift and runs archive-approved.sh to sync plan.md.
#
# NOTE: Designed to run from the project root.
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

MATCH=$(uv run python -c "
import os, sys
p = os.path.normpath('$FILE_PATH').replace('\\\\', '/')
print('yes' if p.endswith('plans/backlog.md') else 'no')
")

if [ "$MATCH" != "yes" ] || [ ! -f "plans/backlog.md" ] || [ ! -f "plans/plan.md" ]; then
    exit 0
fi

# Find CP-IDs with Remediated: annotations in backlog.md where plan.md still
# shows [ ] pending — these are stale due to bypassing archive-approved.sh.
STALE_CPS=$(uv run python -c "
import re, sys

with open('plans/backlog.md', 'r', encoding='utf-8') as f:
    backlog = f.read()
with open('plans/plan.md', 'r', encoding='utf-8') as f:
    plan = f.read()

remediated = re.findall(r'Remediated:\s+(CP-\w+)', backlog)
stale = []
seen = set()
for cp_id in remediated:
    if cp_id in seen:
        continue
    seen.add(cp_id)
    pattern = r'### ' + re.escape(cp_id) + r':.*?\*\*Status:\*\*\s*\[ \] pending'
    if re.search(pattern, plan, re.DOTALL):
        stale.append(cp_id)

print(' '.join(stale))
")

if [ -z "$STALE_CPS" ]; then
    exit 0
fi

CORRECTED=()
for CP_ID in $STALE_CPS; do
    if bash .claude/scripts/archive-approved.sh "$CP_ID" > /dev/null 2>&1; then
        CORRECTED+=("$CP_ID")
    fi
done

if [ ${#CORRECTED[@]} -gt 0 ]; then
    JOINED="${CORRECTED[*]}"
    MSG="archive-sync: ran archive-approved.sh for ${JOINED// /, } (plan.md was stale)"
    echo "{\"type\": \"systemPrompt\", \"content\": \"$MSG\"}"
fi

exit 0

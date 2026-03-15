#!/usr/bin/env bash
# .claude/hooks/on-approved-marker.sh
#
# PostToolUse hook: fires when a Write tool use completes.
# If the written file is plans/tasks/CP-XX.approved, directly flips the
# Status checkbox in plans/plan.md from "[ ] pending" to "[x] done"
# for the approved checkpoint using a Python in-process edit.

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null)}"

if [ -z "$REPO_ROOT" ]; then
    exit 0
fi

# Parse file_path from the hook JSON payload on stdin
INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | uv run python -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('file_path',''))")

# Only act on CP-XX.approved files written to plans/tasks/
if [[ "$FILE_PATH" != *"plans/tasks/CP-"*".approved" ]]; then
    exit 0
fi

CP_ID=$(basename "$FILE_PATH" .approved)
PLAN_FILE="$REPO_ROOT/plans/plan.md"

if [ ! -f "$PLAN_FILE" ]; then
    exit 0
fi

# Write the validating sentinel so reset-on-plan-write.sh exempts this write
mkdir -p "$REPO_ROOT/.iocane"
echo "status-sync" > "$REPO_ROOT/.iocane/validating"

# Flip the Status line directly — no sub-agent needed
uv run python - <<EOF > "$REPO_ROOT/.iocane/status-sync-${CP_ID}.log" 2>&1
import re, sys

plan = "$PLAN_FILE"
cp_id = "${CP_ID}"

with open(plan, "r", encoding="utf-8") as f:
    text = f.read()

pattern = r"(### " + re.escape(cp_id) + r":.*?)\*\*Status:\*\* \[ \] pending"
replacement = r"\1**Status:** [x] done"
new_text, count = re.subn(pattern, replacement, text, count=1, flags=re.DOTALL)

if count == 0:
    print(f"WARNING: no '[ ] pending' status found under ### {cp_id}:")
    sys.exit(0)

with open(plan, "w", encoding="utf-8") as f:
    f.write(new_text)

print(f"Done. {cp_id} status set to [x] done.")
EOF

exit 0

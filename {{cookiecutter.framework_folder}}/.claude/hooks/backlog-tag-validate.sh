#!/usr/bin/env bash
# PostToolUse hook: Edit | Write
# Advisory check: warns when checkbox lines in plans/backlog.md lack a valid tag.
# Valid tags: [DESIGN] [REFACTOR] [CLEANUP] [DEFERRED] [TEST]
# Does not block (exit 0 always) -- backlog items sometimes need human triage.

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
print('yes' if p.endswith('plans/backlog.md') else 'no')
")

if [ "$MATCH" != "yes" ] || [ ! -f "plans/backlog.md" ]; then
    exit 0
fi

UNTAGGED=$(grep -E '^\s*- \[[ x]\] ' plans/backlog.md | grep -vE '\[(DESIGN|REFACTOR|CLEANUP|DEFERRED|TEST|CI-REGRESSION|CI-COLLECTION-ERROR|CI-EXTERNAL)\]' || true)

if [ -n "$UNTAGGED" ]; then
    echo "WARNING: Untagged backlog items found in plans/backlog.md:"
    echo "$UNTAGGED" | while IFS= read -r line; do
        echo "  $line"
    done
    echo "  Valid tags: [DESIGN] [REFACTOR] [CLEANUP] [DEFERRED] [TEST] [CI-REGRESSION] [CI-COLLECTION-ERROR] [CI-EXTERNAL]"
fi

exit 0

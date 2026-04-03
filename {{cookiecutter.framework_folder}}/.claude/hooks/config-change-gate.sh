#!/usr/bin/env bash
# ConfigChange hook
# Blocks modification of settings.json during a session.
# policy_settings changes are unblockable per the docs -- this is fine; they
# represent enterprise-managed overrides and should always take effect.
#
# Input fields:
#   source     -- which config type changed (project_settings, user_settings, etc.)
#   file_path  -- path to the changed file (may be absent)
#
# Exit 2 + JSON decision: "block" prevents the change from being applied.

set -euo pipefail

INPUT=$(cat)

SOURCE=$(echo "$INPUT" | uv run python -c "
import sys, json
d = json.load(sys.stdin)
print(d.get('source', ''))
" 2>/dev/null || echo "")

# Block project settings changes -- harness hook wiring lives here.
if [ "$SOURCE" = "project_settings" ]; then
    printf '{"decision":"block","reason":"settings.json modification blocked -- harness hook wiring must not be changed mid-session."}' 
    exit 2
fi

exit 0

#!/usr/bin/env bash
# SessionEnd hook: clean up transient sentinel state on session exit.
#
# Input fields:
#   reason -- why the session ended (exit, /clear, timeout, logout,
#              bypass_permissions_disabled, other)
#
# Actions:
#   - Logs reason + timestamp to .iocane/session-end.log
#   - Clears .iocane/validating sentinel (prevents stale lock from disabling reset hooks)
#   - Clears .iocane/architect-mode sentinel (prevents stale gate from blocking writes)
#
# Default timeout: 1.5s (configurable via CLAUDE_CODE_SESSIONEND_HOOKS_TIMEOUT_MS).
# Keep this script fast -- it runs inside the timeout window.
#
# Source: hooks.md:1790-1792 (Claude Code docs -- SessionEnd input schema)

set -euo pipefail

INPUT=$(cat)
mkdir -p .iocane

REASON=$(printf '%s' "$INPUT" | uv run python -c "
import sys, json
raw = sys.stdin.read()
d = json.loads(raw) if raw.strip() else {}
print(d.get('reason', 'unknown'))
" 2>/dev/null || echo "unknown")

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
printf '%s reason=%s\n' "$TIMESTAMP" "$REASON" >> .iocane/session-end.log

# Clear sentinels that persist across sessions when a session exits abnormally.
# session-start.sh clears validating at startup, but a crashed session may not
# reach session-start before the user re-opens the project.
rm -f .iocane/validating
rm -f .iocane/architect-mode

exit 0

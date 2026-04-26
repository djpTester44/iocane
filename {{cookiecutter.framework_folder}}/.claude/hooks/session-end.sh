#!/usr/bin/env bash
# SessionEnd hook: archive per-session capability state on session exit.
#
# Input fields:
#   reason -- why the session ended (exit, /clear, timeout, logout,
#              bypass_permissions_disabled, other)
#
# Actions:
#   - Logs reason + timestamp to .iocane/session-end.log
#   - Invokes capability.py session-end (revokes any still-live grants
#     for this session, archives the jsonl to archive/YYYY-MM/, freezes
#     the manifest entry snapshot).
#   - Clears the separate .iocane/architect-mode sentinel (prevents
#     stale gate from blocking writes across sessions).
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

# Capability lifecycle: revoke active grants + archive the session
# before the transient sentinel cleanup. Session id comes from the
# payload; failures are non-fatal (same rationale as session-start).
CAP_SID=$(printf '%s' "$INPUT" | uv run python -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('session_id', '') or '')
except Exception:
    print('')
" 2>/dev/null || echo "")
CAP_REPO_ROOT="${IOCANE_REPO_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
if [ -n "$CAP_SID" ]; then
    uv run python .claude/scripts/capability.py session-end \
        --repo-root "$CAP_REPO_ROOT" \
        --session-id "$CAP_SID" >/dev/null 2>&1 || true
fi

# Clear the architect-mode sentinel that persists across sessions when
# a session exits abnormally. .iocane/architect-mode is a separate
# session-spanning mode flag -- out of scope for the capability-gate
# refactor, managed independently. Legacy .iocane/validating cleanup is
# retired: all workflows now use capability grants, and session-end has
# already revoked any live grants + archived the jsonl above.
rm -f .iocane/architect-mode

exit 0

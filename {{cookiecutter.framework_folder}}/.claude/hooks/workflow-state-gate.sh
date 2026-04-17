#!/usr/bin/env bash
# PreToolUse hook: Edit | Write
# Blocks implementation writes when workflow state does not authorize them.
# Fires for ALL sessions (interactive + sub-agent). Separate from write-gate.sh.
#
# write-gate.sh scopes sub-agent writes to their task's write_targets.
# This hook prevents ANY session from writing to src/tests/interfaces/*.py
# when the workflow hasn't reached dispatch state.
#
# NOTE: Designed to run from a generated project root.
# This script is a harness template artifact.

INPUT=$(cat)

FILE_PATH=$(printf '%s' "$INPUT" | uv run python -c "
import sys, json, os
try:
    d = json.load(sys.stdin)
    fp = d.get('tool_input', {}).get('file_path', '')
    fp = os.path.normpath(fp).replace(os.sep, '/')
    cwd = os.path.normpath(os.getcwd()).replace(os.sep, '/')
    if fp.startswith(cwd + '/'):
        fp = fp[len(cwd) + 1:]
    print(fp)
except Exception:
    print('')
")

if [ -z "$FILE_PATH" ]; then
    exit 0
fi

# Only gate implementation paths
if [[ "$FILE_PATH" != src/* && "$FILE_PATH" != tests/* && ! "$FILE_PATH" =~ interfaces/.*\.py$ ]]; then
    exit 0
fi

# Escape hatch: manual override sentinel
if [ -f ".iocane/manual-override" ]; then
    exit 0
fi

# Role-aware bypass: Tier-1 Test Author writes to tests/contracts/
# between /io-architect and /io-checkpoint. At that workflow state,
# "next" is NOT "dispatch", so the default check below would block
# the tester. Scope the bypass to tests/contracts/ only -- any other
# target still falls through to the state check (and will block).
# .iocane/amend-signals/*.yaml writes are already outside the gate
# scope (line 34 filter) and reach this point only if FILE_PATH is
# src/tests/interfaces -- the bypass is intentionally narrow.
if [ "${IOCANE_ROLE:-}" = "tester" ] && [[ "$FILE_PATH" == tests/contracts/* ]]; then
    exit 0
fi

# ct_author (Phase 4) -- scoped bypass for tests/connectivity/ only.
# Any other target with IOCANE_ROLE=ct_author falls through to the
# default state check. At dispatch time NEXT == dispatch, so writes
# to src/, tests/contracts/, interfaces/, or any non-connectivity
# path would pass the state check -- meaning the role-discipline
# layer is the session-start role block, not this hook. The bypass
# is narrow by design (D13): write-gate.sh exempts non-haiku sessions
# (line 56-59), so no role scoping can live there for Sonnet
# ct_author sessions; this hook plus the role block plus the
# reset-hook chain constitute the full enforcement model.
if [ "${IOCANE_ROLE:-}" = "ct_author" ] && [[ "$FILE_PATH" == tests/connectivity/* ]]; then
    exit 0
fi

STATE_FILE=".iocane/workflow-state.json"
if [ ! -f "$STATE_FILE" ]; then
    exit 0  # No state file = no enforcement (graceful degradation)
fi

# Bash-native JSON parse (no Python overhead on hot path)
NEXT=$(grep -o '"next":"[^"]*"' "$STATE_FILE" | cut -d'"' -f4)
ESCALATION=$(grep -o '"escalation":true' "$STATE_FILE")

if [ -n "$ESCALATION" ]; then
    echo "BLOCKED: Escalation flag active. Resolve .iocane/escalation.log before writing implementation files." >&2
    exit 2
fi

if [ -n "$NEXT" ] && [ "$NEXT" != "dispatch" ]; then
    echo "BLOCKED: Writes to implementation files not authorized." >&2
    echo "Current workflow state: next=$NEXT" >&2
    echo "Advance the workflow: run /$NEXT" >&2
    exit 2
fi

exit 0

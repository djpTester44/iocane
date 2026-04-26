#!/usr/bin/env bash
# PreToolUse hook: Edit | Write
# Blocks implementation writes when workflow state does not authorize them.
# Fires for ALL sessions (interactive + sub-agent). Separate from write-gate.sh.
#
# write-gate.sh scopes sub-agent writes to their task's write_targets.
# This hook prevents ANY session from writing to src/tests/*.py
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
if [[ "$FILE_PATH" != src/* && "$FILE_PATH" != tests/* ]]; then
    exit 0
fi

# Escape hatch: manual override sentinel
if [ -f ".iocane/manual-override" ]; then
    exit 0
fi

STATE_FILE=".iocane/workflow-state.json"
# CWD-scoped intentionally. Worktree sub-agent sessions derive their own
# workflow-state.json from the worktree's plan.yaml at session-start and
# enforce against it; parent-scoping would overwrite the orchestrator's
# state with sub-agent-local views. See worktree-shared-state-audit.md.
if [ ! -f "$STATE_FILE" ]; then
    exit 0  # No state file = no enforcement (graceful degradation)
fi

# Bash-native JSON parse (no Python overhead on hot path).
# DO NOT add `set -e` to this file without first migrating these two
# lines to python. Under `set -e`, a no-match grep exit-1 silently
# kills the hook. See AGENTS.md 2026-04-17 entry (sites #15/#16).
NEXT=$(grep -o '"next":"[^"]*"' "$STATE_FILE" | cut -d'"' -f4 || true)
ESCALATION=$(grep -o '"escalation":true' "$STATE_FILE" || true)

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

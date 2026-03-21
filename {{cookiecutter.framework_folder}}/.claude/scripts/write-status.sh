#!/usr/bin/env bash
# .claude/scripts/write-status.sh
#
# Write a deterministic checkpoint status file.
# Always writes to $IOCANE_REPO_ROOT/plans/tasks/<CP_ID>.status.
# Path is enforced here — callers (io-execute, task files) must not hardcode it.
#
# Usage:
#   bash .claude/scripts/write-status.sh <CP_ID> <STATUS>
#
# Arguments:
#   CP_ID   — checkpoint identifier, e.g. CP-07R2
#   STATUS  — PASS, or FAIL: <reason>
#
# Environment:
#   IOCANE_REPO_ROOT — set by dispatch-agents.sh for sub-agents;
#                      falls back to git rev-parse --show-toplevel.

set -euo pipefail

CP_ID="${1:?write-status.sh requires <CP_ID> as first argument}"
STATUS="${2:?write-status.sh requires <STATUS> as second argument}"

REPO_ROOT="${IOCANE_REPO_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null)}"

if [ -z "$REPO_ROOT" ]; then
    echo "ERROR: write-status.sh: cannot determine repo root (IOCANE_REPO_ROOT not set and git failed)" >&2
    exit 1
fi

STATUS_FILE="$REPO_ROOT/plans/tasks/$CP_ID.status"

printf '%s\n' "$STATUS" > "$STATUS_FILE"
echo "Status written: $STATUS_FILE ($STATUS)"

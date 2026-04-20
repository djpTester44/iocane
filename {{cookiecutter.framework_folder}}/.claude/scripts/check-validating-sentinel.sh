#!/usr/bin/env bash
# Helper: decide whether the .iocane/validating sentinel is "active".
#
# The sentinel is touched by /io-architect Step H-pre to suppress reset
# hooks during the canonical-artifact write sequence, and explicitly
# removed at Step H-5. Cross-session leakage is handled by session-start
# and session-end. Within-session leakage (architect errors mid-write,
# user edits manually before re-running) is handled here: if the sentinel
# is older than IOCANE_SENTINEL_TTL_SEC seconds, treat it as stale.
#
# Exit 0: sentinel exists and is fresh -- caller should bypass its gate.
# Exit 1: sentinel does not exist OR is stale (and was just cleaned up) --
#         caller should run its gate normally.
#
# Usage from a hook:
#   if bash .claude/scripts/check-validating-sentinel.sh; then
#       exit 0
#   fi
#
# NOTE: Designed to run from a generated project root.
# This script is a harness template artifact.

SENTINEL=".iocane/validating"
TTL_SEC="${IOCANE_SENTINEL_TTL_SEC:-3600}"

if [ ! -f "$SENTINEL" ]; then
    exit 1
fi

AGE=$(uv run python -c "
import os, time
try:
    print(int(time.time() - os.path.getmtime('$SENTINEL')))
except Exception:
    print(-1)
" 2>/dev/null)

if [ -z "$AGE" ] || [ "$AGE" -lt 0 ]; then
    # Could not stat -- be conservative, do not bypass.
    exit 1
fi

if [ "$AGE" -gt "$TTL_SEC" ]; then
    rm -f "$SENTINEL"
    exit 1
fi

exit 0

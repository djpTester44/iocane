#!/usr/bin/env bash
# Helper: does an active capability cover (op, target) for this session?
#
# Usage: capability-covers.sh <session_id> <op> <target>
#   op:     write | rm
#   target: the file path (Edit/Write) or the operand (rm)
#
# Exit 0: a live grant in $REPO_ROOT/.iocane/sessions/<sid>.active.txt
#         covers the request -- caller should bypass its gate.
# Exit 1: no matching grant -- caller should run its gate normally.
#
# Hot-path contract: reads the flat-text cache only. No python, no yaml,
# no jsonl parse. The cache is the authority; capability.py is the sole
# writer. An agent that forges grants by appending to the jsonl audit log
# cannot bypass this gate -- the cache is unchanged.
#
# Path resolution: IOCANE_REPO_ROOT env var wins (set by dispatch-agents.sh
# for subagents so their worktree-scoped writes hit the parent repo's
# sessions/). Falls back to `git rev-parse --show-toplevel`.
#
# NOTE: Designed to run from a generated project root.
# This script is a harness template artifact.

set -u

SID="${1:-}"
OP="${2:-}"
TARGET="${3:-}"

if [ -z "$SID" ] || [ -z "$OP" ] || [ -z "$TARGET" ]; then
    exit 1
fi

REPO_ROOT="${IOCANE_REPO_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null)}"
[ -z "$REPO_ROOT" ] && exit 1

CACHE="$REPO_ROOT/.iocane/sessions/$SID.active.txt"
[ ! -f "$CACHE" ] && exit 1
[ ! -s "$CACHE" ] && exit 1

# Normalize target: strip leading ./ and collapse backslashes (Windows
# path style can reach here from Claude Code on Win11).
NORM_TARGET="${TARGET#./}"
NORM_TARGET="${NORM_TARGET//\\//}"

while IFS= read -r line || [ -n "$line" ]; do
    # Skip blank lines.
    [ -z "$line" ] && continue
    # Line format: <op>:<pattern>
    line_op="${line%%:*}"
    [ "$line_op" != "$OP" ] && continue
    pattern="${line#*:}"
    [ -z "$pattern" ] && continue
    # shellcheck disable=SC2053
    if [[ $NORM_TARGET == $pattern ]]; then
        exit 0
    fi
done < "$CACHE"

exit 1

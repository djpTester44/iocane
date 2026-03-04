#!/bin/bash
# smart_search: Agent search tool. Default: filenames only. Use -c for content.
# Usage: ./smart_search.sh [-c] "pattern" [path]
set -o pipefail

MAX_LINE=200
MAX_OUT=50

EXCLUDES="--exclude-dir={.venv,node_modules,.git,.idea,.vscode,__pycache__,dist,build,coverage}"
EXCLUDE_FILES="--exclude={*.min.js,*.map,*.lock,*.svg}"

# Content mode (opt-in)
if [ "$1" = "-c" ]; then
    shift
    [ -z "$1" ] && { echo "ERR: missing pattern"; exit 1; }
    OUT=$(grep -r -n -I --color=never $EXCLUDES $EXCLUDE_FILES "$@" 2>/dev/null)
    # Check if OUT is empty (grep failed to find anything)
    if [ -z "$OUT" ]; then
        exit 0
    fi
    TOTAL=$(echo "$OUT" | grep -c '^' || echo 0)
    echo "$OUT" | head -n "$MAX_OUT" | cut -c "1-$MAX_LINE"
    [ "$TOTAL" -gt "$MAX_OUT" ] && echo "--- TRUNCATED $MAX_OUT/$TOTAL ---"
    exit 0
fi

# Default: filenames only (most token-efficient)
[ -z "$1" ] && { echo "ERR: missing pattern"; exit 1; }
grep -r -l -I --color=never $EXCLUDES $EXCLUDE_FILES "$@" 2>/dev/null | head -n "$MAX_OUT" || true
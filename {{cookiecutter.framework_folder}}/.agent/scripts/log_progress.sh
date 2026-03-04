#!/usr/bin/env bash

# log_progress.sh
# Appends task execution state to plans/progress.md statelessly.
# Usage: ./log_progress.sh <TASK_ID> <STATUS> [NOTES]

set -euo pipefail

PROGRESS_FILE="plans/progress.md"

if [ "$#" -lt 2 ]; then
    echo "ERROR: Invalid arguments."
    echo "Usage: $0 <TASK_ID> <STATUS> [NOTES]"
    exit 1
fi

TASK_ID="$1"
STATUS="$2"
NOTES="${3:-}"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Initialize file and table structure if it doesn't exist
if [ ! -f "$PROGRESS_FILE" ]; then
    mkdir -p "$(dirname "$PROGRESS_FILE")"
    echo "# Execution Progress Log" > "$PROGRESS_FILE"
    echo "Append-only ledger of completed tasks from the io-loop state machine." >> "$PROGRESS_FILE"
    echo "" >> "$PROGRESS_FILE"
    echo "| Timestamp (UTC) | Task ID | Status | Notes |" >> "$PROGRESS_FILE"
    echo "| :--- | :--- | :--- | :--- |" >> "$PROGRESS_FILE"
fi

# Clean up newlines in notes to prevent markdown table breakage
CLEAN_NOTES=$(echo "$NOTES" | tr '\n' ' ')

# Append the record
echo "| $TIMESTAMP | \`$TASK_ID\` | **$STATUS** | $CLEAN_NOTES |" >> "$PROGRESS_FILE"

echo "Success: Logged $TASK_ID as $STATUS to $PROGRESS_FILE."
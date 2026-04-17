#!/usr/bin/env bash
# PostCompact hook: re-inject harness orientation after compaction discards session context.
#
# Input fields:
#   compact_summary -- the generated compaction summary string
#
# Output: JSON with systemPrompt to restore orientation. Uses the same injection
# path as SessionStart so Claude re-orients without needing to re-read plan.yaml.
#
# Requires: pre-compact.sh to have written .iocane/pre-compact-state.json
#
# Source: hooks.md:1757-1759 (Claude Code docs -- PostCompact input schema)

set -euo pipefail

INPUT=$(cat)
# CWD-scoped intentionally: reads pre-compact-state.json written by
# pre-compact.sh IN THE SAME SESSION. See pre-compact.sh for the
# writer-reader pair contract.
mkdir -p .iocane

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
printf '%s post-compact\n' "$TIMESTAMP" >> .iocane/compact.log

# Read saved pre-compact state
STATE_FILE=".iocane/pre-compact-state.json"
ACTIVE_CHECKPOINT=""
ESCALATION_ALERT=""

if [ -f "$STATE_FILE" ]; then
    PARSED=$(uv run python -c "
import json
d = json.load(open('.iocane/pre-compact-state.json'))
print(d.get('active_checkpoint', ''))
print(d.get('escalation_flag', ''))
" 2>/dev/null || printf '\n\n')
    ACTIVE_CHECKPOINT=$(echo "$PARSED" | sed -n '1p')
    ESC_FLAG=$(echo "$PARSED" | sed -n '2p')

    if [ "$ESC_FLAG" = "present" ]; then
        ESCALATION_ALERT="ESCALATION FLAG IS SET -- read .iocane/escalation.log before proceeding."
    fi
fi

SESSION_MODEL=$(cat .iocane/session-model 2>/dev/null || echo "unknown")

CONTEXT="# Post-Compaction Orientation

Compaction just occurred. Your session context was compressed.

${ESCALATION_ALERT}
## Active Checkpoint
${ACTIVE_CHECKPOINT:-No active checkpoint at compaction time.}

## What to Do
- Re-read plans/plan.yaml if you were mid-checkpoint.
- Re-read plans/backlog.yaml if you were tracking open items.
- Do not assume prior approval gates survived compaction.
- Session model: $SESSION_MODEL

Rules reference: .claude/rules/
Workflow reference: .claude/commands/"

printf '%s' "$CONTEXT" | uv run python -c "
import sys, json
content = sys.stdin.read()
print(json.dumps({'systemPrompt': content}))
"

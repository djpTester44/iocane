#!/usr/bin/env bash
# SessionStart hook: orient Claude at the start of every session.
#
# Reads plan.md, plans/tasks/, and backlog.md to determine project state.
# Outputs a structured briefing and suggests the appropriate next workflow.
#
# NOTE: Designed to run from a generated project root.
# This script is a harness template artifact.

set -euo pipefail

INPUT=$(cat)

# Clear any stale validating sentinel left by a crashed session.
# If present at session start, the reset hooks would be permanently disabled.
rm -f .iocane/validating

# Dump raw payload for schema debugging (overwritten every session start).
mkdir -p .iocane
printf '%s' "$INPUT" > .iocane/session-start-payload.json

# Write model name so write-gate can exempt interactive (non-haiku) sessions.
# Sub-agents: dispatch-agents.sh exports IOCANE_MODEL_NAME with the real model string.
# Interactive: fall back to payload parsing (best-effort) then "interactive".
if [ -n "${IOCANE_MODEL_NAME:-}" ]; then
    echo -n "$IOCANE_MODEL_NAME" > .iocane/session-model
else
    printf '%s' "$INPUT" | uv run python -c "
import sys, json, os
raw = sys.stdin.read()
d = json.loads(raw) if raw.strip() else {}
model = (
    d.get('model')
    or d.get('session', {}).get('model')
    or d.get('config', {}).get('model')
    or d.get('metadata', {}).get('model')
    or 'interactive'
)
open('.iocane/session-model', 'w').write(model)
" 2>/dev/null || echo -n "interactive" > .iocane/session-model
fi

output_json() {
    local content="$1"
    uv run python -c "
import json, sys
content = sys.stdin.read()
print(json.dumps({'systemPrompt': content}))
" <<< "$content"
}

# --- Escalation flag check ---
ESCALATION_FLAG=".iocane/escalation.flag"
ESCALATION_LOG=".iocane/escalation.log"
ESCALATION_ALERT=""

if [ -f "$ESCALATION_FLAG" ]; then
    ESCALATION_ALERT="
## ESCALATION REQUIRES REVIEW

One or more sub-agents failed in a previous execution batch.
Log: $ESCALATION_LOG

Read the log and resolve before running /io-orchestrate again.
Clear $ESCALATION_FLAG after review to re-enable orchestration.
"
fi

# --- Read plan.md for checkpoint status ---
PLAN_FILE="plans/plan.md"
ACTIVE_CHECKPOINT=""
PENDING_CHECKPOINTS=""
COMPLETED_CHECKPOINTS=""

if [ -f "$PLAN_FILE" ]; then
    # Extract checkpoints and their status from plan.md
    COMPLETED_CHECKPOINTS=$(grep -E "^\*\*Status:\*\* \[x\]" "$PLAN_FILE" -B5 | grep "^### CP-" | sed 's/### //' || echo "none")
    PENDING_CHECKPOINTS=$(grep -E "^\*\*Status:\*\* \[ \] pending" "$PLAN_FILE" -B5 | grep "^### CP-" | sed 's/### //' || echo "none")
    IN_PROGRESS=$(grep -E "^\*\*Status:\*\* \[~\] in-progress" "$PLAN_FILE" -B5 | grep "^### CP-" | sed 's/### //' || echo "")

    if [ -n "$IN_PROGRESS" ]; then
        ACTIVE_CHECKPOINT="$IN_PROGRESS"
    else
        # First pending checkpoint is the active one
        ACTIVE_CHECKPOINT=$(echo "$PENDING_CHECKPOINTS" | head -1)
    fi
fi

# --- Read plans/tasks/ for recent status files ---
TASKS_DIR="plans/tasks"
LAST_COMPLETED=""
RECENT_FAILURES=""

if [ -d "$TASKS_DIR" ]; then
    # Find most recently passed checkpoint
    LAST_COMPLETED=$(ls -t "$TASKS_DIR"/*.status 2>/dev/null | head -3 | while read f; do
        STATUS=$(cat "$f" 2>/dev/null || echo "")
        CP_ID=$(basename "$f" .status)
        if [[ "$STATUS" == "PASS" ]]; then
            echo "$CP_ID"
            break
        fi
    done || echo "none")

    # Find any recent failures
    RECENT_FAILURES=$(ls -t "$TASKS_DIR"/*.status 2>/dev/null | head -10 | while read f; do
        STATUS=$(cat "$f" 2>/dev/null || echo "")
        CP_ID=$(basename "$f" .status)
        if [[ "$STATUS" == FAIL* ]]; then
            echo "  $CP_ID: $STATUS"
        fi
    done || echo "")
fi

# --- Read backlog.md for open items ---
BACKLOG_FILE="plans/backlog.md"
BACKLOG_ALERT=""
DESIGN_ITEMS=""
REFACTOR_ITEMS=""

if [ -f "$BACKLOG_FILE" ]; then
    DESIGN_ITEMS=$(grep -c "^\- \[ \] \[DESIGN\]" "$BACKLOG_FILE" 2>/dev/null | tr -d '\r' || echo "0")
    REFACTOR_ITEMS=$(grep -c "^\- \[ \] \[REFACTOR\]" "$BACKLOG_FILE" 2>/dev/null | tr -d '\r' || echo "0")

    if [ "$DESIGN_ITEMS" -gt 0 ] || [ "$REFACTOR_ITEMS" -gt 0 ]; then
        BACKLOG_ALERT="
## Backlog Alerts

Open items requiring attention before next orchestration cycle:
- [DESIGN] items: $DESIGN_ITEMS
- [REFACTOR] items: $REFACTOR_ITEMS

Run /review or inspect plans/backlog.md for details.
"
    fi
fi

# --- Determine next workflow suggestion ---
suggest_next_workflow() {
    # Escalation blocks everything
    if [ -f "$ESCALATION_FLAG" ]; then
        echo "Review .iocane/escalation.log, then clear .iocane/escalation.flag before proceeding."
        return
    fi

    # No plan.md yet
    if [ ! -f "$PLAN_FILE" ]; then
        if [ ! -f "plans/PRD.md" ]; then
            echo "No PRD found. Start with /brainstorm or create plans/PRD.md, then run /io-clarify."
            return
        fi
        # Check Clarified stamp before suggesting downstream workflows
        if ! grep -q "Clarified: True" "plans/PRD.md" 2>/dev/null; then
            echo "PRD present but not clarified. Run /io-clarify to resolve ambiguities and stamp Clarified: True."
            return
        fi
        if [ ! -f "plans/roadmap.md" ]; then
            echo "PRD clarified. Run /io-specify to generate roadmap.md."
        elif [ ! -f "plans/project-spec.md" ] || [ ! -d "interfaces" ]; then
            echo "Roadmap present but contracts not locked. Run /io-architect."
        else
            echo "Contracts locked but no checkpoint plan. Run /io-checkpoint."
        fi
        return
    fi

    # Backlog blocks new orchestration
    if [ "$DESIGN_ITEMS" -gt 0 ] 2>/dev/null; then
        echo "Open [DESIGN] backlog items exist. Run /io-architect to resolve before orchestrating."
        return
    fi

    # Check if task files exist but haven't been dispatched yet
    MISSING=$(ls "$TASKS_DIR"/*.md 2>/dev/null | while read f; do
        CP_ID=$(basename "$f" .md)
        if [ ! -f "$TASKS_DIR/$CP_ID.status" ]; then
            echo "$CP_ID"
        fi
    done | grep -v "^$" || echo "")

    if [ -n "$MISSING" ]; then
        echo "Task files ready but not yet dispatched. Run: uv run bash .claude/scripts/dispatch-agents.sh"
        return
    fi

    # All checkpoints complete — ready for review or next feature
    if [ -n "$PENDING_CHECKPOINTS" ] && [ "$PENDING_CHECKPOINTS" != "none" ]; then
        echo "Unblocked checkpoints available. Run /io-orchestrate to generate next batch."
    else
        echo "All checkpoints complete. Run /review, then /gap-analysis, then /doc-sync."
    fi
}

NEXT_STEP=$(suggest_next_workflow)

# --- Assemble briefing ---
BRIEFING="# Iocane Session Briefing

${ESCALATION_ALERT}
## Active Checkpoint
${ACTIVE_CHECKPOINT:-No active checkpoint detected.}

## Pending Checkpoints
${PENDING_CHECKPOINTS:-none}

## Last Completed
${LAST_COMPLETED:-none}

$([ -n "$RECENT_FAILURES" ] && echo "## Recent Failures
$RECENT_FAILURES
" || echo "")
${BACKLOG_ALERT}
## Suggested Next Step
$NEXT_STEP

---
Workflow reference: .claude/commands/
Rules reference: .claude/rules/
"

output_json "$BRIEFING"

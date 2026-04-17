#!/usr/bin/env bash
# SessionStart hook: orient Claude at the start of every session.
#
# Reads plan.yaml, plans/tasks/, and backlog.yaml to determine project state.
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

Read the log and resolve before running dispatch-agents.sh again.
Clear $ESCALATION_FLAG after review to re-enable dispatch.
"
fi

# --- Review-pending check ---
REVIEW_PENDING_ALERT=""
if [ -f ".iocane/review-pending.json" ]; then
    PENDING_CPS=$(uv run python -c "
import json
try:
    d = json.load(open('.iocane/review-pending.json', encoding='utf-8'))
    print(','.join(d.get('cp_ids') or []))
except Exception:
    pass
" 2>/dev/null || true)
    REVIEW_PENDING_ALERT="
## REVIEW PENDING APPROVAL

Review completed but archival not yet approved for: ${PENDING_CPS}
Return to /io-review Step J to archive or escalate.
"
fi

# --- Read plan.yaml for checkpoint status ---
PLAN_FILE="plans/plan.yaml"
ACTIVE_CHECKPOINT=""
PENDING_CHECKPOINTS=""
COMPLETED_CHECKPOINTS=""
VALIDATED=""
HAS_COMPLETE=""

if [ -f "$PLAN_FILE" ]; then
    eval "$(uv run python -c "
import sys
sys.path.insert(0, '.claude/scripts')
from plan_parser import (
    load_plan, pending_checkpoints, completed_checkpoints, in_progress_checkpoints,
)
plan = load_plan('plans/plan.yaml')
pend = pending_checkpoints(plan)
comp = completed_checkpoints(plan)
prog = in_progress_checkpoints(plan)
pend_str = '\n'.join(f'{cp.id}: {cp.title}' for cp in pend) or 'none'
comp_str = '\n'.join(f'{cp.id}: {cp.title}' for cp in comp) or 'none'
active = ''
if prog:
    active = f'{prog[0].id}: {prog[0].title}'
elif pend:
    active = f'{pend[0].id}: {pend[0].title}'
validated_str = 'true' if plan.validated else ''
has_complete_str = 'true' if comp else ''
print(f'PENDING_CHECKPOINTS=\"{pend_str}\"')
print(f'COMPLETED_CHECKPOINTS=\"{comp_str}\"')
print(f'ACTIVE_CHECKPOINT=\"{active}\"')
print(f'VALIDATED=\"{validated_str}\"')
print(f'HAS_COMPLETE=\"{has_complete_str}\"')
" 2>/dev/null)" || {
        PENDING_CHECKPOINTS="none"
        COMPLETED_CHECKPOINTS="none"
        ACTIVE_CHECKPOINT=""
        VALIDATED=""
        HAS_COMPLETE=""
    }
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

# --- Read backlog.yaml for open items ---
BACKLOG_FILE="plans/backlog.yaml"
BACKLOG_ALERT=""
DESIGN_ITEMS=""
REFACTOR_ITEMS=""

if [ -f "$BACKLOG_FILE" ]; then
    COUNTS=$(uv run python -c "
import sys
sys.path.insert(0, '.claude/scripts')
from backlog_parser import load_backlog, items_by_tag, open_items
backlog = load_backlog('plans/backlog.yaml')
opened = open_items(backlog)
design = sum(1 for i in opened if i.tag.value == 'DESIGN')
refactor = sum(1 for i in opened if i.tag.value == 'REFACTOR')
print(f'{design} {refactor}')
" 2>/dev/null || echo "0 0")
    DESIGN_ITEMS=$(echo "$COUNTS" | awk '{print $1}')
    REFACTOR_ITEMS=$(echo "$COUNTS" | awk '{print $2}')

    if [ "$DESIGN_ITEMS" -gt 0 ] || [ "$REFACTOR_ITEMS" -gt 0 ]; then
        BACKLOG_ALERT="
## Backlog Alerts

Open items requiring attention before next orchestration cycle:
- [DESIGN] items: $DESIGN_ITEMS
- [REFACTOR] items: $REFACTOR_ITEMS

Run /io-review or inspect plans/backlog.yaml for details.
"
    fi
fi

# --- Bootstrap workflow-state.json from current artifacts ---
# Derives initial state so the write gate is active from session start.
# Subsequent PostToolUse hooks will update state as artifacts change.
derive_workflow_state() {
    local STATE_FILE=".iocane/workflow-state.json"
    local TIMESTAMP
    TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date +"%Y-%m-%dT%H:%M:%SZ")

    # Escalation flag takes priority
    if [ -f "$ESCALATION_FLAG" ]; then
        # Read existing next state if available, preserve it under escalation
        local EXISTING_NEXT=""
        if [ -f "$STATE_FILE" ]; then
            EXISTING_NEXT=$(uv run python -c "
import json
try:
    d = json.load(open('$STATE_FILE', encoding='utf-8'))
    print(d.get('next') or '')
except Exception:
    pass
" 2>/dev/null || true)
        fi
        printf '{"next":"%s","trigger":"escalation.flag exists at session boot","escalation":true,"timestamp":"%s"}\n' \
            "${EXISTING_NEXT:-unknown}" "$TIMESTAMP" > "$STATE_FILE"
        return
    fi

    # Review-pending: review completed but human has not approved archival
    if [ -f ".iocane/review-pending.json" ]; then
        local PENDING_CPS
        PENDING_CPS=$(uv run python -c "
import json
try:
    d = json.load(open('.iocane/review-pending.json', encoding='utf-8'))
    print(','.join(d.get('cp_ids') or []))
except Exception:
    pass
" 2>/dev/null || true)
        printf '{"next":"io-review","trigger":"review-pending.json exists (pending approval: %s)","review_pending":true,"timestamp":"%s"}\n' \
            "$PENDING_CPS" "$TIMESTAMP" > "$STATE_FILE"
        return
    fi

    # No plan.yaml -> early workflow stages
    if [ ! -f "$PLAN_FILE" ]; then
        if [ -f "plans/project-spec.md" ]; then
            if grep -q '\*\*Approved:\*\* True' "plans/project-spec.md" 2>/dev/null; then
                printf '{"next":"io-checkpoint","trigger":"session-start (project-spec approved, no plan)","timestamp":"%s"}\n' \
                    "$TIMESTAMP" > "$STATE_FILE"
            else
                printf '{"next":"io-architect","trigger":"session-start (project-spec not approved)","timestamp":"%s"}\n' \
                    "$TIMESTAMP" > "$STATE_FILE"
            fi
        fi
        # No project-spec = too early for state enforcement
        return
    fi

    # plan.yaml exists -> VALIDATED and HAS_COMPLETE come from the
    # top-level python block (script-scope), which uses plan_parser.load_plan
    # for structural correctness under `set -euo pipefail`.

    # Check for pending task files (ready for validate-tasks or dispatch)
    local HAS_TASK_FILES=""
    local HAS_VALIDATION_SENTINELS=""
    if [ -d "$TASKS_DIR" ]; then
        HAS_TASK_FILES=$(ls "$TASKS_DIR"/CP-*.yaml 2>/dev/null | head -1)
        HAS_VALIDATION_SENTINELS=$(ls "$TASKS_DIR"/*.task.validation 2>/dev/null | head -1)
    fi

    if [ -n "$HAS_VALIDATION_SENTINELS" ]; then
        printf '{"next":"dispatch","trigger":"session-start (validated task files present)","timestamp":"%s"}\n' \
            "$TIMESTAMP" > "$STATE_FILE"
    elif [ -n "$HAS_TASK_FILES" ]; then
        printf '{"next":"validate-tasks","trigger":"session-start (task files present, not validated)","timestamp":"%s"}\n' \
            "$TIMESTAMP" > "$STATE_FILE"
    elif [ -n "$HAS_COMPLETE" ]; then
        printf '{"next":"io-review","trigger":"session-start (completed CPs in plan)","timestamp":"%s"}\n' \
            "$TIMESTAMP" > "$STATE_FILE"
    elif [ -n "$VALIDATED" ]; then
        printf '{"next":"io-plan-batch","trigger":"session-start (plan validated)","timestamp":"%s"}\n' \
            "$TIMESTAMP" > "$STATE_FILE"
    else
        printf '{"next":"validate-plan","trigger":"session-start (plan not validated)","timestamp":"%s"}\n' \
            "$TIMESTAMP" > "$STATE_FILE"
    fi
}

derive_workflow_state

# --- Determine next workflow suggestion ---
suggest_next_workflow() {
    # Escalation blocks everything
    if [ -f "$ESCALATION_FLAG" ]; then
        echo "Review .iocane/escalation.log, then clear .iocane/escalation.flag before proceeding."
        return
    fi

    # Review completed but not yet approved
    if [ -f ".iocane/review-pending.json" ]; then
        PENDING_CPS=$(uv run python -c "
import json
try:
    d = json.load(open('.iocane/review-pending.json', encoding='utf-8'))
    print(','.join(d.get('cp_ids') or []))
except Exception:
    pass
" 2>/dev/null || true)
        echo "Review completed but approval pending for: $PENDING_CPS. Present /io-review Step J summary to approve archival or escalate."
        return
    fi

    # No plan.yaml yet
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
    MISSING=$(ls "$TASKS_DIR"/CP-*.yaml 2>/dev/null | while read f; do
        CP_ID=$(basename "$f" .yaml)
        if [ ! -f "$TASKS_DIR/$CP_ID.status" ]; then
            echo "$CP_ID"
        fi
    done | grep -v "^$" || echo "")

    if [ -n "$MISSING" ]; then
        echo "Task files ready but not yet validated. Run /validate-tasks, then bash .claude/scripts/dispatch-agents.sh"
        return
    fi

    # All checkpoints complete — ready for review or next feature
    if [ -n "$PENDING_CHECKPOINTS" ] && [ "$PENDING_CHECKPOINTS" != "none" ]; then
        echo "Unblocked checkpoints available. Run /io-plan-batch then /validate-tasks then dispatch-agents.sh for next batch."
    else
        echo "All checkpoints complete. Run /io-review, then /gap-analysis, then /doc-sync."
    fi
}

NEXT_STEP=$(suggest_next_workflow)

# --- Role-aware orientation (Phase 3) ---
# spawn-{tester,...}.sh dispatches a claude -p session with IOCANE_ROLE
# set. SessionStart fires for that new process -- inject role-scoped
# orientation so the dispatched agent reads its write scope and AMEND
# protocol without relying on inherited context. Unset IOCANE_ROLE =
# interactive session; falls through to the generic briefing.
ROLE_BLOCK=""
if [ -n "${IOCANE_ROLE:-}" ]; then
    case "$IOCANE_ROLE" in
        tester)
            ROLE_BLOCK="
## ROLE: Test Author (Tier 1)

You are dispatched as the Tier-1 Test Author for Protocol \`${IOCANE_PROTOCOL:-unknown}\`
(at \`interfaces/${IOCANE_PROTOCOL:-*}.pyi\`).

- Read ONLY: interfaces/*.pyi, plans/test-plan.yaml, plans/symbols.yaml, plans/component-contracts.yaml
- Write ONLY: tests/contracts/test_${IOCANE_PROTOCOL:-*}.py OR .iocane/amend-signals/${IOCANE_PROTOCOL:-*}.yaml
- NEVER edit interfaces/*.pyi, plans/symbols.yaml, plans/test-plan.yaml (architect-owned -- reset hooks will fire)
- If the Protocol is silent on a test-plan invariant, emit an AMEND signal (per AmendSignalFile schema) and terminate without writing tests. Under-specification is a real signal, not a failure.

Workflow: .claude/commands/io-test-author.md
"
            ;;
        ct_author)
            # Derive source-Protocol manifest: for each CT where
            # target_cp == IOCANE_CP_ID, collect every source
            # Protocol via plan.yaml.connectivity_tests[*].contract_under_test.
            # Inject as a bulleted list in the role block so the
            # agent doesn't have to re-derive mid-session.
            #
            # contract_under_test supports comma-separated multi-Protocol
            # entries (e.g., "interfaces/a.pyi :: A, interfaces/b.pyi :: B").
            # Parser mirrors check_ct_completeness.py:33-36 -- split on
            # comma first, then `::`, collect the left side. A naive
            # `split('::')[0]` would drop all but the first Protocol.
            SOURCE_PROTOCOLS=$(uv run python -c "
import sys; sys.path.insert(0, '.claude/scripts')
from plan_parser import load_plan
plan = load_plan('plans/plan.yaml')
cts = [ct for ct in plan.connectivity_tests if ct.target_cp == '${IOCANE_CP_ID:-}']
protos = set()
for ct in cts:
    for segment in ct.contract_under_test.split(','):
        before_colons = segment.split('::')[0].strip()
        if before_colons:
            protos.add(before_colons)
for p in sorted(protos): print(f'  - {p}')
" 2>/dev/null || echo "  - (derivation failed; inspect plans/plan.yaml manually)")

            ROLE_BLOCK="
## ROLE: CT Author (Tier 3a)

You are dispatched as the Tier-3a CT Author for checkpoint \`${IOCANE_CP_ID:-unknown}\`.

Write every connectivity test whose target_cp == ${IOCANE_CP_ID:-unknown}.
The target CP's impl does not exist yet -- CTs will fail by design
once written. The generator stage takes them RED to GREEN.

### Source Protocols for this CP's CTs
${SOURCE_PROTOCOLS}

### Read scope (never edit)
- plans/tasks/${IOCANE_CP_ID:-*}.yaml (your task file)
- plans/plan.yaml (CT signatures)
- plans/seams.yaml (fixture wiring hints)
- plans/symbols.yaml (exception + type registry)
- interfaces/*.pyi (Protocol definitions -- for \`spec=\` type hints)
- tests/contracts/*.py (existing import patterns -- read-only)

### Write scope (only paths listed in task.connectivity_tests[].file)
- tests/connectivity/*.py

### Never-edit (triggers reset hooks; breaks architect blessing during parallel dispatch)
- interfaces/*.pyi
- plans/*.yaml
- tests/contracts/*

### Do NOT
- Run CT gates -- impl does not exist yet; gates will fail by design.
- Create skeleton impl in src/ to silence import errors -- preflight will misdiagnose this as impl-leaked.
- Emit AMEND signals -- on CT spec ambiguity, HALT with structured error (per D16).

Workflow: .claude/commands/io-ct-author.md
Rules reference: .claude/skills/test-writer/references/ct-author-rules.md
"
            ;;
        *) ROLE_BLOCK="" ;;
    esac
fi

# --- Assemble briefing ---
BRIEFING="# Iocane Session Briefing

${ESCALATION_ALERT}
${REVIEW_PENDING_ALERT}
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
${ROLE_BLOCK}
---
Workflow reference: .claude/commands/
Rules reference: .claude/rules/
"

output_json "$BRIEFING"

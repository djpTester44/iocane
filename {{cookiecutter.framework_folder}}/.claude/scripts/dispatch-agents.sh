#!/usr/bin/env bash
# .claude/scripts/dispatch-agents.sh
#
# Owns the full batch lifecycle for sub-agent execution:
#   1. Scans plans/tasks/ for pending CP-XX.yaml files (no matching .status)
#   2. Enforces parallel.limit from .claude/iocane.config.yaml
#   3. Per checkpoint (in parallel up to limit):
#      a. Sets up isolated git worktree via setup-worktree.sh
#      b. Runs baseline test preflight (pytest -x)
#      c. Dispatches generator agent via claude -p (io-execute)
#      d. Dispatches evaluator agent via claude -p (io-evaluator-dispatch)
#      e. On MECHANICAL_FAIL: resets checkboxes, retries generator with eval findings (up to eval_max_retries)
#      f. On DESIGN_FAIL: escalates immediately, no retry
#      g. On evaluator crash/timeout: honors generator PASS, marks EVAL_SKIPPED
#   4. Merges PASS checkpoints, preserves FAIL worktrees
#   5. Reports batch summary
#
# Intermediate commits: The generator commits in Step G. On regen, additional commits
# accumulate on the worktree branch. All commits enter the parent branch via --no-ff merge.
# This is intentional -- intermediate commits have forensic value.
#
# Usage:
#   bash .claude/scripts/dispatch-agents.sh [--resume CP-XX]
#
# Environment (all optional, override config when config is absent):
#   IOCANE_PARALLEL_LIMIT  -- max concurrent agents (fallback when config unreadable)
#   IOCANE_MODEL           -- claude model string (fallback when config unreadable)
#   IOCANE_TIMEOUT         -- per-agent timeout (default: 10m)
#   IOCANE_MAX_TURNS       -- max agent turns (default: 20)
#   IOCANE_EVAL_MODEL      -- evaluator model (default: models.tier2)
#   IOCANE_EVAL_TIMEOUT    -- evaluator timeout (default: 5m)
#   IOCANE_EVAL_MAX_TURNS  -- evaluator turn budget (default: 20)
#   IOCANE_EVAL_MAX_RETRIES -- max regen cycles (default: 2)
#   REPO_ROOT              -- auto-detected via git if not set

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- Argument parsing ---
RESUME_CP=""
while [ $# -gt 0 ]; do
    case "$1" in
        --resume)
            if [ -z "${2:-}" ]; then
                echo "ERROR: --resume requires a checkpoint ID (e.g., --resume CP-01)" >&2
                exit 1
            fi
            RESUME_CP="$2"
            shift 2
            ;;
        *)
            echo "ERROR: Unknown argument: $1" >&2
            echo "Usage: bash .claude/scripts/dispatch-agents.sh [--resume CP-XX]" >&2
            exit 1
            ;;
    esac
done

# --- Configuration ---
REPO_ROOT="${REPO_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null)}"
CONFIG_FILE="$REPO_ROOT/.claude/iocane.config.yaml"

# _cfg_read: extract section.key value from YAML config (awk-based, no external deps)
# Usage: _cfg_read "parallel.limit"
# Handles multi-key sections and strips inline comments.
_cfg_read() {
    local key="$1"
    local section="${key%%.*}"
    local subkey="${key#*.}"
    awk "/^${section}:/{found=1; next} found && /^[^ ]/{exit} found && /^  ${subkey}:/{print; exit}" "$CONFIG_FILE" 2>/dev/null \
        | sed 's/^[^:]*:[[:space:]]*//' \
        | sed 's/[[:space:]]*#.*//' \
        | tr -d '\r' \
        | head -1
}

# Read parallel.limit: config -> IOCANE_PARALLEL_LIMIT env -> default 1
_cfg_parallel=$(_cfg_read "parallel.limit")
if [ -n "$_cfg_parallel" ] && [ "$_cfg_parallel" != "null" ]; then
    PARALLEL_LIMIT="$_cfg_parallel"
    PARALLEL_SOURCE="config"
elif [ -n "${IOCANE_PARALLEL_LIMIT:-}" ]; then
    PARALLEL_LIMIT="$IOCANE_PARALLEL_LIMIT"
    PARALLEL_SOURCE="env"
else
    PARALLEL_LIMIT="1"
    PARALLEL_SOURCE="default"
fi

# Read agents.max_turns: config -> IOCANE_MAX_TURNS env -> default 50
_cfg_max_turns=$(_cfg_read "agents.max_turns")
if [ -n "$_cfg_max_turns" ] && [ "$_cfg_max_turns" != "null" ]; then
    MAX_TURNS="${IOCANE_MAX_TURNS:-$_cfg_max_turns}"
else
    MAX_TURNS="${IOCANE_MAX_TURNS:-50}"
fi

# Read agents.timeout: config -> IOCANE_TIMEOUT env -> default 10m
_cfg_timeout=$(_cfg_read "agents.timeout")
if [ -n "$_cfg_timeout" ] && [ "$_cfg_timeout" != "null" ]; then
    AGENT_TIMEOUT="${IOCANE_TIMEOUT:-$_cfg_timeout}"
else
    AGENT_TIMEOUT="${IOCANE_TIMEOUT:-10m}"
fi

# Read models.tier3: config -> IOCANE_MODEL env -> hard default
_cfg_model=$(_cfg_read "models.tier3")
if [ -n "$_cfg_model" ] && [ "$_cfg_model" != "null" ]; then
    MODEL="${IOCANE_MODEL:-$_cfg_model}"
else
    MODEL="${IOCANE_MODEL:-claude-haiku-4-5-20251001}"
fi

# Read evaluator config
EVAL_MODEL="${IOCANE_EVAL_MODEL:-$(_cfg_read "models.tier2")}"
EVAL_MODEL="${EVAL_MODEL:-claude-sonnet-4-6}"
_cfg_eval_turns=$(_cfg_read "agents.eval_max_turns")
EVAL_MAX_TURNS="${IOCANE_EVAL_MAX_TURNS:-${_cfg_eval_turns:-20}}"
_cfg_eval_timeout=$(_cfg_read "agents.eval_timeout")
EVAL_TIMEOUT="${IOCANE_EVAL_TIMEOUT:-${_cfg_eval_timeout:-5m}}"
_cfg_eval_retries=$(_cfg_read "agents.eval_max_retries")
EVAL_MAX_RETRIES="${IOCANE_EVAL_MAX_RETRIES:-${_cfg_eval_retries:-2}}"

TASKS_DIR="$REPO_ROOT/plans/tasks"

if [ -z "$REPO_ROOT" ]; then
    echo "ERROR: Could not determine repo root. Are you inside a git repository?" >&2
    exit 1
fi

# --- Escalation flag gate (skipped in resume mode) ---
if [ -z "$RESUME_CP" ]; then
    # A previous batch had sub-agent failures. Resolve before dispatching again.
    ESCALATION_FLAG="$REPO_ROOT/.iocane/escalation.flag"
    if [ -f "$ESCALATION_FLAG" ]; then
        echo "ERROR: Escalation flag is set. One or more sub-agents failed in the previous batch." >&2
        echo "       Review $REPO_ROOT/.iocane/escalation.log and clear $ESCALATION_FLAG after resolution." >&2
        exit 1
    fi

    # --- Clean-tree gate ---
    # Worktrees branch from HEAD; uncommitted changes won't propagate to sub-agents.
    if ! git -C "$REPO_ROOT" diff --quiet HEAD 2>/dev/null || \
       ! git -C "$REPO_ROOT" diff --cached --quiet HEAD 2>/dev/null || \
       [ -n "$(git -C "$REPO_ROOT" ls-files --others --exclude-standard 2>/dev/null)" ]; then
        echo "ERROR: Working tree is not clean. Commit or stash changes before dispatching." >&2
        echo "       Worktrees branch from HEAD — uncommitted changes will not reach sub-agents." >&2
        git -C "$REPO_ROOT" status --short >&2
        exit 1
    fi
fi

# --- Dependency gate: pytest-timeout ---
# The preflight uses --timeout=60 which requires pytest-timeout.
# Fail early with an actionable message rather than per-checkpoint PREFLIGHT_FAIL.
if ! uv run python -c "import pytest_timeout" 2>/dev/null; then
    echo "ERROR: pytest-timeout is not installed but is required for preflight test timeouts." >&2
    echo "       Run: uv add --dev pytest-timeout" >&2
    exit 1
fi

# --- Resume validation ---
if [ -n "$RESUME_CP" ]; then
    RESUME_WT="$REPO_ROOT/.worktrees/$RESUME_CP"
    if [ ! -d "$RESUME_WT" ]; then
        echo "ERROR: Worktree not found at $RESUME_WT" >&2
        exit 1
    fi
    RESUME_BRANCH=$(git -C "$RESUME_WT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
    if [ "$RESUME_BRANCH" != "iocane/$RESUME_CP" ]; then
        echo "ERROR: Worktree at $RESUME_WT is on branch '$RESUME_BRANCH', expected 'iocane/$RESUME_CP'" >&2
        exit 1
    fi
    if [ ! -f "$RESUME_WT/plans/tasks/$RESUME_CP.yaml" ]; then
        echo "ERROR: Task file not found at $RESUME_WT/plans/tasks/$RESUME_CP.yaml" >&2
        exit 1
    fi
    # Clear stale status/exit files so post-pipeline collection works
    rm -f "$TASKS_DIR/$RESUME_CP.status" "$TASKS_DIR/$RESUME_CP.exit"
    # Insert resume marker into log
    echo "--- RESUME at $(date -u '+%Y-%m-%dT%H:%M:%SZ') ---" >> "$TASKS_DIR/$RESUME_CP.log"
    # Sync dependencies in case they drifted
    (cd "$RESUME_WT" && uv sync --quiet 2>/dev/null) || true
fi

# Capture the branch that was checked out when the user ran this script.
# Completed checkpoint branches are merged back here on PASS.
PARENT_BRANCH=$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD)

if [ -z "$RESUME_CP" ]; then
    # --- Collect pending task files ---
    # A task file is pending if CP-XX.yaml exists but CP-XX.status does not.
    PENDING=()

    for task_file in "$TASKS_DIR"/CP-*.yaml; do
        [ -f "$task_file" ] || continue
        CP_ID=$(basename "$task_file" .yaml)
        STATUS_FILE="$TASKS_DIR/$CP_ID.status"
        if [ ! -f "$STATUS_FILE" ]; then
            if [ ! -f "$TASKS_DIR/$CP_ID.task.validation" ]; then
                echo "SKIPPED: $CP_ID -- not validated. Run /validate-tasks first." >&2
                continue
            fi
            PENDING+=("$CP_ID")
        fi
    done

    if [ ${#PENDING[@]} -eq 0 ]; then
        echo "No pending task files found in $TASKS_DIR."
        echo "Run the task generation workflow to create task files before dispatching."
        exit 0
    fi

    # --- Audit commit: validation state before dispatch ---
    git -C "$REPO_ROOT" add plans/validation-reports/task-validation-report.yaml 2>/dev/null || true
    git -C "$REPO_ROOT" commit -m "validate-tasks: batch validated before dispatch" --allow-empty 2>/dev/null || true

    echo "Pending checkpoints: ${PENDING[*]}"
    echo "Parallel limit: $PARALLEL_LIMIT (source: $PARALLEL_SOURCE)"

    # --- Enforce parallel limit ---
    BATCH=("${PENDING[@]:0:$PARALLEL_LIMIT}")

    if [ ${#PENDING[@]} -gt "$PARALLEL_LIMIT" ]; then
        echo "NOTE: ${#PENDING[@]} pending checkpoints found, dispatching first $PARALLEL_LIMIT per parallel.limit in .claude/iocane.config.yaml."
        echo "Remaining: ${PENDING[@]:$PARALLEL_LIMIT}"
    fi

    # --- CI Sidecar: pre-wave baseline ---
    if [ -f "$SCRIPT_DIR/ci-sidecar.sh" ]; then
        echo "[CI-SIDECAR] Capturing pre-wave test baseline..."
        bash "$SCRIPT_DIR/ci-sidecar.sh" pre-wave || \
            echo "[CI-COLLECTION-ERROR] Pre-wave sidecar failed (exit $?). Continuing dispatch." >&2
    fi

    echo ""
    echo "Dispatching ${#BATCH[@]} sub-agents..."
fi

# --- Pipeline function: generate-evaluate-regen per checkpoint ---
run_checkpoint_pipeline() {
    local CP_ID="$1"
    local IS_RESUME="${2:-}"
    local WORKTREE_PATH="$REPO_ROOT/.worktrees/$CP_ID"
    local RESULT_FILE="$TASKS_DIR/$CP_ID.result.json"
    local EVAL_FILE="$TASKS_DIR/$CP_ID.eval.json"
    local LOG_FILE="$TASKS_DIR/$CP_ID.log"
    local EXIT_FILE="$TASKS_DIR/$CP_ID.exit"
    local STATUS_FILE="$TASKS_DIR/$CP_ID.status"

    # --- Phase 1: Worktree Setup (fresh only) ---
    if [ -z "$IS_RESUME" ]; then
        bash "$SCRIPT_DIR/setup-worktree.sh" --cp "$CP_ID"
    fi

    # --- Enter worktree (exists for both paths at this point) ---
    cd "$WORKTREE_PATH" || {
        echo "FATAL: Cannot enter worktree $WORKTREE_PATH" >&2
        bash "$REPO_ROOT/.claude/scripts/write-status.sh" "$CP_ID" "WORKTREE_CD_FAIL"
        echo "1" > "$EXIT_FILE"
        return 1
    }

    # --- Phase 2: Preflight (fresh only, scoped to checkpoint CTs) ---
    # Only verify this checkpoint's connectivity tests are not already passing.
    # Full suite regression detection is the CI sidecar's job (BL-001).
    if [ -z "$IS_RESUME" ]; then
        # Extract CT file paths from the task file via task_parser
        CT_FILES=()
        while IFS= read -r ct_path; do
            [[ -n "$ct_path" ]] && CT_FILES+=("$ct_path")
        done < <(uv run python -c "
import sys; sys.path.insert(0, '.claude/scripts')
from task_parser import load_task, extract_ct_files
for f in extract_ct_files(load_task('$TASKS_DIR/$CP_ID.yaml')):
    print(f)
" 2>/dev/null)

        for ct_file in "${CT_FILES[@]}"; do
            if [ -f "$ct_file" ]; then
                # Simple runtime symptom check: if a pre-existing CT
                # file passes pytest before the generator runs, impl
                # leaked somewhere (or a prior run's state is stale).
                # Identity-CT escape -- a structural defect where the
                # CT body never exercises the target -- is caught
                # post-ct_author via symbol_tracer AST analysis in
                # Phase 2A, not here (see Fix #4 in Phase 4 /challenge).
                if uv run rtk pytest -x --timeout=60 "$ct_file" >> "$LOG_FILE" 2>&1; then
                    bash "$REPO_ROOT/.claude/scripts/write-status.sh" "$CP_ID" \
                        "PREFLIGHT_FAIL: CT $ct_file already passes before generation"
                    echo "1" > "$EXIT_FILE"
                    return 1
                fi
                # CT exists and fails -- expected RED state, proceed
            fi
            # CT file doesn't exist -- expected (ct_author stage will create it), proceed
        done
    fi

    # --- Phase 2A: CT-Writer (fresh only; skips if no target_cp CTs) ---
    # Per D1: CT authorship is hoisted out of io-execute into a
    # separate per-CP stage that runs before the generator. CT
    # signatures are pinned at io-plan-batch time; the test body
    # still has semantic freedom. An agent writing both the CT and
    # the impl converges them on whatever passes -- the same
    # independence principle that justifies Tier-1 Test Author.
    # Skipped on resume (CT files were written in the original run
    # and now live in git) and skipped cleanly when the task has
    # zero target_cp CTs.
    if [ -z "$IS_RESUME" ]; then
        CT_COUNT=$(uv run python -c "
import sys; sys.path.insert(0, '.claude/scripts')
from task_parser import load_task
t = load_task('plans/tasks/${CP_ID}.yaml')
print(len(t.connectivity_tests))
" 2>/dev/null || echo "0")
        # Bounds-validate the int in case uv stdout contamination
        # (lockfile syncs, warnings) slipped through the 2>/dev/null.
        [[ "$CT_COUNT" =~ ^[0-9]+$ ]] || CT_COUNT=0

        if [ "$CT_COUNT" -gt 0 ]; then
            # Errexit-safe exit capture: under `set -euo pipefail` a
            # non-zero exit from a plain command aborts the shell
            # before $? can be read (Phase 4 /challenge Fix #1).
            # Wrapping in `if` makes the call errexit-exempt by design.
            if bash "$REPO_ROOT/.claude/scripts/spawn-ct-writer.sh" --cp-id "$CP_ID" \
                    >> "$LOG_FILE" 2>&1; then
                echo "[CT_WRITER] $CP_ID: ct_author exited 0" >> "$LOG_FILE"
            else
                CT_EXIT=$?
                echo "CT_FAIL: ${CP_ID} -- ct_author exited $CT_EXIT" > "$STATUS_FILE"
                echo "1" > "$EXIT_FILE"
                echo "[CT_WRITER] $CP_ID: failed (exit $CT_EXIT)" >> "$LOG_FILE"
                return 1
            fi

            # Post-ct_author: identity-CT escape check via AST import
            # analysis (Fix #4). Every CT file MUST import from src.*;
            # an identity-CT body that only references mock fixtures
            # without exercising the target passes pytest vacuously
            # and would fool downstream preflight on subsequent runs.
            # Catch the structural defect here, before the generator
            # runs, close to where it was introduced.
            if ! CT_POST_CHECK=$(uv run python -c "
import sys
sys.path.insert(0, '.claude/scripts')
sys.path.insert(0, '.claude/skills/symbol-tracer/scripts')
from pathlib import Path
from task_parser import load_task, extract_ct_files
from symbol_tracer import search_file

task = load_task('plans/tasks/${CP_ID}.yaml')
failures = []
for ct_file in extract_ct_files(task):
    p = Path(ct_file)
    if not p.exists():
        failures.append(f'{ct_file} (not written by ct_author)')
        continue
    results = search_file(p, symbol='', imports_from_prefix='src')
    if not results:
        failures.append(f'{ct_file} (no src.* import -- identity-CT escape)')

if failures:
    print(' | '.join(failures))
    sys.exit(1)
" 2>>"$LOG_FILE"); then
                echo "CT_FAIL: ${CP_ID} -- ${CT_POST_CHECK}" > "$STATUS_FILE"
                echo "1" > "$EXIT_FILE"
                echo "[CT_WRITER] $CP_ID: post-check failed: ${CT_POST_CHECK}" >> "$LOG_FILE"
                return 1
            fi

            echo "[CT_WRITER] $CP_ID: PASS (${CT_COUNT} CTs written; src.* import check passed)" >> "$LOG_FILE"
        else
            echo "[CT_WRITER] $CP_ID: SKIP (no target_cp CTs)" >> "$LOG_FILE"
        fi
    fi

    # --- Phase 3: Generate-Evaluate-Regen Loop ---
    local ATTEMPT=0
    local MAX_CYCLES=$((EVAL_MAX_RETRIES + 1))  # initial + retries

    while [ "$ATTEMPT" -lt "$MAX_CYCLES" ]; do
        ATTEMPT=$((ATTEMPT + 1))

        # Track attempts in .iocane for observability
        mkdir -p "$REPO_ROOT/.iocane"
        echo "$ATTEMPT" > "$REPO_ROOT/.iocane/$CP_ID.attempts"

        # --- Checkpoint reset for regen ---
        if [ "$ATTEMPT" -gt 1 ]; then
            # Reset step progress so regen agent starts from Step B
            uv run python -c "
import sys; sys.path.insert(0, '.claude/scripts')
from task_parser import load_task, reset_step_progress, save_task
p = '$WORKTREE_PATH/plans/tasks/$CP_ID.yaml'
save_task(p, reset_step_progress(load_task(p)))
"
            echo "[REGEN] $CP_ID: reset step progress for attempt $ATTEMPT" >> "$LOG_FILE"
        fi

        # --- Generator (or Regen) ---
        local GEN_PROMPT
        if [ "$ATTEMPT" -eq 1 ]; then
            GEN_PROMPT="Read and execute the workflow defined in .claude/commands/io-execute.md. Your task file is plans/tasks/${CP_ID}.yaml. Follow every step exactly. Terminate after writing the status file."
        else
            # Regen: include eval findings as negative constraints
            local REGEN_HINT
            REGEN_HINT=$(uv run python -c "
import json, sys
try:
    d = json.load(open('$EVAL_FILE'))
    hint = d.get('regen_hint', '')
    print(hint if hint and hint != 'null' else '')
except: print('')
" 2>/dev/null) || true
            GEN_PROMPT="Read and execute the workflow defined in .claude/commands/io-execute.md. Your task file is plans/tasks/${CP_ID}.yaml. This is retry attempt $ATTEMPT. Your previous attempt was evaluated and failed. The evaluator found these issues: ${REGEN_HINT}. Fix these specific issues. Follow every step exactly. Terminate after writing the status file."
        fi

        # Export sub-agent env vars
        export IOCANE_SUBAGENT=1
        export IOCANE_CP_ID="$CP_ID"
        export IOCANE_ATTEMPT="$ATTEMPT"
        export IOCANE_REPO_ROOT="$REPO_ROOT"
        export IOCANE_LOG_FILE="$LOG_FILE"
        export IOCANE_MODEL_NAME="$MODEL"
        unset VIRTUAL_ENV

        cd "$WORKTREE_PATH"

        # Clear previous status for retry
        rm -f "$STATUS_FILE"

        echo "$GEN_PROMPT" | timeout "$AGENT_TIMEOUT" claude -p \
            --model "$MODEL" \
            --max-turns "$MAX_TURNS" \
            --allowedTools "Bash,Read,Write,Edit" \
            --output-format json \
            > "$RESULT_FILE" 2>> "$LOG_FILE"
        local GEN_EXIT=$?

        # Check generator result
        local GEN_STATUS
        GEN_STATUS=$(cat "$STATUS_FILE" 2>/dev/null || echo "MISSING")
        if [ "$GEN_EXIT" -ne 0 ] || [ "$GEN_STATUS" != "PASS" ]; then
            echo "$GEN_EXIT" > "$EXIT_FILE"
            return "$GEN_EXIT"
        fi

        # --- Evaluator ---
        local EVAL_PROMPT="Read and execute the workflow defined in .claude/commands/io-evaluator-dispatch.md. Your task file is plans/tasks/${CP_ID}.yaml. This is evaluation of attempt $ATTEMPT. Grade the implementation. Write the eval result to $REPO_ROOT/plans/tasks/${CP_ID}.eval.json (use this exact absolute path). Terminate."

        # Clear previous eval for retry
        rm -f "$EVAL_FILE"

        echo "$EVAL_PROMPT" | timeout "$EVAL_TIMEOUT" claude -p \
            --model "$EVAL_MODEL" \
            --max-turns "$EVAL_MAX_TURNS" \
            --allowedTools "Bash,Read,Write" \
            --output-format json \
            > "$TASKS_DIR/$CP_ID.eval-result.json" 2>> "$LOG_FILE"
        local EVAL_EXIT=$?

        # --- Evaluator crash handling ---
        # If evaluator crashed or didn't write eval.json, treat as
        # evaluator infrastructure failure, not a checkpoint failure.
        # The generator already passed its own gates. Honor PASS.
        if [ "$EVAL_EXIT" -ne 0 ] || [ ! -f "$EVAL_FILE" ]; then
            echo "[EVAL_SKIP] $CP_ID attempt $ATTEMPT: evaluator exited $EVAL_EXIT or did not produce eval.json. Generator PASS honored." >> "$LOG_FILE"
            echo "0" > "$EXIT_FILE"
            echo '{"checkpoint":"'"$CP_ID"'","verdict":"EVAL_SKIPPED","reason":"evaluator_crash_or_timeout","attempt":'"$ATTEMPT"'}' > "$EVAL_FILE"
            return 0
        fi

        # --- Parse eval verdict ---
        local EVAL_VERDICT
        EVAL_VERDICT=$(uv run python -c "
import json, sys
try:
    d = json.load(open('$EVAL_FILE'))
    print(d.get('verdict', 'MISSING'))
except: print('PARSE_ERROR')
" 2>/dev/null) || true

        case "$EVAL_VERDICT" in
            PASS)
                echo "0" > "$EXIT_FILE"
                return 0
                ;;
            MECHANICAL_FAIL)
                if [ "$ATTEMPT" -lt "$MAX_CYCLES" ]; then
                    echo "[REGEN] $CP_ID attempt $ATTEMPT: MECHANICAL_FAIL, retrying ($ATTEMPT of $MAX_CYCLES)" >> "$LOG_FILE"
                    continue
                else
                    bash "$REPO_ROOT/.claude/scripts/write-status.sh" "$CP_ID" \
                        "EVAL_FAIL: MECHANICAL after $ATTEMPT attempts -- retries exhausted"
                    echo "1" > "$EXIT_FILE"
                    return 1
                fi
                ;;
            DESIGN_FAIL)
                bash "$REPO_ROOT/.claude/scripts/write-status.sh" "$CP_ID" \
                    "EVAL_FAIL: DESIGN -- requires /io-architect"
                echo "1" > "$EXIT_FILE"
                return 1
                ;;
            *)
                # Unparseable verdict -- honor generator PASS
                echo "[EVAL_SKIP] $CP_ID attempt $ATTEMPT: unparseable verdict '$EVAL_VERDICT'. Generator PASS honored." >> "$LOG_FILE"
                echo '{"checkpoint":"'"$CP_ID"'","verdict":"EVAL_SKIPPED","reason":"unparseable_verdict","raw":"'"$EVAL_VERDICT"'","attempt":'"$ATTEMPT"'}' > "$EVAL_FILE"
                echo "0" > "$EXIT_FILE"
                return 0
                ;;
        esac
    done
}

if [ -n "$RESUME_CP" ]; then
    # --- Resume single checkpoint ---
    echo "Resuming checkpoint $RESUME_CP..."
    BATCH=("$RESUME_CP")
    run_checkpoint_pipeline "$RESUME_CP" "resume"
else
    # --- Dispatch batch concurrently ---
    declare -A PIDS

    for CP_ID in "${BATCH[@]}"; do
        run_checkpoint_pipeline "$CP_ID" &
        PIDS[$CP_ID]=$!
    done

    # --- Wait for all checkpoint pipelines ---
    echo "Waiting for checkpoint pipelines..."
    for CP_ID in "${BATCH[@]}"; do
        wait "${PIDS[$CP_ID]}" || true
    done
fi

# --- Collect results, log, and clean up ---
echo ""
TOTAL=${#BATCH[@]}
FAILED=0

for CP_ID in "${BATCH[@]}"; do
    EXIT_CODE=$(cat "$TASKS_DIR/$CP_ID.exit" 2>/dev/null || echo "1")
    STATUS=$(cat "$TASKS_DIR/$CP_ID.status" 2>/dev/null || echo "MISSING")

    if [ "$EXIT_CODE" -eq 0 ] && [ "$STATUS" = "PASS" ]; then
        echo "$CP_ID: PASS"

        # --- Compensating control: flag EVAL_SKIPPED merges in backlog ---
        EVAL_VERDICT=$(uv run python -c "
import json, sys
try:
    d = json.load(open('$TASKS_DIR/$CP_ID.eval.json'))
    print(d.get('verdict', ''))
except: print('')
" 2>/dev/null) || true

        if [ "$EVAL_VERDICT" = "EVAL_SKIPPED" ]; then
            echo "$CP_ID: WARNING -- merged with EVAL_SKIPPED. Adding backlog entry for audit."
            uv run python -c "
import sys, yaml
from datetime import datetime, timezone

sys.path.insert(0, '${REPO_ROOT}/.claude/scripts')

path = '${REPO_ROOT}/plans/backlog.yaml'
try:
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
except FileNotFoundError:
    data = {'items': []}

items = data.get('items', [])
items.append({
    'id': '',
    'tag': '[TEST]',
    'severity': 'HIGH',
    'title': '$CP_ID merged with EVAL_SKIPPED -- requires manual review',
    'description': 'Evaluator timed out or crashed. Generator PASS was honored. Code merged without quality grading.',
    'routed': '',
})
data['items'] = items

with open(path, 'w', encoding='utf-8') as f:
    yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
print('$CP_ID: backlog entry written for EVAL_SKIPPED')
" 2>/dev/null || echo "$CP_ID: WARNING -- failed to write EVAL_SKIPPED backlog entry" >&2
        fi

        # Check whether the branch has any new commits to merge.
        AHEAD=$(git -C "$REPO_ROOT" rev-list --count "$PARENT_BRANCH..iocane/$CP_ID" 2>/dev/null || echo "0")
        if [ "$AHEAD" -eq 0 ]; then
            echo "$CP_ID: WARNING -- branch iocane/$CP_ID has no new commits. Sub-agent may not have committed its work. Skipping merge." >&2
        else
            git -C "$REPO_ROOT" merge "iocane/$CP_ID" --no-ff -m "Merge checkpoint $CP_ID into $PARENT_BRANCH"
            echo "$CP_ID: Merged into $PARENT_BRANCH."

            # --- Register completion in plan.yaml ---
            uv run python -c "
import sys
sys.path.insert(0, '${REPO_ROOT}/.claude/scripts')
from plan_parser import load_plan, update_checkpoint_status, save_plan
from schemas import CheckpointStatus
path = sys.argv[1]
cp_id = sys.argv[2]
plan = load_plan(path)
plan = update_checkpoint_status(plan, cp_id, CheckpointStatus.COMPLETE)
save_plan(path, plan)
print(f'{cp_id}: plan.yaml -> complete')
" "$REPO_ROOT/plans/plan.yaml" "$CP_ID" 2>/dev/null || true
        fi

        git -C "$REPO_ROOT" worktree remove "$REPO_ROOT/.worktrees/$CP_ID" --force 2>/dev/null || true
        git -C "$REPO_ROOT" worktree prune
        git -C "$REPO_ROOT" branch -d "iocane/$CP_ID" 2>/dev/null || true
        echo "$CP_ID: Worktree and branch removed."

    elif echo "$STATUS" | grep -q "^PREFLIGHT_FAIL"; then
        echo "$CP_ID: PREFLIGHT_FAIL -- baseline tests failing before generation. See $TASKS_DIR/$CP_ID.log"
        FAILED=$((FAILED + 1))
        echo "$CP_ID: Worktree preserved at $REPO_ROOT/.worktrees/$CP_ID for inspection."

    elif echo "$STATUS" | grep -q "^CT_FAIL"; then
        # CT-writer HALT or non-zero exit -- surfaces as a hard
        # failure, no retry (D16). The ct_author HALTs on spec
        # ambiguity rather than emitting an AMEND, so a failure
        # here points at either an architect defect or an
        # agent-execution defect; both warrant human triage.
        # Classify as MECHANICAL_FAIL-family for the escalation
        # flag so the next session surfaces it prominently, same
        # as EVAL_FAIL / "MISSING" paths.
        echo "$CP_ID: $STATUS -- see $TASKS_DIR/$CP_ID.log"
        FAILED=$((FAILED + 1))
        mkdir -p "$REPO_ROOT/.iocane"
        echo "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" > "$REPO_ROOT/.iocane/escalation.flag"
        echo "[BATCH] $CP_ID: CT-writer failed -- $STATUS" >> "$REPO_ROOT/.iocane/escalation.log"
        echo "$CP_ID: Worktree preserved at $REPO_ROOT/.worktrees/$CP_ID for inspection."

    elif echo "$STATUS" | grep -q "^EVAL_FAIL"; then
        echo "$CP_ID: $STATUS -- see $TASKS_DIR/$CP_ID.log and $TASKS_DIR/$CP_ID.eval.json"
        FAILED=$((FAILED + 1))
        echo "$CP_ID: Worktree preserved at $REPO_ROOT/.worktrees/$CP_ID for inspection."

    else
        if [ "$STATUS" = "MISSING" ]; then
            echo "$CP_ID: No status written (likely max-turns exhaustion, exit $EXIT_CODE) -- see $TASKS_DIR/$CP_ID.log"
            echo "       To resume: bash .claude/scripts/dispatch-agents.sh --resume $CP_ID"
            # Signal escalation so new sessions surface the unfinished checkpoint
            mkdir -p "$REPO_ROOT/.iocane"
            echo "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" > "$REPO_ROOT/.iocane/escalation.flag"
        else
            echo "$CP_ID: $STATUS (exit $EXIT_CODE) -- see $TASKS_DIR/$CP_ID.log"
        fi
        FAILED=$((FAILED + 1))
        echo "$CP_ID: Worktree preserved at $REPO_ROOT/.worktrees/$CP_ID for inspection."
    fi
done

# --- CI Sidecar: post-wave regression diff (skipped in resume mode) ---
if [ -z "$RESUME_CP" ] && [ -f "$SCRIPT_DIR/ci-sidecar.sh" ]; then
    echo ""
    echo "[CI-SIDECAR] Running post-wave regression diff..."
    bash "$SCRIPT_DIR/ci-sidecar.sh" post-wave || \
        echo "[CI-COLLECTION-ERROR] Post-wave sidecar failed (exit $?). Merges preserved." >&2
fi

# --- Summary ---
echo ""
echo "Batch complete. Passed: $((TOTAL - FAILED))/$TOTAL"
echo ""

if [ "$FAILED" -gt 0 ]; then
    echo "Failures detected. Check plans/tasks/*.log and .iocane/escalation.log"
    exit 1
fi

# --- Clear escalation state on clean batch ---
if [ -f "$REPO_ROOT/.iocane/escalation.flag" ]; then
    rm "$REPO_ROOT/.iocane/escalation.flag"
    rm -f "$REPO_ROOT/.iocane/escalation.log"
    # Reset workflow-state.json escalation field
    STATE_FILE="$REPO_ROOT/.iocane/workflow-state.json"
    if [ -f "$STATE_FILE" ]; then
        _NEXT=$(grep -o '"next":"[^"]*"' "$STATE_FILE" | cut -d'"' -f4)
        _TRIGGER=$(grep -o '"trigger":"[^"]*"' "$STATE_FILE" | cut -d'"' -f4)
        printf '{"next":"%s","trigger":"%s","escalation":false,"timestamp":"%s"}\n' \
            "${_NEXT:-unknown}" "${_TRIGGER:-batch-passed}" \
            "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" > "$STATE_FILE"
    fi
    echo "Escalation state cleared (all checkpoints passed)."
fi

echo "All checkpoints passed. Run /io-review to verify outputs."
exit 0

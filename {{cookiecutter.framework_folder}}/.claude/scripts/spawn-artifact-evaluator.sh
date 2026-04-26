#!/usr/bin/env bash
# .claude/scripts/spawn-artifact-evaluator.sh
#
# Spawns a semantic artifact-evaluator subprocess against a canonical
# YAML artifact set. Invoked from io-architect Step H against the
# 4-file design surface (component-contracts, seams, symbols, test-plan).
#
# Substage A4 wires the --rubric design path. --rubric cdt and
# --rubric ct stub-exit non-zero with deferral messages; A5 and A6
# fill those branches by extending this script (no arg-parser change).
#
# Usage:
#   bash .claude/scripts/spawn-artifact-evaluator.sh --rubric design \
#     --contracts plans/component-contracts.yaml \
#     --seams plans/seams.yaml \
#     --symbols plans/symbols.yaml \
#     --test-plan plans/test-plan.yaml \
#     [--dry-run]
#
# Environment overrides (each takes precedence over iocane.config.yaml):
#   IOCANE_DESIGN_EVAL_MODEL     -- claude model string (default: models.tier1)
#   IOCANE_DESIGN_EVAL_MAX_TURNS -- per-invocation turn budget (default: agents.design_eval_max_turns)
#   IOCANE_DESIGN_EVAL_TIMEOUT   -- per-invocation wall-clock (default: agents.design_eval_timeout)
#   REPO_ROOT                    -- auto-detected via git if unset

set -euo pipefail

usage() {
    cat >&2 <<'EOF'
Usage: spawn-artifact-evaluator.sh --rubric {design|cdt|ct} \
    --contracts <path> --seams <path> --symbols <path> --test-plan <path> \
    [--dry-run]
EOF
}

RUBRIC=""
CONTRACTS=""
SEAMS=""
SYMBOLS=""
TEST_PLAN=""
DRY_RUN=0

while [ $# -gt 0 ]; do
    case "$1" in
        --rubric)
            if [ -z "${2:-}" ]; then
                echo "ERROR: --rubric requires a value (design|cdt|ct)" >&2
                usage
                exit 2
            fi
            RUBRIC="$2"
            shift 2
            ;;
        --contracts)
            CONTRACTS="${2:-}"
            shift 2
            ;;
        --seams)
            SEAMS="${2:-}"
            shift 2
            ;;
        --symbols)
            SYMBOLS="${2:-}"
            shift 2
            ;;
        --test-plan)
            TEST_PLAN="${2:-}"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "ERROR: Unknown argument: $1" >&2
            usage
            exit 2
            ;;
    esac
done

if [ -z "$RUBRIC" ]; then
    echo "ERROR: --rubric is required" >&2
    usage
    exit 2
fi

case "$RUBRIC" in
    design)
        ;;
    cdt)
        echo "ERROR: --rubric cdt is deferred to substage A5 per substage-A4.md s0" >&2
        exit 3
        ;;
    ct)
        echo "ERROR: --rubric ct is deferred to substage A6 per substage-A4.md s0" >&2
        exit 3
        ;;
    *)
        echo "ERROR: Unknown rubric '$RUBRIC' (expected design|cdt|ct)" >&2
        usage
        exit 2
        ;;
esac

# Required-args validation for the design rubric.
MISSING=()
[ -n "$CONTRACTS" ] || MISSING+=("--contracts")
[ -n "$SEAMS" ] || MISSING+=("--seams")
[ -n "$SYMBOLS" ] || MISSING+=("--symbols")
[ -n "$TEST_PLAN" ] || MISSING+=("--test-plan")
if [ ${#MISSING[@]} -gt 0 ]; then
    echo "ERROR: --rubric design requires: ${MISSING[*]}" >&2
    usage
    exit 2
fi

REPO_ROOT="${REPO_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || true)}"
if [ -z "$REPO_ROOT" ]; then
    echo "ERROR: Could not determine repo root. Are you inside a git repository?" >&2
    exit 1
fi
CONFIG_FILE="$REPO_ROOT/.claude/iocane.config.yaml"

# _cfg_read: extract section.key value from YAML config (awk-based).
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

# Resolve model: env override -> models.tier1 -> hard default.
_cfg_design_model=$(_cfg_read "models.tier1")
if [ -n "${IOCANE_DESIGN_EVAL_MODEL:-}" ]; then
    DESIGN_MODEL="$IOCANE_DESIGN_EVAL_MODEL"
elif [ -n "$_cfg_design_model" ] && [ "$_cfg_design_model" != "null" ]; then
    DESIGN_MODEL="$_cfg_design_model"
else
    DESIGN_MODEL="claude-opus-4-7"
fi

# Resolve max_turns: env override -> agents.design_eval_max_turns -> hard default.
_cfg_design_turns=$(_cfg_read "agents.design_eval_max_turns")
if [ -n "${IOCANE_DESIGN_EVAL_MAX_TURNS:-}" ]; then
    DESIGN_MAX_TURNS="$IOCANE_DESIGN_EVAL_MAX_TURNS"
elif [ -n "$_cfg_design_turns" ] && [ "$_cfg_design_turns" != "null" ]; then
    DESIGN_MAX_TURNS="$_cfg_design_turns"
else
    DESIGN_MAX_TURNS="50"
fi

# Resolve timeout: env override -> agents.design_eval_timeout -> hard default.
_cfg_design_timeout=$(_cfg_read "agents.design_eval_timeout")
if [ -n "${IOCANE_DESIGN_EVAL_TIMEOUT:-}" ]; then
    DESIGN_TIMEOUT="$IOCANE_DESIGN_EVAL_TIMEOUT"
elif [ -n "$_cfg_design_timeout" ] && [ "$_cfg_design_timeout" != "null" ]; then
    DESIGN_TIMEOUT="$_cfg_design_timeout"
else
    DESIGN_TIMEOUT="15m"
fi

COMMAND_FILE=".claude/commands/io-design-evaluator.md"
PROMPT="Read and execute the workflow defined in ${COMMAND_FILE}. Canonical artifacts: contracts=${CONTRACTS}; seams=${SEAMS}; symbols=${SYMBOLS}; test-plan=${TEST_PLAN}. Apply the design-evaluator rubric. Emit OBSERVATION findings via findings_emitter; do not halt."

if [ "$DRY_RUN" -eq 1 ]; then
    cat <<EOF
rubric: design
model: ${DESIGN_MODEL}
max_turns: ${DESIGN_MAX_TURNS}
timeout: ${DESIGN_TIMEOUT}
command_file: ${COMMAND_FILE}
contracts: ${CONTRACTS}
seams: ${SEAMS}
symbols: ${SYMBOLS}
test_plan: ${TEST_PLAN}
EOF
    exit 0
fi

# Subagent session linkage: tag this subprocess as a subagent of the
# parent architect session so session-start.sh registers it under the
# right manifest entry and does not clobber .current-session-id.
# Pattern mirrors dispatch-agents.sh:357-363.
export IOCANE_SUBAGENT=1
export IOCANE_PARENT_SESSION_ID="$(cat "$REPO_ROOT/.iocane/sessions/.current-session-id" 2>/dev/null || echo "")"
export IOCANE_REPO_ROOT="$REPO_ROOT"

echo "$PROMPT" | timeout "$DESIGN_TIMEOUT" claude -p \
    --model "$DESIGN_MODEL" \
    --max-turns "$DESIGN_MAX_TURNS" \
    --allowedTools "Bash,Read,Write,Grep,Glob" \
    --output-format json

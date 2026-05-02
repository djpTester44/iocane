#!/bin/bash
set -euo pipefail

#
# spawn-test-author.sh
#
# Spawn script for the wire-tests Author role (CDT or CT). Invoked per-target
# by run_actor_critic_loop.sh (Step 4.7). Spawns a `claude -p` subprocess with
# the appropriate capability grant + read-only context paths + write-target
# instruction.
#

# --- Globals & Defaults ---

IOCANE_REPO_ROOT="${IOCANE_REPO_ROOT:-.}"
TARGET_ID=""
TARGET_TYPE=""
RETRY_ATTEMPT=""
PRIOR_EVAL_PATH=""

# Configuration defaults (overridable by env or config file)
AUTHOR_MODEL="${AUTHOR_MODEL:-claude-sonnet-4-6}"
AUTHOR_MAX_TURNS="${AUTHOR_MAX_TURNS:-70}"
AUTHOR_TIMEOUT="${AUTHOR_TIMEOUT:-10m}"

# --- CLI Parsing ---

while [[ $# -gt 0 ]]; do
    case "$1" in
        --target-id)
            TARGET_ID="$2"
            shift 2
            ;;
        --target-type)
            TARGET_TYPE="$2"
            shift 2
            ;;
        --retry-attempt)
            RETRY_ATTEMPT="$2"
            shift 2
            ;;
        --prior-eval-path)
            PRIOR_EVAL_PATH="$2"
            shift 2
            ;;
        *)
            echo "ERROR: Unknown option $1" >&2
            exit 1
            ;;
    esac
done

# --- Validation ---

# Check required args
if [ -z "$TARGET_ID" ]; then
    echo "ERROR: --target-id is required" >&2
    exit 1
fi

if [ -z "$TARGET_TYPE" ]; then
    echo "ERROR: --target-type is required" >&2
    exit 1
fi

# Validate target-id against identifier regex: ^[A-Za-z_][A-Za-z0-9_-]*$
if ! [[ "$TARGET_ID" =~ ^[A-Za-z_][A-Za-z0-9_-]*$ ]]; then
    echo "ERROR: --target-id '$TARGET_ID' does not match required pattern ^[A-Za-z_][A-Za-z0-9_-]*$" >&2
    exit 2
fi

# Validate target-type
case "$TARGET_TYPE" in
    cdt|ct) : ;;
    *)
        echo "ERROR: --target-type must be 'cdt' or 'ct', got '$TARGET_TYPE'" >&2
        exit 1
        ;;
esac

# Validate retry args
if [ -n "$RETRY_ATTEMPT" ]; then
    if ! [[ "$RETRY_ATTEMPT" =~ ^[0-9]+$ ]] || [ "$RETRY_ATTEMPT" -lt 2 ]; then
        echo "ERROR: --retry-attempt must be an integer >= 2, got '$RETRY_ATTEMPT'" >&2
        exit 1
    fi
    if [ -z "$PRIOR_EVAL_PATH" ]; then
        echo "ERROR: --prior-eval-path is required when --retry-attempt is set" >&2
        exit 1
    fi
    if [ ! -f "$PRIOR_EVAL_PATH" ]; then
        echo "ERROR: --prior-eval-path '$PRIOR_EVAL_PATH' does not exist as a file" >&2
        exit 1
    fi
else
    if [ -n "$PRIOR_EVAL_PATH" ]; then
        echo "ERROR: --prior-eval-path is forbidden when --retry-attempt is not set" >&2
        exit 1
    fi
fi

# --- Resolve Config ---

# Attempt to load config if it exists; use env/defaults as fallback
CONFIG_FILE="${IOCANE_REPO_ROOT}/.claude/iocane.config.yaml"

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

if [ -f "$CONFIG_FILE" ]; then
    # Extract tier2 model from YAML (simple grep; assumes consistent format)
    TIER2_MODEL=$(grep -A2 "^models:" "$CONFIG_FILE" | grep "tier2:" | awk '{print $2}' || echo "")
    if [ -n "$TIER2_MODEL" ]; then
        AUTHOR_MODEL="$TIER2_MODEL"
    fi
    _cfg_turns=$(_cfg_read "wire_tests.author_max_turns")
    if [ -n "$_cfg_turns" ] && [ "$_cfg_turns" != "null" ]; then
        AUTHOR_MAX_TURNS="$_cfg_turns"
    fi
    AGENT_TIMEOUT=$(grep "timeout:" "$CONFIG_FILE" | head -1 | awk '{print $2}' || echo "")
    if [ -n "$AGENT_TIMEOUT" ]; then
        AUTHOR_TIMEOUT="$AGENT_TIMEOUT"
    fi
fi

# --- Architect-mode Sentinel Preflight ---

ARCHITECT_MODE_FLAG="${IOCANE_REPO_ROOT}/.iocane/architect-mode"
if [ -f "$ARCHITECT_MODE_FLAG" ]; then
    echo "ERROR: .iocane/architect-mode sentinel is set. /io-architect is mid-design." >&2
    echo "       Complete or abandon the architect pass and clear $ARCHITECT_MODE_FLAG before dispatching." >&2
    exit 1
fi

# --- Setup Environment ---

export IOCANE_REPO_ROOT
export IOCANE_PARENT_SESSION_ID="$(cat "${IOCANE_REPO_ROOT}/.iocane/sessions/.current-session-id" 2>/dev/null || echo "")"
export IOCANE_SUBAGENT=1

case "$TARGET_TYPE" in
    cdt) export IOCANE_ROLE=test_author_cdt ;;
    ct)  export IOCANE_ROLE=test_author_ct ;;
esac

# --- Build Read-Only Context Paths ---

READONLY_PATHS=()

case "$TARGET_TYPE" in
    cdt)
        READONLY_PATHS=(
            "plans/component-contracts.yaml"
            "plans/symbols.yaml"
            ".claude/rubrics/cdt-rubric.md"
        )
        ;;
    ct)
        READONLY_PATHS=(
            "plans/seams.yaml"
            "plans/component-contracts.yaml"
            "plans/symbols.yaml"
            "tests/contracts/test_*.py"
            ".claude/rubrics/ct-rubric.md"
        )
        ;;
esac

# On retry, include the prior eval YAML
if [ -n "$RETRY_ATTEMPT" ]; then
    READONLY_PATHS+=("$PRIOR_EVAL_PATH")
fi

# --- Build Write Target ---

case "$TARGET_TYPE" in
    cdt) WRITE_TARGET="tests/contracts/test_${TARGET_ID}.py" ;;
    ct)  WRITE_TARGET="tests/connectivity/test_${TARGET_ID}.py" ;;
esac

# --- Build Author Prompt ---

read -r -d '' AUTHOR_PROMPT << 'PROMPT_EOF' || true
You are the Author in a Contract-Driven Test wire-test actor-critic loop.

Your role: Author a high-quality test (CDT or CT) that adheres to the rubric
and passes validation.

**Write Target File**

Your test must be written to this file path (relative to repo root):
${WRITE_TARGET}

**Required Context Files (Read-Only)**

Before authoring, review these files for the contracts and rubric you must
satisfy:

${READONLY_PATHS_DISPLAY}

**On Retry (Attempt N >= 2)**

${RETRY_CONTEXT}

The orchestrator has archived your prior test file; it is not on disk.
Author a FRESH implementation that satisfies the contracts and rubric.
Use the evaluator's critique_notes and axis booleans to understand what
failed, then address those specific issues in this new attempt.

**Action**

Using the contracts, symbols, and rubric as your specification, author the test.
Write it to ${WRITE_TARGET} and terminate.
PROMPT_EOF

# Build display strings for prompt injection
READONLY_PATHS_DISPLAY=$(printf '%s\n' "${READONLY_PATHS[@]}" | sed 's/^/- /')

if [ -n "$RETRY_ATTEMPT" ]; then
    RETRY_CONTEXT="This is retry attempt $RETRY_ATTEMPT. Read the prior evaluation at:
${PRIOR_EVAL_PATH}

Extract the critique_notes and axis-result booleans to understand what failed."
else
    RETRY_CONTEXT=""
fi

# Perform simple template substitution
AUTHOR_PROMPT="${AUTHOR_PROMPT//\${WRITE_TARGET}/$WRITE_TARGET}"
AUTHOR_PROMPT="${AUTHOR_PROMPT//\${READONLY_PATHS_DISPLAY}/$READONLY_PATHS_DISPLAY}"
AUTHOR_PROMPT="${AUTHOR_PROMPT//\${RETRY_CONTEXT}/$RETRY_CONTEXT}"

# --- Setup Output Files ---

RESULT_FILE="${IOCANE_REPO_ROOT}/.iocane/wire-tests/author-result-${TARGET_ID}-attempt-${RETRY_ATTEMPT:-1}.json"
LOG_FILE="${IOCANE_REPO_ROOT}/.iocane/wire-tests/author-log-${TARGET_ID}-attempt-${RETRY_ATTEMPT:-1}.txt"

mkdir -p "$(dirname "$RESULT_FILE")" "$(dirname "$LOG_FILE")"

# --- Invoke claude -p ---

# Errexit-safe exit capture: under `set -euo pipefail` a failing pipeline
# aborts the shell before $? can be read. Wrapping in `if cmd; then :; else
# X=$?; fi` makes the call errexit-exempt AND preserves $? inside the else
# branch.
AUTHOR_EXIT=0
if echo "$AUTHOR_PROMPT" | timeout "$AUTHOR_TIMEOUT" claude -p \
        --model "$AUTHOR_MODEL" \
        --max-turns "$AUTHOR_MAX_TURNS" \
        --allowedTools "Read,Write,Edit,Bash" \
        --output-format json \
        > "$RESULT_FILE" 2>> "$LOG_FILE"; then
    :
else
    AUTHOR_EXIT=$?
fi

# --- Inspect result JSON to surface invisible failure modes ---
#
# claude -p returns exit 0 even when the response payload is an error envelope
# (is_error=true, api_error_status=429 / 529 / 401 / etc.). Without this
# inspection, an error envelope looks like a clean exit and the inner loop
# happily proceeds to the Critic, which also errors; the eval YAML never lands;
# the parser-failure path treats it as STATUS=FAIL and burns a retry cycle.
# Two distinguishable failures are surfaced as dedicated exit codes:
#
#   64 -- API error envelope (any is_error=true response: 429 rate-limit,
#         529 overloaded, auth errors, server errors, etc.). The inner loop
#         snapshots api_error_status into the FindingFile.
#   65 -- empty OR unparseable result file. Subprocess killed mid-write
#         (panic-stop), partial-write before kill, or other infra failure.
#
# Otherwise AUTHOR_EXIT is preserved.
if [ -f "$RESULT_FILE" ]; then
    if [ ! -s "$RESULT_FILE" ]; then
        AUTHOR_EXIT=65
    else
        _classify=$(uv run python -c "
import json
try:
    d = json.loads(open('${RESULT_FILE}').read())
except Exception:
    print('UNPARSEABLE')
    raise SystemExit(0)
if d.get('is_error') is True:
    print('API_ERROR')
" 2>/dev/null)
        case "$_classify" in
            UNPARSEABLE) AUTHOR_EXIT=65 ;;
            API_ERROR)   AUTHOR_EXIT=64 ;;
        esac
    fi
fi

exit "$AUTHOR_EXIT"

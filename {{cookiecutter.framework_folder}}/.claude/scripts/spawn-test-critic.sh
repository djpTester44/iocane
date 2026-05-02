#!/usr/bin/env bash
# .claude/scripts/spawn-test-critic.sh
#
# Wire-tests Critic role: spawns a Claude subprocess that validates CDT or CT
# test files against rubrics. Invoked per-target by run_actor_critic_loop.sh
# AFTER the Author turn writes the test file.
#
# Usage:
#   spawn-test-critic.sh --target-id <id> --target-type cdt|ct
#
# Outputs:
#   .iocane/wire-tests/eval_<target_id>.yaml (EvalReport schema)

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================

TARGET_ID=""
TARGET_TYPE=""

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

# ============================================================================
# Parse CLI Arguments
# ============================================================================

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
        *)
            echo "ERROR: Unknown argument '$1'" >&2
            exit 2
            ;;
    esac
done

# Validate required arguments
if [ -z "$TARGET_ID" ] || [ -z "$TARGET_TYPE" ]; then
    echo "ERROR: --target-id and --target-type are required" >&2
    exit 2
fi

# Validate target-id format: ^[A-Za-z_][A-Za-z0-9_-]*$
if ! [[ "$TARGET_ID" =~ ^[A-Za-z_][A-Za-z0-9_-]*$ ]]; then
    echo "ERROR: --target-id '$TARGET_ID' does not match pattern ^[A-Za-z_][A-Za-z0-9_-]*$" >&2
    exit 2
fi

# Validate target-type
if [ "$TARGET_TYPE" != "cdt" ] && [ "$TARGET_TYPE" != "ct" ]; then
    echo "ERROR: --target-type must be 'cdt' or 'ct', got '$TARGET_TYPE'" >&2
    exit 2
fi

# ============================================================================
# Environment Setup
# ============================================================================

IOCANE_REPO_ROOT="${IOCANE_REPO_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null)}"
IOCANE_REPO_ROOT="${IOCANE_REPO_ROOT:-.}"

CONFIG_FILE="$IOCANE_REPO_ROOT/.claude/iocane.config.yaml"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "ERROR: Config file not found: $CONFIG_FILE" >&2
    exit 1
fi

# Export required env vars
export IOCANE_REPO_ROOT
export IOCANE_ROLE=test_critic
export IOCANE_PARENT_SESSION_ID="$(cat "$IOCANE_REPO_ROOT/.iocane/sessions/.current-session-id" 2>/dev/null || echo "")"
export IOCANE_SUBAGENT=1

# ============================================================================
# Architect-Mode Gate
# ============================================================================

ARCHITECT_MODE_FLAG="$IOCANE_REPO_ROOT/.iocane/architect-mode"
if [ -f "$ARCHITECT_MODE_FLAG" ]; then
    echo "ERROR: .iocane/architect-mode sentinel is set. /io-architect is mid-design." >&2
    echo "       Complete or abandon the architect pass and clear $ARCHITECT_MODE_FLAG before spawning Critic." >&2
    exit 1
fi

# ============================================================================
# Resolve Model and Timeout
# ============================================================================

MODEL=$(_cfg_read "models.tier1")
if [ -z "$MODEL" ] || [ "$MODEL" = "null" ]; then
    MODEL="claude-opus-4-7"
fi

AGENT_TIMEOUT=$(_cfg_read "agents.timeout")
if [ -z "$AGENT_TIMEOUT" ] || [ "$AGENT_TIMEOUT" = "null" ]; then
    AGENT_TIMEOUT="10m"
fi

# Per-agent turn budget for the Critic invocation (distinct from wire_tests.max_turns, which governs loop cycles).
CRITIC_MAX_TURNS=$(_cfg_read "wire_tests.critic_max_turns")
if [ -z "$CRITIC_MAX_TURNS" ] || [ "$CRITIC_MAX_TURNS" = "null" ]; then
    CRITIC_MAX_TURNS="30"
fi

# ============================================================================
# Resolve Paths by Target Type
# ============================================================================

# Read-only: test file (varies by type)
if [ "$TARGET_TYPE" = "cdt" ]; then
    TEST_FILE="tests/contracts/test_${TARGET_ID}.py"
    RUBRIC_FILE=".claude/rubrics/cdt-rubric.md"
else
    TEST_FILE="tests/connectivity/test_${TARGET_ID}.py"
    RUBRIC_FILE=".claude/rubrics/ct-rubric.md"
fi

# Output directory and file
OUTPUT_DIR="$IOCANE_REPO_ROOT/.iocane/wire-tests"
EVAL_FILE="$OUTPUT_DIR/eval_${TARGET_ID}.yaml"
LOG_FILE="$OUTPUT_DIR/critic_${TARGET_ID}.log"

# ============================================================================
# Create Output Directory
# ============================================================================

mkdir -p "$OUTPUT_DIR"
: > "$LOG_FILE"

# ============================================================================
# Build Critic Prompt
# ============================================================================

read -r -d '' CRITIC_PROMPT <<'PROMPT_EOF' || :
You are a Critic agent validating wire-tests (Contract-Driven Tests or Connectivity Tests).

Role: test_critic
Target Type: TARGET_TYPE_PLACEHOLDER
Target ID: TARGET_ID_PLACEHOLDER

Your task is to evaluate the just-authored test file and emit a structured verdict (EvalReport).

READ THESE FILES (read-only; do not modify):
- Test file: TEST_FILE_PLACEHOLDER
- Rubric file: RUBRIC_FILE_PLACEHOLDER
- plans/component-contracts.yaml
- plans/symbols.yaml
SEAMS_READ_PLACEHOLDER

The rubric file is the immutable specification. Grade the test file against it.

WRITE OUTPUT to this exact path (creates new file; uses YAML format):
  EVAL_FILE_PLACEHOLDER

SCHEMA: EvalReport (Pydantic model, frozen=True, extra="forbid")
  target_id: str = TARGET_ID_PLACEHOLDER
  target_type: Literal["cdt", "ct"] = TARGET_TYPE_PLACEHOLDER
  attempt: int (>= 1, derived from any prior evals for this target)
  status: Literal["PASS", "FAIL", "AMBIGUOUS"]
  critique_notes: str = "" (required non-empty when status is FAIL or AMBIGUOUS)

  For CDT only:
    payload_shape_covered: bool | None
    invariants_asserted: bool | None
    collaborator_mocks_speced: bool | None
    raises_coverage_complete: bool | None

  For CT only:
    seam_fan_coverage: bool | None
    cdt_ct_mock_spec_consistent: bool | None
    integration_path_asserted: bool | None

EVALUATION CRITERIA (per rubric):
1. Read the rubric file thoroughly.
2. Assess the test file against each rubric criterion.
3. For each axis (payload_shape_covered, invariants_asserted, etc.), decide: true, false, or null (if undecidable).
4. Decide STATUS:
   - PASS: all applicable axes true, critique_notes may be empty.
   - FAIL: any axis false AND critique_notes non-empty (explain which axis/why).
   - AMBIGUOUS: axes are partial/null AND critique_notes non-empty (explain what was ambiguous).
5. Write the EvalReport to the target path.

INDEPENDENCE CONSTRAINT: You have NOT seen any prior Critic evaluations, Author self-assessments, or retry history for this target. Form your verdict from the test file and rubric alone.

Do not mention previous attempts, prior evaluator notes, or author reasoning. Your verdict stands on the code and rubric.

Emit the EvalReport as valid YAML. Validate schema compliance before writing.
PROMPT_EOF

# Substitute placeholders
CRITIC_PROMPT="${CRITIC_PROMPT//TARGET_TYPE_PLACEHOLDER/$TARGET_TYPE}"
CRITIC_PROMPT="${CRITIC_PROMPT//TARGET_ID_PLACEHOLDER/$TARGET_ID}"
CRITIC_PROMPT="${CRITIC_PROMPT//TEST_FILE_PLACEHOLDER/$TEST_FILE}"
CRITIC_PROMPT="${CRITIC_PROMPT//RUBRIC_FILE_PLACEHOLDER/$RUBRIC_FILE}"
CRITIC_PROMPT="${CRITIC_PROMPT//EVAL_FILE_PLACEHOLDER/$EVAL_FILE}"

# Add CT-specific read if target type is CT
if [ "$TARGET_TYPE" = "ct" ]; then
    CRITIC_PROMPT="${CRITIC_PROMPT//SEAMS_READ_PLACEHOLDER/- plans/seams.yaml}"
else
    CRITIC_PROMPT="${CRITIC_PROMPT//SEAMS_READ_PLACEHOLDER/}"
fi

# ============================================================================
# Subprocess Invocation (Errexit-Safe)
# ============================================================================

CRITIC_EXIT=0
if echo "$CRITIC_PROMPT" | timeout "$AGENT_TIMEOUT" claude -p \
        --model "$MODEL" \
        --max-turns "$CRITIC_MAX_TURNS" \
        --allowedTools "Read,Write,Bash" \
        --output-format json \
        > "$OUTPUT_DIR/critic_${TARGET_ID}.json" 2>> "$LOG_FILE"; then
    :
else
    CRITIC_EXIT=$?
fi

# --- Inspect result JSON to surface invisible failure modes ---
#
# claude -p returns exit 0 even when the response payload is an error envelope
# (is_error=true, api_error_status=429 / 529 / 401 / etc.). Surface error
# envelopes and empty/unparseable result files as dedicated exit codes so the
# inner loop can branch instead of treating absent eval YAML as STATUS=FAIL.
#
#   64 -- API error envelope (any is_error=true response: 429 rate-limit,
#         529 overloaded, auth errors, server errors, etc.). The inner loop
#         snapshots api_error_status into the FindingFile.
#   65 -- empty OR unparseable result file. Subprocess killed mid-write
#         (panic-stop), partial-write before kill, or other infra failure.
#
# Otherwise CRITIC_EXIT is preserved.
CRITIC_RESULT_FILE="$OUTPUT_DIR/critic_${TARGET_ID}.json"
if [ -f "$CRITIC_RESULT_FILE" ]; then
    if [ ! -s "$CRITIC_RESULT_FILE" ]; then
        CRITIC_EXIT=65
    else
        _classify=$(uv run python -c "
import json
try:
    d = json.loads(open('${CRITIC_RESULT_FILE}').read())
except Exception:
    print('UNPARSEABLE')
    raise SystemExit(0)
if d.get('is_error') is True:
    print('API_ERROR')
" 2>/dev/null)
        case "$_classify" in
            UNPARSEABLE) CRITIC_EXIT=65 ;;
            API_ERROR)   CRITIC_EXIT=64 ;;
        esac
    fi
fi

# ============================================================================
# Exit
# ============================================================================

if [ "$CRITIC_EXIT" -ne 0 ]; then
    echo "ERROR: Critic subprocess failed with exit code $CRITIC_EXIT for target $TARGET_ID" >&2
    echo "       See log: $LOG_FILE" >&2
    exit "$CRITIC_EXIT"
fi

# Check that eval file was written
if [ ! -f "$EVAL_FILE" ]; then
    echo "ERROR: Critic did not write eval file: $EVAL_FILE" >&2
    exit 1
fi

echo "OK: Critic verdict written to $EVAL_FILE"
exit 0

#!/usr/bin/env bash
# .claude/scripts/run_actor_critic_loop.sh
#
# Per-target inner loop for /io-wire-tests-cdt and /io-wire-tests-ct.
# Implements R2 clause 5(b) bounded retry: Author -> Critic -> inspect
# EvalReport.STATUS -> branch (PASS/FAIL/AMBIGUOUS).
#
# Usage:
#   run_actor_critic_loop.sh \
#     --target-id <id> \
#     --target-type cdt|ct \
#     --max-turns <N> \
#     --session-id <sid>
#
# Exits 0 on all terminal workflow states (PASS/FAIL-exhausted/AMBIGUOUS);
# FindingFile carries the verdict for FAIL-exhausted and AMBIGUOUS.
# Non-zero exit only on infrastructure failures.

set -euo pipefail

# ============================================================================
# Globals
# ============================================================================

REPO="${IOCANE_REPO_ROOT:-.}"
TARGET_ID=""
TARGET_TYPE=""
MAX_TURNS=""
SESSION_ID=""

AUTHOR_CAP_GRANTED=0
CRITIC_CAP_GRANTED=0

# ============================================================================
# CLI Parsing
# ============================================================================

while [[ $# -gt 0 ]]; do
    case "$1" in
        --target-id)    TARGET_ID="$2";    shift 2 ;;
        --target-type)  TARGET_TYPE="$2";  shift 2 ;;
        --max-turns)    MAX_TURNS="$2";    shift 2 ;;
        --session-id)   SESSION_ID="$2";   shift 2 ;;
        *)
            echo "ERROR: Unknown argument '$1'" >&2
            exit 1
            ;;
    esac
done

# ============================================================================
# Validation
# ============================================================================

if [ -z "$TARGET_ID" ]; then
    echo "ERROR: --target-id is required" >&2; exit 1
fi
if [ -z "$TARGET_TYPE" ]; then
    echo "ERROR: --target-type is required" >&2; exit 1
fi
if [ -z "$MAX_TURNS" ]; then
    echo "ERROR: --max-turns is required" >&2; exit 1
fi
if [ -z "$SESSION_ID" ]; then
    echo "ERROR: --session-id is required" >&2; exit 1
fi

if ! [[ "$TARGET_ID" =~ ^[A-Za-z_][A-Za-z0-9_-]*$ ]]; then
    echo "ERROR: --target-id '$TARGET_ID' does not match ^[A-Za-z_][A-Za-z0-9_-]*\$" >&2
    exit 2
fi

case "$TARGET_TYPE" in
    cdt|ct) ;;
    *)
        echo "ERROR: --target-type must be 'cdt' or 'ct', got '$TARGET_TYPE'" >&2
        exit 1
        ;;
esac

if ! [[ "$MAX_TURNS" =~ ^[0-9]+$ ]] || [ "$MAX_TURNS" -lt 1 ]; then
    echo "ERROR: --max-turns must be an integer >= 1, got '$MAX_TURNS'" >&2
    exit 1
fi

# ============================================================================
# Path Resolution
# ============================================================================

case "$TARGET_TYPE" in
    cdt)
        TEST_FILE="${REPO}/tests/contracts/test_${TARGET_ID}.py"
        ;;
    ct)
        TEST_FILE="${REPO}/tests/connectivity/test_${TARGET_ID}.py"
        ;;
esac

EVAL_FILE="${REPO}/.iocane/wire-tests/eval_${TARGET_ID}.yaml"
LIFETIME_DIR="${REPO}/.iocane/wire-tests/lifetime"
LIFETIME_FILE="${LIFETIME_DIR}/${TARGET_ID}.json"
LIFETIME_SENTINEL="${LIFETIME_DIR}/${TARGET_ID}.reset"
SPAWN_LOG_DIR="${REPO}/.iocane/wire-tests/spawn-log"
ARCHIVE_DIR="${REPO}/.iocane/wire-tests/archive"
PARENT_SID="$(cat "${REPO}/.iocane/sessions/.current-session-id" 2>/dev/null || echo "")"

# ============================================================================
# Helpers
# ============================================================================

# _iso8601: print current UTC timestamp as ISO 8601
_iso8601() {
    uv run python -c "from datetime import datetime, UTC; print(datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ'))"
}

# _emit_spawn_log ROLE ATTEMPT WRITE_TARGET_PATH EXIT_STATUS
# Writes .iocane/wire-tests/spawn-log/<target_id>-<role>-<attempt>.json
# via write-temp-then-rename. HALTs with FindingFile on rename failure.
_emit_spawn_log() {
    local role="$1"
    local attempt="$2"
    local write_target_path="$3"
    local exit_status="$4"

    local sid_spawn_dir="${SPAWN_LOG_DIR}/${SESSION_ID}"
    mkdir -p "$sid_spawn_dir"
    local target="${sid_spawn_dir}/${TARGET_ID}-${role}-${attempt}.json"
    local tmp="${target}.tmp.$$"

    local ts
    ts=$(_iso8601)
    uv run python -c "
import json, sys
d = {
    'target_id': '${TARGET_ID}',
    'sid': '${SESSION_ID}',
    'write_target_path': '${write_target_path}',
    'timestamp_iso8601': '${ts}',
    'exit_status': ${exit_status},
    'parent_session_id': '${PARENT_SID}',
}
print(json.dumps(d, indent=2))
" > "$tmp"

    if ! mv "$tmp" "$target"; then
        rm -f "$tmp"
        _emit_finding "spawn_log_emit_failed" \
            "spawn-log rename failed for ${TARGET_ID} ${role} attempt ${attempt}" \
            "mv ${tmp} -> ${target} returned non-zero" \
            "wire_tests" \
            "Retry after clearing stale tmp files in ${SPAWN_LOG_DIR}"
        exit 1
    fi
}

# _read_lifetime_count: print ambiguous_count from lifetime JSON (0 if absent/unreadable)
_read_lifetime_count() {
    if [ ! -f "$LIFETIME_FILE" ]; then
        echo 0
        return
    fi
    uv run python -c "
import json, sys
try:
    d = json.load(open('${LIFETIME_FILE}'))
    print(int(d.get('ambiguous_count', 0)))
except Exception:
    print(0)
" 2>/dev/null || echo 0
}

# _increment_lifetime: atomically increment ambiguous_count via write-temp-then-rename
# Returns 0 on success; emits FindingFile and exits 1 on rename failure.
_increment_lifetime() {
    mkdir -p "$LIFETIME_DIR"
    local current
    current=$(_read_lifetime_count)
    local new_count=$(( current + 1 ))
    local ts
    ts=$(_iso8601)
    local tmp="${LIFETIME_FILE}.tmp.$$"

    uv run python -c "
import json
print(json.dumps({'ambiguous_count': ${new_count}, 'last_updated': '${ts}'}))
" > "$tmp"

    if ! mv "$tmp" "$LIFETIME_FILE"; then
        rm -f "$tmp"
        _emit_finding "lifetime_increment_failed" \
            "lifetime increment rename failed for ${TARGET_ID}" \
            "mv ${tmp} -> ${LIFETIME_FILE} returned non-zero" \
            "wire_tests" \
            "Manually delete ${LIFETIME_FILE}.tmp.$$ if present and re-run"
        exit 1
    fi
}

# _emit_finding DEFECT_KIND WHAT WHERE ROOT_CAUSE_LAYER FIX_STEP
# Writes a temp Finding YAML and invokes findings_emitter.
_emit_finding() {
    local defect_kind="$1"
    local what="$2"
    local where="$3"
    local root_cause_layer="$4"
    local fix_step="$5"

    local context_field
    if [ -n "$TARGET_ID" ]; then
        context_field="test_file: tests/contracts/test_${TARGET_ID}.py"
        if [ "$TARGET_TYPE" = "ct" ]; then
            context_field="test_file: tests/connectivity/test_${TARGET_ID}.py"
        fi
    else
        context_field="test_file: unknown"
    fi

    local tmp_yaml="${REPO}/.iocane/wire-tests/finding-tmp-${TARGET_ID}-$$.yaml"
    mkdir -p "$(dirname "$tmp_yaml")"
    cat > "$tmp_yaml" <<YAML_EOF
role: wire_test_critic
context:
  ${context_field}
defect_kind: ${defect_kind}
affected_artifacts:
  - ${TEST_FILE}
diagnosis:
  what: "${what}"
  where: "${where}"
  why: "Orchestrator halt: ${defect_kind}"
remediation:
  root_cause_layer: ${root_cause_layer}
  fix_steps:
    - "${fix_step}"
  re_entry_commands:
    - "bash .claude/scripts/run_actor_critic_loop.sh --target-id ${TARGET_ID} --target-type ${TARGET_TYPE} --max-turns ${MAX_TURNS} --session-id ${SESSION_ID}"
YAML_EOF

    local EMIT_EXIT=0
    if uv run python -c "
import sys
sys.path.insert(0, '${REPO}/.claude/scripts')
from findings_emitter import _cli
sys.argv = ['findings_emitter', '--from-yaml', '${tmp_yaml}', '--repo-root', '${REPO}']
sys.exit(_cli())
"; then :
    else EMIT_EXIT=$?; fi

    rm -f "$tmp_yaml"
    return $EMIT_EXIT
}

# _revoke_caps: revoke Author and Critic capability grants (best-effort; errors logged)
_revoke_caps() {
    if [ "$AUTHOR_CAP_GRANTED" -eq 1 ]; then
        local R=0
        if uv run python "${REPO}/.claude/scripts/capability.py" revoke \
                --session-id "$SESSION_ID" \
                --template "io-wire-tests.${TARGET_TYPE}"; then :
        else R=$?; fi
        [ "$R" -eq 0 ] && AUTHOR_CAP_GRANTED=0 || true
    fi
    if [ "$CRITIC_CAP_GRANTED" -eq 1 ]; then
        local R=0
        if uv run python "${REPO}/.claude/scripts/capability.py" revoke \
                --session-id "$SESSION_ID" \
                --template "io-wire-tests.critic"; then :
        else R=$?; fi
        [ "$R" -eq 0 ] && CRITIC_CAP_GRANTED=0 || true
    fi
}

# ============================================================================
# D-19 Startup: Sentinel Check + Lifetime Read
# ============================================================================

mkdir -p "$LIFETIME_DIR"

if [ -f "$LIFETIME_SENTINEL" ]; then
    local_ts=$(_iso8601)
    tmp_lt="${LIFETIME_FILE}.tmp.$$"
    uv run python -c "
import json
print(json.dumps({'ambiguous_count': 0, 'last_updated': '${local_ts}'}))
" > "$tmp_lt"
    if mv "$tmp_lt" "$LIFETIME_FILE"; then
        rm -f "$LIFETIME_SENTINEL"
    else
        rm -f "$tmp_lt"
        echo "WARN: failed to zero lifetime counter for ${TARGET_ID} after sentinel reset" >&2
    fi
fi

AMBIGUOUS_COUNT=$(_read_lifetime_count)

if [ "$AMBIGUOUS_COUNT" -ge 3 ]; then
    _emit_finding "actor_critic_lifetime_max" \
        "AMBIGUOUS lifetime ceiling reached for ${TARGET_ID}" \
        ".iocane/wire-tests/lifetime/${TARGET_ID}.json ambiguous_count=${AMBIGUOUS_COUNT}" \
        "wire_tests" \
        "Review spec ambiguity for ${TARGET_ID}, resolve upstream, then delete ${LIFETIME_FILE} and re-run (or create ${LIFETIME_SENTINEL} to reset counter)"
    exit 0
fi

# ============================================================================
# Capability Grants (pre-loop)
# ============================================================================

GRANT_EXIT=0
if uv run python "${REPO}/.claude/scripts/capability.py" grant \
        --session-id "$SESSION_ID" \
        --subagent \
        --parent-session-id "$PARENT_SID" \
        --template "io-wire-tests.${TARGET_TYPE}"; then :
else GRANT_EXIT=$?; fi
if [ "$GRANT_EXIT" -ne 0 ]; then
    echo "ERROR: capability grant failed for io-wire-tests.${TARGET_TYPE} (exit $GRANT_EXIT)" >&2
    exit "$GRANT_EXIT"
fi
AUTHOR_CAP_GRANTED=1

GRANT_EXIT=0
if uv run python "${REPO}/.claude/scripts/capability.py" grant \
        --session-id "$SESSION_ID" \
        --subagent \
        --parent-session-id "$PARENT_SID" \
        --template "io-wire-tests.critic"; then :
else GRANT_EXIT=$?; fi
if [ "$GRANT_EXIT" -ne 0 ]; then
    echo "ERROR: capability grant failed for io-wire-tests.critic (exit $GRANT_EXIT)" >&2
    _revoke_caps
    exit "$GRANT_EXIT"
fi
CRITIC_CAP_GRANTED=1

# ============================================================================
# Inner Loop
# ============================================================================

ATTEMPT=1

while [ "$ATTEMPT" -le "$MAX_TURNS" ]; do

    # --- Author spawn ---
    AUTHOR_EXIT=0
    if [ "$ATTEMPT" -eq 1 ]; then
        if bash "${REPO}/.claude/scripts/spawn-test-author.sh" \
                --target-id "$TARGET_ID" \
                --target-type "$TARGET_TYPE"; then :
        else AUTHOR_EXIT=$?; fi
    else
        PRIOR_EVAL="${REPO}/.iocane/wire-tests/eval_${TARGET_ID}.yaml"
        if bash "${REPO}/.claude/scripts/spawn-test-author.sh" \
                --target-id "$TARGET_ID" \
                --target-type "$TARGET_TYPE" \
                --retry-attempt "$ATTEMPT" \
                --prior-eval-path "$PRIOR_EVAL"; then :
        else AUTHOR_EXIT=$?; fi
    fi

    # Determine Author write target for spawn-log
    AUTHOR_WRITE_TARGET="${TEST_FILE}"
    _emit_spawn_log "author" "$ATTEMPT" "$AUTHOR_WRITE_TARGET" "$AUTHOR_EXIT"

    if [ "$AUTHOR_EXIT" -eq 64 ]; then
        # API error envelope (claude -p exit 0 + is_error=true). spawn-test-author
        # surfaced 64. Halt cleanly without consuming a turn or archiving. Snapshot
        # the actual api_error_status + result message inline so the finding is
        # self-contained (file path is sid+attempt-suffixed, but inline detail
        # removes the indirection cost for operator post-mortem).
        _revoke_caps
        _author_snapshot=$(uv run python -c "
import json
try:
    d = json.loads(open('${REPO}/.iocane/wire-tests/author-result-${TARGET_ID}-attempt-${ATTEMPT}.json').read())
    s = d.get('api_error_status', 'unknown')
    m = (d.get('result') or '')[:200].replace(chr(10), ' ').replace(chr(13), '').replace(chr(34), chr(39))
    print(f'api_error_status={s}; result snippet: {m}')
except Exception:
    print('snapshot extraction failed')
" 2>/dev/null)
        _emit_finding "api_error_envelope" \
            "Author spawn returned API error envelope for ${TARGET_ID} at attempt ${ATTEMPT}" \
            "${_author_snapshot}" \
            "wire_tests" \
            "Inspect api_error_status above. 429/529 -> wait for window reset; 401/403 -> fix credentials; 5xx -> retry after brief backoff. Re-run: bash .claude/scripts/io-wire-tests-${TARGET_TYPE}.sh --targets ${TARGET_ID}"
        exit 64
    fi
    if [ "$AUTHOR_EXIT" -eq 65 ]; then
        # Empty / unparseable result file -- claude -p partial-wrote then exited
        # (network reset, server abort, or other mid-stream infra failure).
        # Panic-stop kills are recorded separately in
        # wire_test_panic_stop_audit-*.yaml -- this finding is for non-panic-stop
        # infra failures only. Halt without consuming a turn or archiving.
        _revoke_caps
        _emit_finding "spawn_kill_or_infra_failure" \
            "Author spawn killed mid-write or infra failure for ${TARGET_ID} at attempt ${ATTEMPT}" \
            ".iocane/wire-tests/author-result-${TARGET_ID}-attempt-${ATTEMPT}.json is empty or unparseable" \
            "wire_tests" \
            "claude -p partial-wrote then exited (network reset / server abort / infra failure mid-stream). Panic-stop kills are recorded in .iocane/findings/wire_test_panic_stop_audit-*.yaml -- this finding is emitted only for non-panic-stop infra failures. Inspect run-log/${TARGET_ID}.log and re-run: bash .claude/scripts/io-wire-tests-${TARGET_TYPE}.sh --targets ${TARGET_ID}"
        exit 65
    fi
    if [ "$AUTHOR_EXIT" -ne 0 ]; then
        echo "ERROR: Author spawn failed (exit $AUTHOR_EXIT) for ${TARGET_ID} attempt ${ATTEMPT}" >&2
        _revoke_caps
        exit "$AUTHOR_EXIT"
    fi

    # --- Critic spawn ---
    CRITIC_EXIT=0
    if bash "${REPO}/.claude/scripts/spawn-test-critic.sh" \
            --target-id "$TARGET_ID" \
            --target-type "$TARGET_TYPE"; then :
    else CRITIC_EXIT=$?; fi

    CRITIC_WRITE_TARGET="${REPO}/.iocane/wire-tests/eval_${TARGET_ID}.yaml"
    _emit_spawn_log "critic" "$ATTEMPT" "$CRITIC_WRITE_TARGET" "$CRITIC_EXIT"

    if [ "$CRITIC_EXIT" -eq 64 ]; then
        # API error envelope (claude -p exit 0 + is_error=true). spawn-test-critic
        # surfaced 64. Halt cleanly without consuming a turn or archiving. Snapshot
        # the actual api_error_status + result message inline -- critic_<id>.json
        # has NO attempt/sid suffix so the file overwrites between attempts;
        # post-mortem MUST come from the finding text, not the cited path.
        _revoke_caps
        _critic_snapshot=$(uv run python -c "
import json
try:
    d = json.loads(open('${REPO}/.iocane/wire-tests/critic_${TARGET_ID}.json').read())
    s = d.get('api_error_status', 'unknown')
    m = (d.get('result') or '')[:200].replace(chr(10), ' ').replace(chr(13), '').replace(chr(34), chr(39))
    print(f'api_error_status={s}; result snippet: {m}')
except Exception:
    print('snapshot extraction failed')
" 2>/dev/null)
        _emit_finding "api_error_envelope" \
            "Critic spawn returned API error envelope for ${TARGET_ID} at attempt ${ATTEMPT}" \
            "${_critic_snapshot}" \
            "wire_tests" \
            "Inspect api_error_status above. 429/529 -> wait for window reset; 401/403 -> fix credentials; 5xx -> retry after brief backoff. Re-run: bash .claude/scripts/io-wire-tests-${TARGET_TYPE}.sh --targets ${TARGET_ID}"
        exit 64
    fi
    if [ "$CRITIC_EXIT" -eq 65 ]; then
        # Empty / unparseable result file -- claude -p partial-wrote then exited
        # (network reset, server abort, or other mid-stream infra failure).
        # Panic-stop kills are recorded separately in
        # wire_test_panic_stop_audit-*.yaml -- this finding is for non-panic-stop
        # infra failures only. Halt without consuming a turn or archiving.
        _revoke_caps
        _emit_finding "spawn_kill_or_infra_failure" \
            "Critic spawn killed mid-write or infra failure for ${TARGET_ID} at attempt ${ATTEMPT}" \
            ".iocane/wire-tests/critic_${TARGET_ID}.json is empty or unparseable" \
            "wire_tests" \
            "claude -p partial-wrote then exited (network reset / server abort / infra failure mid-stream). Panic-stop kills are recorded in .iocane/findings/wire_test_panic_stop_audit-*.yaml -- this finding is emitted only for non-panic-stop infra failures. Inspect run-log/${TARGET_ID}.log and re-run: bash .claude/scripts/io-wire-tests-${TARGET_TYPE}.sh --targets ${TARGET_ID}"
        exit 65
    fi
    if [ "$CRITIC_EXIT" -ne 0 ]; then
        echo "ERROR: Critic spawn failed (exit $CRITIC_EXIT) for ${TARGET_ID} attempt ${ATTEMPT}" >&2
        _revoke_caps
        exit "$CRITIC_EXIT"
    fi

    # --- Parse EvalReport STATUS ---
    STATUS=""
    PARSE_EXIT=0
    if STATUS=$(uv run python -c "
import sys
sys.path.insert(0, '${REPO}/.claude/scripts')
from eval_parser import load_eval_report
r = load_eval_report('${EVAL_FILE}')
print(r.status)
" 2>/dev/null); then :
    else PARSE_EXIT=$?; fi

    if [ "$PARSE_EXIT" -ne 0 ] || [ -z "$STATUS" ]; then
        # Malformed eval counts against MAX_TURNS per payload-contracts spec
        echo "WARN: failed to parse EvalReport for ${TARGET_ID} attempt ${ATTEMPT} (exit $PARSE_EXIT); treating as FAIL" >&2
        STATUS="FAIL"
    fi

    # --- Branch on STATUS ---
    case "$STATUS" in

        PASS)
            _revoke_caps
            echo "OK: ${TARGET_ID} attempt ${ATTEMPT} STATUS=PASS"
            exit 0
            ;;

        FAIL)
            if [ "$ATTEMPT" -lt "$MAX_TURNS" ]; then
                # D-18: archive prior test file before retry spawn
                sid_archive_dir="${ARCHIVE_DIR}/${SESSION_ID}"
                mkdir -p "$sid_archive_dir"
                ARCHIVE_TARGET="${sid_archive_dir}/test_${TARGET_ID}-attempt-${ATTEMPT}.py"
                if ! mv "$TEST_FILE" "$ARCHIVE_TARGET"; then
                    _revoke_caps
                    _emit_finding "archive_step_failed" \
                        "archive mv failed for ${TARGET_ID} attempt ${ATTEMPT}" \
                        "${TEST_FILE} -> ${ARCHIVE_TARGET}" \
                        "wire_tests" \
                        "Manually mv ${TEST_FILE} to ${ARCHIVE_TARGET} then re-run"
                    exit 1
                fi
                ATTEMPT=$(( ATTEMPT + 1 ))
                continue
            else
                # MAX_TURNS exhausted
                _revoke_caps
                _emit_finding "actor_critic_max_turns" \
                    "Author/Critic loop exhausted MAX_TURNS=${MAX_TURNS} for ${TARGET_ID}" \
                    ".iocane/wire-tests/eval_${TARGET_ID}.yaml final STATUS=FAIL" \
                    "wire_tests" \
                    "Review critique_notes in eval_${TARGET_ID}.yaml; revise contracts or rubric upstream then re-run"
                exit 0
            fi
            ;;

        AMBIGUOUS)
            _revoke_caps
            # D-19: increment lifetime counter
            _increment_lifetime
            _emit_finding "actor_critic_ambiguous" \
                "Critic returned AMBIGUOUS for ${TARGET_ID} at attempt ${ATTEMPT}" \
                ".iocane/wire-tests/eval_${TARGET_ID}.yaml STATUS=AMBIGUOUS" \
                "wire_tests" \
                "Review critique_notes in eval_${TARGET_ID}.yaml; clarify spec ambiguity then re-run (or create ${LIFETIME_SENTINEL} to reset lifetime counter)"
            exit 0
            ;;

        *)
            echo "WARN: unrecognised STATUS='${STATUS}' for ${TARGET_ID} attempt ${ATTEMPT}; treating as FAIL" >&2
            if [ "$ATTEMPT" -lt "$MAX_TURNS" ]; then
                sid_archive_dir="${ARCHIVE_DIR}/${SESSION_ID}"
                mkdir -p "$sid_archive_dir"
                ARCHIVE_TARGET="${sid_archive_dir}/test_${TARGET_ID}-attempt-${ATTEMPT}.py"
                if ! mv "$TEST_FILE" "$ARCHIVE_TARGET" 2>/dev/null; then
                    echo "WARN: archive mv failed for unknown STATUS; continuing without archive" >&2
                fi
                ATTEMPT=$(( ATTEMPT + 1 ))
                continue
            else
                _revoke_caps
                _emit_finding "actor_critic_max_turns" \
                    "MAX_TURNS=${MAX_TURNS} exhausted (final STATUS=${STATUS}) for ${TARGET_ID}" \
                    ".iocane/wire-tests/eval_${TARGET_ID}.yaml" \
                    "wire_tests" \
                    "Review eval_${TARGET_ID}.yaml and re-run"
                exit 0
            fi
            ;;
    esac

done

# Loop exit without terminal state (shouldn't reach here given the case branches above)
_revoke_caps
echo "ERROR: loop exited without terminal state for ${TARGET_ID}" >&2
exit 1

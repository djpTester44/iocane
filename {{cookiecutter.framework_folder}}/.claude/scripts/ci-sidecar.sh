#!/usr/bin/env bash
# CI Sidecar: Full suite regression detection (advisory, never blocking)
# Subcommands: pre-wave | post-wave | diff
# Always exits 0 -- failures are logged, not gated.
#
# Usage:
#   bash .claude/scripts/ci-sidecar.sh pre-wave
#   bash .claude/scripts/ci-sidecar.sh post-wave
#   bash .claude/scripts/ci-sidecar.sh diff
#
# Environment overrides:
#   CI_ENABLED   -- override ci.enabled config (true/false)
#   CI_TIMEOUT   -- override ci.timeout config (e.g. 5m)
#   REPO_ROOT    -- auto-detected via git if not set

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- Configuration ---
REPO_ROOT="${REPO_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null)}"
CONFIG_FILE="$REPO_ROOT/.claude/iocane.config.yaml"

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

# --- Phase gate: CI-REGRESSION tag infrastructure ---
HOOK_FILE="$REPO_ROOT/.claude/hooks/backlog-tag-validate.sh"
if ! grep -q "CI-REGRESSION" "$HOOK_FILE" 2>/dev/null; then
    echo "ERROR: [CI-REGRESSION] tag not registered in $HOOK_FILE"
    echo "  Complete Phase 2 (tag infrastructure) before running the CI sidecar."
    echo "  Add CI-REGRESSION (and CI-COLLECTION-ERROR) to the valid tags list in backlog-tag-validate.sh."
    exit 0
fi

# --- Resolve config values ---
_cfg_ci_enabled=$(_cfg_read "ci.enabled")
CI_ENABLED="${CI_ENABLED:-${_cfg_ci_enabled:-true}}"

_cfg_ci_timeout=$(_cfg_read "ci.timeout")
CI_TIMEOUT="${CI_TIMEOUT:-${_cfg_ci_timeout:-5m}}"

if [ "$CI_ENABLED" = "false" ]; then
    echo "ci-sidecar: CI disabled (ci.enabled=false). Skipping."
    exit 0
fi

# --- Report storage ---
CI_DIR="$REPO_ROOT/.iocane/ci"
mkdir -p "$CI_DIR"

PRE_REPORT="$CI_DIR/ci-wave-report.json"
POST_REPORT="$CI_DIR/ci-wave-report-post.json"
BACKLOG_FILE="$REPO_ROOT/plans/backlog.md"

# --- Helper: run the test suite, return output in a temp file ---
# Sets global: SUITE_OUTPUT_FILE, SUITE_EXIT_CODE
run_suite() {
    local output_file
    output_file=$(mktemp)
    local exit_code=0

    timeout "$CI_TIMEOUT" uv run rtk pytest --tb=line -q --no-header 2>&1 > "$output_file" || exit_code=$?

    SUITE_OUTPUT_FILE="$output_file"
    SUITE_EXIT_CODE="$exit_code"
}

# --- Helper: parse pytest --tb=line -q --no-header output ---
# Sets global: PARSE_FAILURES_FILE, PARSE_ERRORS_FILE,
#              PARSE_TOTAL, PARSE_PASSED, PARSE_FAILED, PARSE_ERRORS_COUNT, PARSE_DURATION
parse_output() {
    local output_file="$1"

    PARSE_FAILURES_FILE=$(mktemp)
    PARSE_ERRORS_FILE=$(mktemp)

    # Parse failures and collection errors via awk
    awk '
        /^FAILED / {
            # FAILED tests/foo.py::test_bar - ErrorMsg
            line = $0
            sub(/^FAILED /, "", line)
            # Split on " - " to separate test id from error message
            idx = index(line, " - ")
            if (idx > 0) {
                test_id = substr(line, 1, idx - 1)
                err_msg = substr(line, idx + 3)
            } else {
                test_id = line
                err_msg = ""
            }
            print test_id "\t" err_msg
        }
    ' "$output_file" > "$PARSE_FAILURES_FILE"

    awk '
        /^ERROR / {
            line = $0
            sub(/^ERROR /, "", line)
            # Collection errors: "tests/test_foo.py - ErrorMsg" or just a path
            idx = index(line, " - ")
            if (idx > 0) {
                test_id = substr(line, 1, idx - 1)
                err_msg = substr(line, idx + 3)
            } else {
                test_id = line
                err_msg = ""
            }
            print test_id "\t" err_msg
        }
    ' "$output_file" > "$PARSE_ERRORS_FILE"

    # Parse summary line: "2 failed, 43 passed in 12.34s" or "45 passed in 5.00s" etc.
    local summary_line
    summary_line=$(grep -E '[0-9]+ (failed|passed|error)' "$output_file" | tail -1 || true)

    PARSE_TOTAL=0
    PARSE_PASSED=0
    PARSE_FAILED=0
    PARSE_ERRORS_COUNT=0
    PARSE_DURATION="0s"

    if [ -n "$summary_line" ]; then
        PARSE_PASSED=$(echo "$summary_line" | grep -oE '[0-9]+ passed' | grep -oE '[0-9]+' || echo 0)
        PARSE_FAILED=$(echo "$summary_line" | grep -oE '[0-9]+ failed' | grep -oE '[0-9]+' || echo 0)
        PARSE_ERRORS_COUNT=$(echo "$summary_line" | grep -oE '[0-9]+ error' | grep -oE '[0-9]+' || echo 0)
        PARSE_DURATION=$(echo "$summary_line" | grep -oE '[0-9]+\.[0-9]+s' || echo "0s")
        PARSE_TOTAL=$(( PARSE_PASSED + PARSE_FAILED + PARSE_ERRORS_COUNT ))
    fi

    # Default 0 if empty
    PARSE_PASSED="${PARSE_PASSED:-0}"
    PARSE_FAILED="${PARSE_FAILED:-0}"
    PARSE_ERRORS_COUNT="${PARSE_ERRORS_COUNT:-0}"
    PARSE_TOTAL="${PARSE_TOTAL:-0}"
}

# --- Helper: determine report status from exit code and parse results ---
resolve_status() {
    local exit_code="$1"
    if [ "$exit_code" -eq 124 ]; then
        echo "TIMEOUT"
    elif [ "$exit_code" -eq 5 ]; then
        echo "NO_TESTS"
    elif [ "$exit_code" -ne 0 ] && [ "${PARSE_TOTAL:-0}" -eq 0 ]; then
        echo "COLLECTION_ERROR"
    else
        echo "COMPLETE"
    fi
}

# --- Helper: write JSON report ---
write_report() {
    local report_file="$1"
    local failures_file="$2"
    local errors_file="$3"
    local exit_code="$4"
    local status="$5"

    local timestamp branch commit_sha
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date +"%Y-%m-%dT%H:%M:%SZ")
    commit_sha=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
    branch=$(git branch --show-current 2>/dev/null || echo "unknown")

    python -c "
import json
import sys

failures_file = sys.argv[1]
errors_file   = sys.argv[2]
report_file   = sys.argv[3]

failures = []
with open(failures_file) as f:
    for line in f:
        line = line.rstrip('\n')
        if '\t' in line:
            parts = line.split('\t', 1)
            failures.append({'test': parts[0].strip(), 'error': parts[1].strip()})
        elif line.strip():
            failures.append({'test': line.strip(), 'error': ''})

collection_errors = []
with open(errors_file) as f:
    for line in f:
        line = line.rstrip('\n')
        if '\t' in line:
            parts = line.split('\t', 1)
            collection_errors.append({'test': parts[0].strip(), 'error': parts[1].strip()})
        elif line.strip():
            collection_errors.append({'test': line.strip(), 'error': ''})

report = {
    'metadata': {
        'timestamp':       sys.argv[4],
        'commit_sha':      sys.argv[5],
        'branch':          sys.argv[6],
        'status':          sys.argv[7],
        'ci_timeout':      sys.argv[8],
        'pytest_exit_code': int(sys.argv[9]),
    },
    'summary': {
        'total':    int(sys.argv[10]),
        'passed':   int(sys.argv[11]),
        'failed':   int(sys.argv[12]),
        'errors':   int(sys.argv[13]),
        'duration': sys.argv[14],
    },
    'failures':          failures,
    'collection_errors': collection_errors,
}

with open(report_file, 'w') as out:
    json.dump(report, out, indent=2)
    out.write('\n')
" \
        "$failures_file" \
        "$errors_file" \
        "$report_file" \
        "$timestamp" \
        "$commit_sha" \
        "$branch" \
        "$status" \
        "$CI_TIMEOUT" \
        "$exit_code" \
        "${PARSE_TOTAL:-0}" \
        "${PARSE_PASSED:-0}" \
        "${PARSE_FAILED:-0}" \
        "${PARSE_ERRORS_COUNT:-0}" \
        "${PARSE_DURATION:-0s}"

    echo "ci-sidecar: report written -> $report_file"
}

# --- Helper: run diff between pre and post reports ---
# Stdout is ONLY the final "0" or "1" (appended flag) so callers can capture it.
# All human-readable output goes to stderr.
run_diff() {
    if [ ! -f "$PRE_REPORT" ]; then
        echo "ci-sidecar diff: no pre-wave report found at $PRE_REPORT" >&2
        echo 0
        return 0
    fi
    if [ ! -f "$POST_REPORT" ]; then
        echo "ci-sidecar diff: no post-wave report found at $POST_REPORT" >&2
        echo 0
        return 0
    fi

    local pre_commit post_commit
    pre_commit=$(python -c "import json; d=json.load(open('$PRE_REPORT')); print(d['metadata']['commit_sha'])")
    post_commit=$(python -c "import json; d=json.load(open('$POST_REPORT')); print(d['metadata']['commit_sha'])")

    # Extract sorted test-id lists
    local pre_failures_sorted post_failures_sorted
    pre_failures_sorted=$(mktemp)
    post_failures_sorted=$(mktemp)
    local pre_errors_sorted post_errors_sorted
    pre_errors_sorted=$(mktemp)
    post_errors_sorted=$(mktemp)

    python -c "
import json, sys
report = json.load(open(sys.argv[1]))
for item in report.get('failures', []):
    print(item['test'])
" "$PRE_REPORT" | sort > "$pre_failures_sorted"

    python -c "
import json, sys
report = json.load(open(sys.argv[1]))
for item in report.get('failures', []):
    print(item['test'])
" "$POST_REPORT" | sort > "$post_failures_sorted"

    python -c "
import json, sys
report = json.load(open(sys.argv[1]))
for item in report.get('collection_errors', []):
    print(item['test'])
" "$PRE_REPORT" | sort > "$pre_errors_sorted"

    python -c "
import json, sys
report = json.load(open(sys.argv[1]))
for item in report.get('collection_errors', []):
    print(item['test'])
" "$POST_REPORT" | sort > "$post_errors_sorted"

    # New regressions: in post but not pre
    local new_failures new_collection_errors resolved_failures
    new_failures=$(comm -23 "$post_failures_sorted" "$pre_failures_sorted" || true)
    new_collection_errors=$(comm -23 "$post_errors_sorted" "$pre_errors_sorted" || true)
    resolved_failures=$(comm -23 "$pre_failures_sorted" "$post_failures_sorted" || true)

    local appended=0

    if [ -n "$resolved_failures" ]; then
        echo "ci-sidecar: resolved failures (pre->post):" >&2
        echo "$resolved_failures" | while IFS= read -r test_id; do
            echo "  RESOLVED: $test_id" >&2
        done
    fi

    if [ -n "$new_failures" ]; then
        echo "ci-sidecar: new regressions detected:" >&2
        echo "$new_failures" | while IFS= read -r test_id; do
            echo "  [CI-REGRESSION] $test_id" >&2
        done
        append_backlog_failures "$new_failures" "$pre_commit" "$post_commit"
        appended=1
    fi

    if [ -n "$new_collection_errors" ]; then
        echo "ci-sidecar: new collection errors detected:" >&2
        echo "$new_collection_errors" | while IFS= read -r test_id; do
            echo "  [CI-COLLECTION-ERROR] $test_id" >&2
        done
        append_backlog_collection_errors "$new_collection_errors" "$pre_commit" "$post_commit"
        appended=1
    fi

    if [ "$appended" -eq 0 ]; then
        echo "ci-sidecar diff: no new regressions." >&2
    fi

    rm -f "$pre_failures_sorted" "$post_failures_sorted" "$pre_errors_sorted" "$post_errors_sorted"

    echo "$appended"
}

# --- Helper: look up error message for a test id from the post report ---
_get_error_for_test() {
    local report_file="$1"
    local test_id="$2"
    local field="${3:-failures}"
    python -c "
import json, sys
report = json.load(open(sys.argv[1]))
for item in report.get(sys.argv[3], []):
    if item['test'] == sys.argv[2]:
        print(item.get('error', ''))
        break
" "$report_file" "$test_id" "$field" 2>/dev/null || true
}

# --- Helper: append [CI-REGRESSION] entries to backlog ---
append_backlog_failures() {
    local test_ids="$1"
    local pre_commit="$2"
    local post_commit="$3"

    if [ ! -f "$BACKLOG_FILE" ]; then
        echo "WARNING: $BACKLOG_FILE not found -- cannot append backlog entries." >&2
        return 0
    fi

    echo "$test_ids" | while IFS= read -r test_id; do
        [ -z "$test_id" ] && continue
        local err_msg
        err_msg=$(_get_error_for_test "$POST_REPORT" "$test_id" "failures")
        printf '\n- [ ] [CI-REGRESSION] %s -- new failure after wave merge\n' "$test_id" >> "$BACKLOG_FILE"
        printf '  - Source: ci-sidecar post-wave\n' >> "$BACKLOG_FILE"
        printf '  - Pre-wave commit: %s\n' "$pre_commit" >> "$BACKLOG_FILE"
        printf '  - Post-wave commit: %s\n' "$post_commit" >> "$BACKLOG_FILE"
        printf '  - Error: %s\n' "$err_msg" >> "$BACKLOG_FILE"
    done
}

# --- Helper: append [CI-COLLECTION-ERROR] entries to backlog ---
append_backlog_collection_errors() {
    local test_ids="$1"
    local pre_commit="$2"
    local post_commit="$3"

    if [ ! -f "$BACKLOG_FILE" ]; then
        echo "WARNING: $BACKLOG_FILE not found -- cannot append backlog entries." >&2
        return 0
    fi

    echo "$test_ids" | while IFS= read -r test_id; do
        [ -z "$test_id" ] && continue
        local err_msg
        err_msg=$(_get_error_for_test "$POST_REPORT" "$test_id" "collection_errors")
        printf '\n- [ ] [CI-COLLECTION-ERROR] %s -- new collection error after wave merge\n' "$test_id" >> "$BACKLOG_FILE"
        printf '  - Source: ci-sidecar post-wave\n' >> "$BACKLOG_FILE"
        printf '  - Pre-wave commit: %s\n' "$pre_commit" >> "$BACKLOG_FILE"
        printf '  - Post-wave commit: %s\n' "$post_commit" >> "$BACKLOG_FILE"
        printf '  - Error: %s\n' "$err_msg" >> "$BACKLOG_FILE"
    done
}

# =============================================================================
# Subcommand: pre-wave
# =============================================================================
cmd_pre_wave() {
    echo "ci-sidecar: pre-wave baseline collection (timeout=$CI_TIMEOUT)"

    # Check if existing baseline matches current HEAD
    if [ -f "$PRE_REPORT" ]; then
        local report_sha
        report_sha=$(python -c "import json; d=json.load(open('$PRE_REPORT')); print(d['metadata']['commit_sha'])" 2>/dev/null || echo "")
        local current_sha
        current_sha=$(git rev-parse HEAD 2>/dev/null || echo "")
        if [ -n "$report_sha" ] && [ "$report_sha" = "$current_sha" ]; then
            echo "ci-sidecar: baseline current (commit=$current_sha). Skipping pre-wave run."
            return 0
        fi
    fi

    run_suite
    parse_output "$SUITE_OUTPUT_FILE"

    local status
    status=$(resolve_status "$SUITE_EXIT_CODE")

    write_report "$PRE_REPORT" "$PARSE_FAILURES_FILE" "$PARSE_ERRORS_FILE" "$SUITE_EXIT_CODE" "$status"

    echo "ci-sidecar: pre-wave complete. status=$status passed=${PARSE_PASSED:-0} failed=${PARSE_FAILED:-0} errors=${PARSE_ERRORS_COUNT:-0}"

    rm -f "$SUITE_OUTPUT_FILE" "$PARSE_FAILURES_FILE" "$PARSE_ERRORS_FILE"
}

# =============================================================================
# Subcommand: post-wave
# =============================================================================
cmd_post_wave() {
    echo "ci-sidecar: post-wave full suite run (timeout=$CI_TIMEOUT)"

    run_suite
    parse_output "$SUITE_OUTPUT_FILE"

    local status
    status=$(resolve_status "$SUITE_EXIT_CODE")

    write_report "$POST_REPORT" "$PARSE_FAILURES_FILE" "$PARSE_ERRORS_FILE" "$SUITE_EXIT_CODE" "$status"

    echo "ci-sidecar: post-wave complete. status=$status passed=${PARSE_PASSED:-0} failed=${PARSE_FAILED:-0} errors=${PARSE_ERRORS_COUNT:-0}"

    rm -f "$SUITE_OUTPUT_FILE" "$PARSE_FAILURES_FILE" "$PARSE_ERRORS_FILE"

    # Diff and backlog append
    local appended=0
    appended=$(run_diff)

    # Promote post to baseline
    cp "$POST_REPORT" "$PRE_REPORT"
    echo "ci-sidecar: promoted post-wave report to baseline."

    # If backlog was modified, assign IDs
    if [ "${appended:-0}" -eq 1 ]; then
        local id_script="$SCRIPT_DIR/assign-backlog-ids.sh"
        if [ -f "$id_script" ]; then
            echo "ci-sidecar: assigning backlog IDs..."
            bash "$id_script" || echo "WARNING: assign-backlog-ids.sh failed (non-blocking)."
        else
            echo "WARNING: $id_script not found -- backlog IDs not assigned."
        fi
    fi
}

# =============================================================================
# Subcommand: diff
# =============================================================================
cmd_diff() {
    echo "ci-sidecar: running diff on existing reports (no test re-collection)"
    # Discard the numeric stdout return value -- we only want the stderr output here.
    run_diff > /dev/null
}

# =============================================================================
# Subcommand dispatch
# =============================================================================
SUBCOMMAND="${1:-}"

case "$SUBCOMMAND" in
    pre-wave)
        cmd_pre_wave
        ;;
    post-wave)
        cmd_post_wave
        ;;
    diff)
        cmd_diff
        ;;
    *)
        echo "Usage: bash ci-sidecar.sh <subcommand>"
        echo ""
        echo "Subcommands:"
        echo "  pre-wave   -- collect baseline test results before a dispatch wave"
        echo "  post-wave  -- collect post-wave results, diff against baseline, append regressions to backlog"
        echo "  diff       -- re-run diff on existing report files without re-collecting tests"
        echo ""
        echo "Environment overrides:"
        echo "  CI_ENABLED=$CI_ENABLED (config: ci.enabled)"
        echo "  CI_TIMEOUT=$CI_TIMEOUT (config: ci.timeout)"
        ;;
esac

exit 0

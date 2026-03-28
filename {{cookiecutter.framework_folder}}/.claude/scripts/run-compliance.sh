#!/usr/bin/env bash
# .claude/scripts/run-compliance.sh
#
# Consolidated compliance runner used by /io-review and /gap-analysis.
# Runs all compliance checks and outputs actionable findings only.
#
# Usage:
#   bash .claude/scripts/run-compliance.sh <target_path> [<target_path> ...]
#
# Exit code:
#   0 — all checks passed
#   1 — one or more checks found violations

set -euo pipefail

if [ "$#" -eq 0 ]; then
    echo "Usage: run-compliance.sh <target_path> [<target_path> ...]" >&2
    exit 1
fi

TARGETS=("$@")
FAILED=0

run_check() {
    local label="$1"
    shift
    local output
    if output=$("$@" 2>&1); then
        echo "  PASS  $label"
    else
        echo "  FAIL  $label"
        echo "$output" | grep -v '^$' | sed 's/^/        /'
        FAILED=1
    fi
}

echo "=== Compliance: ${TARGETS[*]} ==="

run_check "ruff"         uv run rtk ruff check "${TARGETS[@]}"
run_check "mypy"         uv run mypy "${TARGETS[@]}"
run_check "lint-imports" uv run rtk lint-imports
run_check "bandit"       uv run bandit -q -ll "${TARGETS[@]}"
run_check "di-check"     uv run python .claude/scripts/check_di_compliance.py "${TARGETS[@]}"

echo ""
if [ "$FAILED" -eq 0 ]; then
    echo "All compliance checks passed."
else
    echo "Compliance failures detected. Fix before proceeding."
fi

exit "$FAILED"

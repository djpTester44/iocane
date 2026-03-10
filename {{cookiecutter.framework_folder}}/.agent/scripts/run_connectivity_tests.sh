#!/usr/bin/env bash
# .agent/scripts/run_connectivity_tests.sh
#
# Reads all connectivity test gate commands from plans/plan.md,
# runs each one, and reports PASS/FAIL per CT-ID.
#
# Output: structured table — CT-ID | Gate Command | PASS/FAIL
#
# Used by /review and /gap-analysis to verify seam integrity.
#
# Usage:
#   bash .agent/scripts/run_connectivity_tests.sh
#   bash .agent/scripts/run_connectivity_tests.sh --cp CP-01   # filter by checkpoint
#   bash .agent/scripts/run_connectivity_tests.sh --json       # machine-readable output

set -uo pipefail

PLAN_FILE="plans/plan.md"
FILTER_CP=""
JSON_OUTPUT=false

# --- Preflight: uv must be on PATH ---
if ! command -v uv &>/dev/null; then
    echo "ERROR: uv not found on PATH. Cannot execute gate commands." >&2
    exit 1
fi

# --- Argument parsing ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --cp)
            FILTER_CP="$2"
            shift 2
            ;;
        --json)
            JSON_OUTPUT=true
            shift
            ;;
        *)
            echo "Unknown argument: $1" >&2
            echo "Usage: $0 [--cp CP-ID] [--json]" >&2
            exit 1
            ;;
    esac
done

# --- Verify plan.md exists ---
if [ ! -f "$PLAN_FILE" ]; then
    echo "ERROR: $PLAN_FILE not found. Run /io-checkpoint to generate it." >&2
    exit 1
fi

# --- Extract connectivity tests from plan.md ---
# Expected format in plan.md:
#
#   ## Connectivity Tests
#
#   ### CT-001: [Description]
#   **Seam:** CP-01 -> CP-02
#   **Gate command:** `pytest tests/path/test_seam.py::test_name`
#
# Also handles inline checkpoint sections with connectivity test sub-blocks.

CT_DATA=$(python3 -c "
import re, sys

with open('$PLAN_FILE') as f:
    content = f.read()

# Match the Connectivity Tests section (may appear at document level or within checkpoints)
# Pattern: CT-NNN identifier followed by a gate command on the same or next non-empty line
pattern = re.compile(
    r'###\s+(CT-\d+)[^\n]*\n'          # CT-ID header
    r'(?:.*?\n)*?'                      # optional lines (seam description, etc.)
    r'\*\*(?:Gate command|gate command):\*\*\s*\`?([^\`\n]+)\`?',  # gate command
    re.MULTILINE
)

results = []
for m in pattern.finditer(content):
    ct_id = m.group(1).strip()
    gate_cmd = m.group(2).strip()

    # Extract seam/checkpoint association if present
    seam_match = re.search(
        r'###\s+' + re.escape(ct_id) + r'[^\n]*\n(.*?)\*\*(?:Gate|gate)',
        content, re.DOTALL
    )
    seam = ''
    if seam_match:
        seam_block = seam_match.group(1)
        seam_line = re.search(r'\*\*Seam:\*\*\s*(.+)', seam_block)
        if seam_line:
            seam = seam_line.group(1).strip()

    results.append({'ct_id': ct_id, 'gate_cmd': gate_cmd, 'seam': seam})

if not results:
    print('NONE')
else:
    for r in results:
        # Tab-separated: CT-ID \t gate_cmd \t seam
        print(r['ct_id'] + '\t' + r['gate_cmd'] + '\t' + r['seam'])
" 2>/dev/null)

if [ "$CT_DATA" = "NONE" ] || [ -z "$CT_DATA" ]; then
    echo "No connectivity tests found in $PLAN_FILE."
    echo "Ensure /io-checkpoint has defined tests in a '## Connectivity Tests' section."
    exit 0
fi

# --- Run each connectivity test and collect results ---
PASS_COUNT=0
FAIL_COUNT=0
declare -a TABLE_ROWS=()
declare -a JSON_ROWS=()

while IFS=$'\t' read -r CT_ID GATE_CMD SEAM; do
    # Apply --cp filter if specified
    if [ -n "$FILTER_CP" ] && [ -n "$SEAM" ]; then
        if ! echo "$SEAM" | grep -q "$FILTER_CP"; then
            continue
        fi
    fi

    # Run the gate command safely — no eval, word-split into array
    read -ra CMD_ARRAY <<< "$GATE_CMD"
    CMD_OUTPUT=$("${CMD_ARRAY[@]}" 2>&1)
    CMD_EXIT=$?

    if [ $CMD_EXIT -eq 0 ]; then
        STATUS="PASS"
        PASS_COUNT=$((PASS_COUNT + 1))
    else
        STATUS="FAIL"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi

    # Truncate long gate commands for table display
    DISPLAY_CMD="$GATE_CMD"
    if [ ${#DISPLAY_CMD} -gt 60 ]; then
        DISPLAY_CMD="${DISPLAY_CMD:0:57}..."
    fi

    TABLE_ROWS+=("$CT_ID|$DISPLAY_CMD|$STATUS|$SEAM")

    # Capture first failure line for JSON output
    FAIL_DETAIL=""
    if [ "$STATUS" = "FAIL" ]; then
        FAIL_DETAIL=$(echo "$CMD_OUTPUT" | grep -E "^(FAILED|ERROR|AssertionError)" | head -1 || echo "exit code $CMD_EXIT")
    fi
    JSON_ROWS+=("{\"ct_id\":\"$CT_ID\",\"gate_cmd\":\"$GATE_CMD\",\"seam\":\"$SEAM\",\"status\":\"$STATUS\",\"detail\":\"$FAIL_DETAIL\"}")

done <<< "$CT_DATA"

TOTAL=$((PASS_COUNT + FAIL_COUNT))

# --- Output ---
if $JSON_OUTPUT; then
    # Machine-readable JSON for /review and /gap-analysis tooling
    python3 -c "
import json, sys
rows = [$(IFS=,; echo "${JSON_ROWS[*]:-}")]
print(json.dumps({
    'total': $TOTAL,
    'pass': $PASS_COUNT,
    'fail': $FAIL_COUNT,
    'results': rows
}, indent=2))
"
else
    # Human-readable table
    echo ""
    echo "Connectivity Test Results"
    echo "========================="
    printf "%-10s %-62s %-6s %s\n" "CT-ID" "Gate Command" "Result" "Seam"
    printf "%-10s %-62s %-6s %s\n" "----------" "--------------------------------------------------------------" "------" "----"

    for row in "${TABLE_ROWS[@]:-}"; do
        IFS='|' read -r CT_ID DISPLAY_CMD STATUS SEAM <<< "$row"
        printf "%-10s %-62s %-6s %s\n" "$CT_ID" "$DISPLAY_CMD" "$STATUS" "$SEAM"
    done

    echo ""
    echo "Summary: $PASS_COUNT/$TOTAL PASS | $FAIL_COUNT/$TOTAL FAIL"

    if [ $FAIL_COUNT -gt 0 ]; then
        echo ""
        echo "CONNECTIVITY FAILURES DETECTED."
        echo "Failing seams must be green before /review can approve this checkpoint batch."
        exit 1
    else
        echo ""
        echo "All connectivity tests PASS."
        exit 0
    fi
fi
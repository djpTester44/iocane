#!/usr/bin/env bash
# .claude/scripts/spawn-evaluator.sh
#
# Spawn a Sonnet sub-agent (evaluator) to validate a constructor's output for
# one finding. Evaluators run after all constructors complete (Wave 2 of dispatch).
#
# Usage:
#   bash .claude/scripts/spawn-evaluator.sh --finding-id 1
#
# Reads model from iocane.config.yaml (models.tier2).
# Logs to plans/harness-evo-{date}.log.
# Runs claude -p synchronously (caller manages parallelism via &).
# Does NOT modify harness artifacts -- read-only evaluation.

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null)}"
if [ -z "$REPO_ROOT" ]; then
    echo "spawn-evaluator: ERROR: could not determine repo root." >&2
    exit 1
fi

FINDING_ID=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --finding-id) FINDING_ID="$2"; shift 2 ;;
        *) echo "spawn-evaluator: unknown arg: $1" >&2; exit 1 ;;
    esac
done

if [ -z "$FINDING_ID" ]; then
    echo "spawn-evaluator: ERROR: --finding-id is required." >&2
    exit 1
fi

RESULT_FILE="$REPO_ROOT/plans/evo-findings/finding-${FINDING_ID}-result.md"

if [ ! -f "$RESULT_FILE" ]; then
    echo "spawn-evaluator: ERROR: result file not found: $RESULT_FILE" >&2
    exit 1
fi

CONFIG_FILE="$REPO_ROOT/.claude/iocane.config.yaml"

_cfg_read() {
    local key="$1"
    local section="${key%%.*}"
    local subkey="${key#*.}"
    awk "/^${section}:/{found=1; next} found && /^[^ ]/{exit} found && /^  ${subkey}:/{print; exit}" "$CONFIG_FILE" 2>/dev/null \
        | sed 's/^[^:]*:[[:space:]]*//' \
        | sed 's/[[:space:]]*#.*//' \
        | tr -d '"' \
        | tr -d '\r' \
        | head -1
}

_cfg_model=$(_cfg_read "models.tier2")
MODEL="${IOCANE_MODEL:-${_cfg_model:-claude-sonnet-4-6}}"

LOG_DATE="$(date +%Y-%m-%d)"
LOG_FILE="$REPO_ROOT/plans/harness-evo-${LOG_DATE}.log"

echo "spawn-evaluator: finding=${FINDING_ID} model=$MODEL" >&2

cd "$REPO_ROOT"
claude -p \
    --model "$MODEL" \
    --max-turns 10 \
    --allowedTools "Read,Write,Glob,Grep" \
    <<PROMPT >> "$LOG_FILE" 2>&1
You are a harness-author evaluator agent. Your job is to validate the constructor
output for finding ${FINDING_ID}. You do NOT modify any harness artifacts.

Step 1: Load your evaluation context.
  Read .claude/skills/harness-author/SKILL.md
  Read .claude/skills/harness-author/references/ (especially the evals reference).

Step 2: Read the constructor result file:
  plans/evo-findings/finding-${FINDING_ID}-result.md

  From this file, identify:
  - The Target path (artifact that was authored or edited)
  - The Disposition (HOOK-CANDIDATE, RULE-CANDIDATE, etc.)
  - The Action taken (authored|edited|deferred|not-applicable)

Step 3: If Action is "authored" or "edited":
  Read the artifact at the Target path.
  Run the relevant subset of harness-author evals for this artifact type:
  - For hooks: earned-prose filter, structural template compliance
  - For rules: cost-model framing, no procedure prose
  - For commands: gate structure, verifiable steps
  - For skills: domain template, variance-reduction focus

Step 4: Write evaluation result to:
  plans/evo-findings/finding-${FINDING_ID}-eval.md

  Eval file format:
  # Evaluator Result: Finding ${FINDING_ID}
  - **Target:** [target path]
  - **Disposition:** [disposition]
  - **Constructor action:** [action]
  - **Verdict:** PASS | FAIL | DEFERRED
  - **Findings:** [bulleted list of issues, or "None" if PASS]
  - **Token impact:** [estimated token cost of new/changed artifact]
PROMPT

echo "spawn-evaluator: finding=${FINDING_ID} complete." >&2

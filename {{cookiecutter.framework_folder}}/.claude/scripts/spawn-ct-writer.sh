#!/usr/bin/env bash
# .claude/scripts/spawn-ct-writer.sh
#
# Dispatches a Tier-3a CT Author session for one CP. Writes all
# connectivity tests whose target_cp == $CP_ID into
# tests/connectivity/*.py.
#
# Role contract: exports IOCANE_ROLE=ct_author + IOCANE_CP_ID=<id> so
# session-start.sh can inject role-scoped orientation into the new
# claude -p process.
#
# Usage:
#   bash .claude/scripts/spawn-ct-writer.sh --cp-id <CP-ID>
#
# --cp-id must match ^CP-\d+(R\d+)?$ -- identifier-shaped CP ID, no
# path traversal, no shell metacharacters. Pattern mirrors the tester
# stem regex hardening (/challenge Phase 3 finding).
#
# Outcome is success when all target_cp-scoped CTs for this CP are
# written to tests/connectivity/. If the task has zero CTs with
# target_cp == this CP, the script exits 0 -- dispatcher treats this
# as a clean skip.
#
# Reads model from iocane.config.yaml (models.ct_author). Falls back
# to claude-sonnet-4-6 if the key is absent, with stderr warning.

set -euo pipefail

# --- Arg parsing ---
CP_ID=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --cp-id) CP_ID="$2"; shift 2 ;;
        *) echo "spawn-ct-writer: unknown arg: $1" >&2; exit 1 ;;
    esac
done

if [ -z "$CP_ID" ]; then
    echo "spawn-ct-writer: --cp-id <CP-ID> required" >&2
    exit 1
fi

# Identifier-shaped CP-ID only. Blocks path traversal, shell
# metacharacters, whitespace, newlines. Matches CP-NN or CP-NNR<n>.
if [[ ! "$CP_ID" =~ ^CP-[0-9]+(R[0-9]+)?$ ]]; then
    echo "spawn-ct-writer: --cp-id must match ^CP-[0-9]+(R[0-9]+)?\$, got '$CP_ID'" >&2
    exit 1
fi

# --- Resolve consumer repo root ---
REPO_ROOT="${REPO_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null)}"
if [ -z "$REPO_ROOT" ]; then
    echo "spawn-ct-writer: not in a git repo" >&2
    exit 1
fi

# --- Preflight gates ---

# Architect-mode sentinel: if /io-architect is mid-amend, Protocols
# are mid-mutation and CTs authored now would be against stale
# contracts. Mirrors spawn-tester.sh precedent.
#
# Defense-in-depth: the primary architect-mode gate lives in
# dispatch-agents.sh (pre-worktree, parent CWD guaranteed). This
# check remains for standalone user-invoked CT-writer spawns that
# bypass the dispatcher. In the dispatcher path REPO_ROOT resolves
# to the worktree (dispatcher cds in before spawning), so this check
# is a no-op there; the dispatcher gate caught it first.
if [ -f "$REPO_ROOT/.iocane/architect-mode" ]; then
    echo "spawn-ct-writer: .iocane/architect-mode sentinel is set -- resolve before dispatch" >&2
    exit 1
fi

TASK_FILE="$REPO_ROOT/plans/tasks/${CP_ID}.yaml"
if [ ! -f "$TASK_FILE" ]; then
    echo "spawn-ct-writer: $TASK_FILE not found" >&2
    exit 1
fi

if [ ! -f "$REPO_ROOT/plans/plan.yaml" ]; then
    echo "spawn-ct-writer: plans/plan.yaml not found" >&2
    exit 1
fi
if [ ! -f "$REPO_ROOT/plans/seams.yaml" ]; then
    echo "spawn-ct-writer: plans/seams.yaml not found" >&2
    exit 1
fi

# Task file must parse cleanly via Pydantic; bail fast if not.
if ! uv run python -c "
import sys; sys.path.insert(0, '$REPO_ROOT/.claude/scripts')
from task_parser import load_task
load_task('$TASK_FILE')
" 2>/dev/null; then
    echo "spawn-ct-writer: $TASK_FILE failed Pydantic validation" >&2
    exit 1
fi

# Count target_cp-scoped CTs. Zero CTs = clean skip (dispatcher
# expects exit 0 and no work done).
CT_COUNT=$(uv run python -c "
import sys; sys.path.insert(0, '$REPO_ROOT/.claude/scripts')
from task_parser import load_task
t = load_task('$TASK_FILE')
print(len(t.connectivity_tests))
" 2>/dev/null || echo "0")

if [ "$CT_COUNT" -eq 0 ]; then
    echo "spawn-ct-writer: cp=${CP_ID} no CTs for this CP, skipping" >&2
    exit 0
fi

# --- Config read (with in-code fallback + bounds validation) ---
CONFIG_FILE="$REPO_ROOT/.claude/iocane.config.yaml"
DEFAULT_MODEL="claude-sonnet-4-6"

_cfg_read() {
    local section="$1"
    local subkey="$2"
    awk "/^${section}:/{f=1;next} f&&/^[^ ]/{exit} f&&/^  ${subkey}:/{print;exit}" "$CONFIG_FILE" 2>/dev/null \
        | sed 's/^[^:]*:[[:space:]]*//;s/[[:space:]]*#.*//;s/"//g' \
        | tr -d '\r' \
        | head -1
}

_cfg_model=$(_cfg_read models ct_author)

# Bounds validation: reject empty, whitespace-only, or obvious-invalid
# values. Matches handle_amend_signal.py:141-166 pattern.
_cfg_model_trimmed=$(printf '%s' "$_cfg_model" | tr -d '[:space:]')
if [ -z "$_cfg_model_trimmed" ]; then
    MODEL="${IOCANE_MODEL:-$DEFAULT_MODEL}"
    if [ -z "${IOCANE_MODEL:-}" ]; then
        echo "spawn-ct-writer: WARN: models.ct_author not found in $CONFIG_FILE; falling back to $MODEL" >&2
    fi
else
    MODEL="${IOCANE_MODEL:-$_cfg_model}"
fi

# --- Export role contract + ensure consumer cwd ---
export IOCANE_ROLE=ct_author
export IOCANE_CP_ID="$CP_ID"
export IOCANE_REPO_ROOT="$REPO_ROOT"
export IOCANE_MODEL_NAME="$MODEL"
unset VIRTUAL_ENV
cd "$REPO_ROOT"

LOG_FILE="$REPO_ROOT/plans/ct-author-${CP_ID}.log"

# Prompt pattern mirrors spawn-tester.sh. Slash-command resolution
# inside -p is not hook-guaranteed; the io-ct-author.md workflow is
# invoked by reference instead.
PROMPT="Read and execute the workflow defined in .claude/commands/io-ct-author.md. Your target CP is ${CP_ID}. Write every connectivity test whose target_cp == ${CP_ID} under tests/connectivity/, per the file paths listed in task.connectivity_tests. Do NOT run any gate -- target impl does not exist yet. Do NOT create skeleton impl in src/. Terminate on completion."

echo "spawn-ct-writer: cp=${CP_ID} cts=${CT_COUNT} model=$MODEL" >&2

echo "$PROMPT" | claude -p \
    --model "$MODEL" \
    --max-turns 30 \
    --allowedTools "Bash,Read,Write,Edit,Glob,Grep" \
    --output-format json \
    >> "$LOG_FILE" 2>&1

echo "spawn-ct-writer: cp=${CP_ID} complete." >&2

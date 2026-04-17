#!/usr/bin/env bash
# .claude/scripts/spawn-tester.sh
#
# Dispatches a Tier-1 Test Author session for one Protocol.
# Role contract: exports IOCANE_ROLE=tester + IOCANE_PROTOCOL=<stem> so
# session-start.sh can inject role-scoped orientation into the new
# claude -p process.
#
# Usage:
#   bash .claude/scripts/spawn-tester.sh --protocol <stem>
#
# --protocol must be the bare Protocol stem (e.g., "idataflow"), NOT a
# path. Path-shaped input is rejected -- the stem convention is the
# contract that keeps the amend-attempts sidecar filename flat (no
# nested dirs from a .pyi path).
#
# Outcome is success when EITHER the tester writes tests/contracts/
# test_<stem>.py OR emits .iocane/amend-signals/<stem>.yaml. Both are
# legitimate terminal states of the Test Author workflow.
#
# Reads model from iocane.config.yaml (models.tier1). Falls back to
# claude-opus-4-6 if the key is absent.

set -euo pipefail

# --- Arg parsing ---
PROTOCOL=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --protocol) PROTOCOL="$2"; shift 2 ;;
        *) echo "spawn-tester: unknown arg: $1" >&2; exit 1 ;;
    esac
done

if [ -z "$PROTOCOL" ]; then
    echo "spawn-tester: --protocol <stem> required" >&2
    exit 1
fi

# Reject anything that is not an identifier-shaped stem. Blocks path
# traversal (..), Windows reserved names (CON/PRN/NUL/AUX), whitespace,
# newlines, shell metacharacters ($, `, ", \), unicode, and extension
# suffixes -- all of which could corrupt filesystem paths, shell
# heredocs, or the role-block prompt injected by session-start.sh.
if [[ ! "$PROTOCOL" =~ ^[A-Za-z_][A-Za-z0-9_-]*$ ]]; then
    echo "spawn-tester: --protocol must match ^[A-Za-z_][A-Za-z0-9_-]*\$ (identifier-shaped stem), got '$PROTOCOL'" >&2
    exit 1
fi

# --- Resolve consumer repo root ---
REPO_ROOT="${REPO_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null)}"
if [ -z "$REPO_ROOT" ]; then
    echo "spawn-tester: not in a git repo" >&2
    exit 1
fi

# --- Preflight gates ---

# Architect-mode sentinel would block tester .py writes via
# architect-boundary.sh. Fail fast rather than let the tester
# run into a gate.
if [ -f "$REPO_ROOT/.iocane/architect-mode" ]; then
    echo "spawn-tester: .iocane/architect-mode sentinel is set -- resolve before dispatch" >&2
    exit 1
fi

# Target Protocol must exist.
if [ ! -f "$REPO_ROOT/interfaces/${PROTOCOL}.pyi" ]; then
    echo "spawn-tester: interfaces/${PROTOCOL}.pyi not found" >&2
    exit 1
fi

# Architect-owned inputs. Only test-plan.yaml carries a `validated`
# stamp (architect owns it via Step H-post-validate); symbols.yaml has
# no stamp (its validation is coupled to test-plan via the reset-hook
# chain -- any symbols.yaml write resets test-plan.yaml.validated).
# symbols.yaml: existence check only.
# test-plan.yaml: anchored grep on the top-level key. A substring match
# would false-green on any invariant description containing the literal
# "validated: true" (e.g., pass-criteria prose quoting prior state).
if [ ! -f "$REPO_ROOT/plans/test-plan.yaml" ]; then
    echo "spawn-tester: plans/test-plan.yaml not found" >&2
    exit 1
fi
if [ ! -f "$REPO_ROOT/plans/symbols.yaml" ]; then
    echo "spawn-tester: plans/symbols.yaml not found" >&2
    exit 1
fi
if ! grep -qE '^validated:[[:space:]]*true[[:space:]]*$' "$REPO_ROOT/plans/test-plan.yaml"; then
    echo "spawn-tester: plans/test-plan.yaml not stamped validated: true (run /io-architect Step H-post-validate)" >&2
    exit 1
fi

# --- Config read (with in-code fallback) ---
CONFIG_FILE="$REPO_ROOT/.claude/iocane.config.yaml"

_cfg_read() {
    local section="$1"
    local subkey="$2"
    awk "/^${section}:/{f=1;next} f&&/^[^ ]/{exit} f&&/^  ${subkey}:/{print;exit}" "$CONFIG_FILE" 2>/dev/null \
        | sed 's/^[^:]*:[[:space:]]*//;s/[[:space:]]*#.*//;s/"//g' \
        | tr -d '\r' \
        | head -1
}

_cfg_model=$(_cfg_read models tier1)
MODEL="${IOCANE_MODEL:-${_cfg_model:-claude-opus-4-6}}"

if [ -z "$_cfg_model" ]; then
    echo "spawn-tester: WARN: models.tier1 not found in $CONFIG_FILE; falling back to $MODEL" >&2
fi

# --- Export role contract + ensure consumer cwd ---
export IOCANE_ROLE=tester
export IOCANE_PROTOCOL="$PROTOCOL"
export IOCANE_REPO_ROOT="$REPO_ROOT"
export IOCANE_MODEL_NAME="$MODEL"
unset VIRTUAL_ENV
cd "$REPO_ROOT"

LOG_FILE="$REPO_ROOT/plans/tester-${PROTOCOL}.log"

# Prompt format mirrors dispatch-agents.sh (explicit instruction, not
# raw slash command). Slash-command resolution inside -p is not
# hook-guaranteed; the io-test-author.md workflow is invoked by
# reference instead.
PROMPT="Read and execute the workflow defined in .claude/commands/io-test-author.md. Your target Protocol is ${PROTOCOL} (at interfaces/${PROTOCOL}.pyi). Follow every step in order. If the Protocol is under-specified for any declared invariant, emit .iocane/amend-signals/${PROTOCOL}.yaml per the AmendSignalFile schema and terminate without writing a test file. Otherwise write tests/contracts/test_${PROTOCOL}.py and terminate."

echo "spawn-tester: protocol=${PROTOCOL} model=$MODEL" >&2

echo "$PROMPT" | claude -p \
    --model "$MODEL" \
    --max-turns 30 \
    --allowedTools "Bash,Read,Write,Edit,Glob,Grep" \
    --output-format json \
    >> "$LOG_FILE" 2>&1

echo "spawn-tester: protocol=${PROTOCOL} complete." >&2

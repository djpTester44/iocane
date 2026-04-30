#!/usr/bin/env bash
# scaffold-claude-md.sh
#
# Scaffolds CLAUDE.md from .claude/templates/CLAUDE.md.template with
# project-name + description substitutions. Unconditional overwrite --
# any pre-existing CLAUDE.md is replaced.
#
# Used by /io-adopt Step 1d (brownfield bootstrap). The brownfield
# pre_gen_project.py cookiecutter hook archives any prior CLAUDE.md to
# OLD_CLAUDE.md before /io-adopt runs; this script writes the new
# harness-localized template at that point. Operator manually merges
# OLD_CLAUDE.md content per io-adopt.md Step 1d Line 54 guidance.
#
# Greenfield uses scaffold-greenfield.sh, which has its own CLAUDE.md
# branch with skip-if-exists semantics (different contract by design).
#
# Usage:
#   bash .claude/scripts/scaffold-claude-md.sh \
#     --name PROJECT_NAME \
#     --description "Short description"
#
# Arguments:
#   --name             Project name (snake_case)
#   --description      One-line project description
#
# Output:
#   Writes (or overwrites) CLAUDE.md in the current working directory.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_TEMPLATE="$SCRIPT_DIR/../templates/CLAUDE.md.template"

PROJECT_NAME=""
PROJECT_DESCRIPTION=""

# --- Parse arguments ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --name)          PROJECT_NAME="$2";        shift 2 ;;
        --description)   PROJECT_DESCRIPTION="$2"; shift 2 ;;
        *) echo "ERROR: Unknown argument: $1" >&2; exit 1 ;;
    esac
done

# --- Validate ---
if [ -z "$PROJECT_NAME" ]; then
    echo "ERROR: --name is required" >&2
    exit 1
fi

if [ ! -f "$CLAUDE_TEMPLATE" ]; then
    echo "ERROR: CLAUDE.md template not found at $CLAUDE_TEMPLATE" >&2
    exit 1
fi

# --- Substitute and write CLAUDE.md (unconditional overwrite) ---
sed \
    -e "s|__PROJECT_NAME__|${PROJECT_NAME}|g" \
    -e "s|__PROJECT_DESCRIPTION__|${PROJECT_DESCRIPTION}|g" \
    "$CLAUDE_TEMPLATE" > CLAUDE.md

echo "CLAUDE.md written (unconditional overwrite -- prior content replaced if present)."

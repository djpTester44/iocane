#!/usr/bin/env bash
# scaffold-greenfield.sh
#
# Scaffolds pyproject.toml and CLAUDE.md from the harness templates directory.
# Called by /io-init (Step C / C1) after the layer map is resolved.
#
# Deployed location (consumer repo): .claude/scripts/scaffold-greenfield.sh
# Source location (iocane_build):    .claude/scripts/scaffold-greenfield.sh
# Templates resolved relative to the script via ../templates/.
#
# Usage:
#   bash .claude/scripts/scaffold-greenfield.sh \
#     --name PROJECT_NAME \
#     --description "Short description" \
#     --python 3.12 \
#     --root-packages "src,interfaces"
#
# Arguments:
#   --name             Project name (snake_case)
#   --description      One-line project description
#   --python           Python version, e.g. 3.12
#   --root-packages    Comma-separated importlinter root packages, e.g. "src,interfaces"
#
# Output:
#   Writes pyproject.toml and CLAUDE.md to the current working directory.
#   Exits non-zero if pyproject.toml already exists (will not overwrite).
#   Skips CLAUDE.md if it already exists.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE="$SCRIPT_DIR/../templates/pyproject.toml.template"

PROJECT_NAME=""
PROJECT_DESCRIPTION=""
PYTHON_VERSION="3.12"
ROOT_PACKAGES_RAW="src,interfaces"

# --- Parse arguments ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --name)          PROJECT_NAME="$2";        shift 2 ;;
        --description)   PROJECT_DESCRIPTION="$2"; shift 2 ;;
        --python)        PYTHON_VERSION="$2";      shift 2 ;;
        --root-packages) ROOT_PACKAGES_RAW="$2";   shift 2 ;;
        *) echo "ERROR: Unknown argument: $1" >&2; exit 1 ;;
    esac
done

# --- Validate ---
if [ -z "$PROJECT_NAME" ]; then
    echo "ERROR: --name is required" >&2
    exit 1
fi

if [ -f "pyproject.toml" ]; then
    echo "ERROR: pyproject.toml already exists. Remove it first if you want to re-scaffold." >&2
    exit 1
fi

if [ ! -f "$TEMPLATE" ]; then
    echo "ERROR: Template not found at $TEMPLATE" >&2
    exit 1
fi

# --- Derive substitution values ---
# Python version without dots for target-version (3.12 -> 312)
PYTHON_VERSION_NODOT="${PYTHON_VERSION//./}"

# Convert comma-separated root packages to quoted TOML array entries
# e.g. "src,interfaces" -> '"src", "interfaces"'
ROOT_PACKAGES_TOML=$(echo "$ROOT_PACKAGES_RAW" | tr ',' '\n' | sed 's/^[[:space:]]*//' | sed 's/[[:space:]]*$//' | sed 's/.*/"&"/' | tr '\n' ',' | sed 's/,$//' | sed 's/,/, /g')

# --- Substitute and write pyproject.toml ---
sed \
    -e "s|__PROJECT_NAME__|${PROJECT_NAME}|g" \
    -e "s|__PROJECT_DESCRIPTION__|${PROJECT_DESCRIPTION}|g" \
    -e "s|__PYTHON_VERSION_NODOT__|${PYTHON_VERSION_NODOT}|g" \
    -e "s|__PYTHON_VERSION__|${PYTHON_VERSION}|g" \
    -e "s|__ROOT_PACKAGES__|${ROOT_PACKAGES_TOML}|g" \
    "$TEMPLATE" > pyproject.toml

echo "pyproject.toml written."

# --- Scaffold CLAUDE.md ---
CLAUDE_TEMPLATE="$SCRIPT_DIR/../templates/CLAUDE.md.template"

if [ -f "CLAUDE.md" ]; then
    echo "CLAUDE.md already exists -- skipping."
else
    if [ ! -f "$CLAUDE_TEMPLATE" ]; then
        echo "WARNING: CLAUDE.md template not found at $CLAUDE_TEMPLATE -- skipping." >&2
    else
        sed \
            -e "s|__PROJECT_NAME__|${PROJECT_NAME}|g" \
            -e "s|__PROJECT_DESCRIPTION__|${PROJECT_DESCRIPTION}|g" \
            "$CLAUDE_TEMPLATE" > CLAUDE.md
        echo "CLAUDE.md written."
    fi
fi

# --- Scaffold plans/ directory structure (idempotent) ---
mkdir -p plans/tasks
echo "plans/ scaffolded (plans/tasks/ created; PRD.md preserved if present)."

# --- Merge .gitignore additions (idempotent, non-blocking) ---
GITIGNORE_TEMPLATE="$SCRIPT_DIR/../templates/gitignore-additions"
if [ -f "$GITIGNORE_TEMPLATE" ]; then
    if [ ! -f ".gitignore" ]; then
        cp "$GITIGNORE_TEMPLATE" .gitignore
        echo ".gitignore created from template."
    else
        # Append-missing only; preserve user ordering and comments.
        while IFS= read -r line; do
            grep -qxF -- "$line" .gitignore || printf "%s\n" "$line" >> .gitignore
        done < "$GITIGNORE_TEMPLATE" || echo "WARNING: .gitignore merge failed; skipping (non-blocking)." >&2
        echo ".gitignore merged with template additions."
    fi
fi

# --- Scaffold plans/roadmap.md stub (idempotent) ---
ROADMAP_STUB="$SCRIPT_DIR/../templates/roadmap.md.stub"
if [ -f "plans/roadmap.md" ]; then
    echo "plans/roadmap.md already exists -- skipping stub."
elif [ -f "$ROADMAP_STUB" ]; then
    cp "$ROADMAP_STUB" plans/roadmap.md
    echo "plans/roadmap.md stub written."
else
    echo "WARNING: roadmap.md.stub template not found at $ROADMAP_STUB -- skipping." >&2
fi

# --- Initialize plans/backlog.yaml stub (idempotent) ---
BACKLOG_STUB="$SCRIPT_DIR/../templates/backlog.yaml.stub"
if [ -f "plans/backlog.yaml" ]; then
    echo "plans/backlog.yaml already exists -- skipping init."
elif [ -f "$BACKLOG_STUB" ]; then
    cp "$BACKLOG_STUB" plans/backlog.yaml
    echo "plans/backlog.yaml initialized."
else
    echo "WARNING: backlog.yaml.stub template not found at $BACKLOG_STUB -- skipping." >&2
fi

# --- Seed catalog.toml from template (idempotent; greenfield only) ---
CATALOG_TEMPLATE="$SCRIPT_DIR/../templates/catalog.toml"
if [ -f "catalog.toml" ]; then
    echo "catalog.toml already exists -- skipping seed."
elif [ -f "$CATALOG_TEMPLATE" ]; then
    cp "$CATALOG_TEMPLATE" catalog.toml
    echo "catalog.toml seeded from template (DRAFT -- operator review required before /io-clarify)."
else
    echo "WARNING: catalog.toml template not found at $CATALOG_TEMPLATE -- skipping." >&2
fi

echo "Next: run /io-specify to generate the dependency-ordered feature roadmap from the clarified PRD."

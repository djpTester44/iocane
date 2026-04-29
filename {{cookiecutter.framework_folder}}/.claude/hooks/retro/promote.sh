#!/usr/bin/env bash
# /lessons-retro promote.sh -- finalization + deferred-registry actions.
#
# The /lessons-retro-review slash command performs the actual rule-file
# writes via the Edit/Write tools (which fire secret-scan.sh / emoji-scan.sh
# PreToolUse hooks as a safety net). This script handles only deterministic
# state mutations:
#
#   finalize <proposal_path>
#     - Archive proposal to .lessons/retro-review/archive/.
#     - Delete .lessons/.pending-review flag.
#     - Remove the matching Pass 1 tmp JSONL (same timestamp prefix).
#
#   defer <archived_proposal_path> <id> <name>
#     - Append an entry to .lessons/deferred.yaml (creating the file with
#       header if missing). Pure shell append, no YAML parsing.
#     - <name> may contain spaces; quote when invoking.
#
# Exit codes: 0 on success, 2 on bad usage, 1 on operational error.

set -u

ACTION="${1:-}"

case "$ACTION" in
    finalize)
        PROPOSAL="${2:-}"
        if [ -z "$PROPOSAL" ] || [ ! -f "$PROPOSAL" ]; then
            echo "error: proposal not found or not readable: $PROPOSAL" >&2
            exit 2
        fi

        mkdir -p .lessons/retro-review/archive

        mv "$PROPOSAL" .lessons/retro-review/archive/ \
            || { echo "error: failed to archive proposal" >&2; exit 1; }

        rm -f .lessons/.pending-review

        # Pass 1 JSONL has the same timestamp prefix as the proposal:
        #   proposal: 20260427-0549-proposal.md
        #   pass1:    sesh-knowledge_20260427-0549.jsonl
        PROPOSAL_BASENAME="$(basename "$PROPOSAL")"
        STAMP="${PROPOSAL_BASENAME%-proposal.md}"
        PASS1_TMP=".lessons/tmp/sesh-knowledge_${STAMP}.jsonl"

        if [ -f "$PASS1_TMP" ]; then
            rm -f "$PASS1_TMP"
        fi

        ARCHIVED="$(basename "$PROPOSAL")"
        echo "finalized: archived=$ARCHIVED, pending-review cleared, pass1 tmp removed"
        exit 0
        ;;

    defer)
        ARCHIVED_PATH="${2:-}"
        ID="${3:-}"
        NAME="${4:-}"

        if [ -z "$ARCHIVED_PATH" ] || [ -z "$ID" ] || [ -z "$NAME" ]; then
            echo "usage: $0 defer <archived_proposal_path> <id> <name>" >&2
            exit 2
        fi

        REGISTRY=".lessons/deferred.yaml"

        if [ ! -f "$REGISTRY" ]; then
            cat > "$REGISTRY" <<'HEADER'
# .lessons/deferred.yaml -- registry of DEFERRED lesson items from archived proposals.
# Each entry: id, name (one-line summary), path to archived proposal, defer date.
# Pruning is user-driven (edit this file to remove acted-upon entries).
# `name` is a hint; if the archived proposal is hand-edited later, this field can drift.

deferred:
HEADER
        fi

        TODAY="$(date -u +%Y-%m-%d)"

        # Sanitize name for YAML: escape double quotes, drop newlines, trim.
        SAFE_NAME="$(printf '%s' "$NAME" | tr '\n' ' ' | sed 's/"/\\"/g')"

        {
            printf '  - id: %s\n' "$ID"
            printf '    name: "%s"\n' "$SAFE_NAME"
            printf '    proposal: %s\n' "$ARCHIVED_PATH"
            printf '    deferred_at: %s\n' "$TODAY"
        } >> "$REGISTRY"

        echo "deferred: id=$ID registered in $REGISTRY"
        exit 0
        ;;

    *)
        echo "usage: $0 finalize <proposal_path>" >&2
        echo "       $0 defer <archived_proposal_path> <id> <name>" >&2
        exit 2
        ;;
esac

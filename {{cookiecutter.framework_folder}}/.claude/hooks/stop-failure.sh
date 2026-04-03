#!/usr/bin/env bash
# StopFailure hook: log API-error-terminated turns for dispatch observability.
#
# Input fields:
#   error                  -- error type (rate_limit, billing_error, authentication_failed,
#                             invalid_request, server_error, max_output_tokens, unknown)
#   error_details          -- additional details (optional)
#   last_assistant_message -- rendered error text shown in conversation (optional)
#
# Output: none. Exit code and output are ignored by Claude Code.
# This hook exists purely for logging.
#
# Source: hooks.md:1533-1559 (Claude Code docs -- StopFailure input schema)

set -euo pipefail

INPUT=$(cat)
mkdir -p .iocane

PARSED=$(printf '%s' "$INPUT" | uv run python -c "
import sys, json
raw = sys.stdin.read()
d = json.loads(raw) if raw.strip() else {}
error = d.get('error', 'unknown')
details = d.get('error_details', '')
msg = d.get('last_assistant_message', '')[:200]
print(error)
print(details)
print(msg)
" 2>/dev/null || printf 'unknown\n\n\n')

ERROR_TYPE=$(echo "$PARSED" | sed -n '1p')
ERROR_DETAILS=$(echo "$PARSED" | sed -n '2p')
ERROR_MSG=$(echo "$PARSED" | sed -n '3p')

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

printf '%s error=%s details="%s" msg="%s"\n' \
    "$TIMESTAMP" "$ERROR_TYPE" "$ERROR_DETAILS" "$ERROR_MSG" \
    >> .iocane/stop-failure.log

exit 0

#!/usr/bin/env bash
# PreToolUse hook: Edit | Write
# Scans file content being written for common hardcoded secret patterns.
# Blocks with exit 2 if a match is found.

INPUT=$(cat)

CONTENT=$(echo "$INPUT" | uv run python -c "
import sys, json
try:
    d = json.load(sys.stdin)
    ti = d.get('tool_input', {})
    # Edit tool: new_string; Write tool: content
    print(ti.get('new_string', '') or ti.get('content', ''))
except Exception:
    print('')
")

if [ -z "$CONTENT" ]; then
    exit 0
fi

# Check for AWS access key pattern
if echo "$CONTENT" | grep -qE 'AKIA[0-9A-Z]{16}'; then
    echo "BLOCKED: Hardcoded AWS access key detected (AKIA...). Inject secrets via environment variables." >&2
    exit 2
fi

# Check for generic secret assignments
if echo "$CONTENT" | grep -qiE '(secret|token|api_key|password|credential)\s*=\s*["'"'"'][^"'"'"']{8,}["'"'"']'; then
    echo "BLOCKED: Hardcoded secret assignment detected. Inject secrets via environment variables at the entrypoint layer (config.py)." >&2
    exit 2
fi

# Check for Bearer tokens
if echo "$CONTENT" | grep -qE 'Bearer\s+[A-Za-z0-9\-._~+/]+=*'; then
    echo "BLOCKED: Hardcoded Bearer token detected. Inject secrets via environment variables." >&2
    exit 2
fi

exit 0

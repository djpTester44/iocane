#!/usr/bin/env bash
# PreToolUse hook: Bash
# Gates rm commands against .iocane/rm-allowlist.txt.
# Deny list still catches rm -rf and rmdir; this hook catches plain rm / rm -f.
#
# NOTE: Designed to run from a generated project root.
# The allowlist lives at .iocane/rm-allowlist.txt in the target repo.

ALLOWLIST=".iocane/rm-allowlist.txt"

INPUT="${CLAUDE_TOOL_INPUT:-$(cat)}"
[ -z "$INPUT" ] && exit 0

COMMAND=$(echo "$INPUT" | uv run python -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('tool_input', {}).get('command', ''))
except Exception:
    print('')
" 2>/dev/null)

# Only gate commands where rm is an executed shell command.
# 1. Strip quoted strings so "rm -f foo" inside python -c doesn't trigger.
# 2. Split on shell metacharacters so compound commands are checked per-segment.
# 3. Match rm as the leading command (with optional wrapper prefixes).
# 4. Separately catch find -exec rm.
_STRIPPED=$(echo "$COMMAND" | sed "s/'[^']*'//g; s/\"[^\"]*\"//g")
{
  echo "$_STRIPPED" | tr ';&|' '\n' |
    grep -qE '^\s*(sudo\s+|env\s+|command\s+|nohup\s+|nice\s+|time\s+|doas\s+|xargs\s+)*rm\s' ||
  echo "$_STRIPPED" | grep -qE '[-]exec\s+rm(\s|$)'
} || exit 0

# Block if no allowlist exists
if [ ! -f "$ALLOWLIST" ]; then
    echo "BLOCKED: rm not on allowlist ($ALLOWLIST not found)" >&2
    exit 2
fi

# Match against allowlist patterns
while IFS= read -r pattern || [ -n "$pattern" ]; do
    [[ -z "$pattern" || "$pattern" == \#* ]] && continue
    # shellcheck disable=SC2053
    if [[ $COMMAND == $pattern ]]; then
        exit 0
    fi
done < "$ALLOWLIST"

echo "BLOCKED: rm not on allowlist. Add a pattern to $ALLOWLIST to allow." >&2
exit 2

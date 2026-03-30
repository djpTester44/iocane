#!/usr/bin/env bash
# PreToolUse hook: Edit | Write
# Blocks writes that contain Unicode emoji characters.
# Emoji in output violates the engineering constitution.

INPUT=$(cat)

RESULT=$(echo "$INPUT" | uv run python -c "
import sys, re, json

try:
    d = json.load(sys.stdin)
    ti = d.get('tool_input', {})
    content = ti.get('new_string', '') or ti.get('content', '')
except Exception:
    content = ''

if not content:
    print('ok')
    sys.exit(0)

pattern = re.compile(
    u'[\U0001F600-\U0001F64F'
    u'\U0001F300-\U0001F5FF'
    u'\U0001F680-\U0001F6FF'
    u'\U0001F900-\U0001F9FF'
    u'\U0001FA00-\U0001FAFF'
    u'\U00002300-\U000023FF'
    u'\U00002600-\U000026FF'
    u'\U00002700-\U000027BF'
    u'\U00002B50-\U00002B55'
    u'\U0000FE00-\U0000FE0F'
    u'\u200d]'
)
print('emoji' if pattern.search(content) else 'ok')
")

if [ "$RESULT" = "emoji" ]; then
    echo "BLOCKED: Emoji character detected in content. Emoji are forbidden per the engineering constitution." >&2
    exit 2
fi

exit 0

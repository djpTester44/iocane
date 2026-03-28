#!/usr/bin/env bash
# PreToolUse hook: Bash
# Enforces rtk prefix for standalone CLI tools and Python tools via uv run.
#
# Catches bare tool invocations and blocks with corrective guidance.
# Does NOT enforce on bash script.sh invocations, uv add/run itself,
# or commands inside hook scripts (hooks run as bash).

INPUT=$(cat)

COMMAND=$(echo "$INPUT" | uv run python -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('tool_input', {}).get('command', ''))
except Exception:
    print('')
")

# --- Structural parser: parses command tokens to avoid false positives ---
# Strips quoted strings, command substitutions, then checks leading token per
# shell-operator-separated segment. Exempt: bash, uv (unless uv run <blocked>).
RESULT=$(RTK_CMD="$COMMAND" uv run python - << 'PYEOF'
import sys, re, os

cmd = os.environ.get('RTK_CMD', '')

# Strip quoted substrings (removes echo "run git status" style false positives)
cmd_s = re.sub(r'"(?:[^"\\]|\\.)*"', '', cmd)
cmd_s = re.sub(r"'[^']*'", '', cmd_s)

# Strip command substitutions
cmd_s = re.sub(r'\$\([^)]*\)', '', cmd_s)
cmd_s = re.sub(r'`[^`]*`', '', cmd_s)

# Split on shell operators
segments = re.split(r'\|\||&&|[|;]', cmd_s)

CLI_BLOCKED = {'git', 'ls', 'grep', 'rg', 'gh', 'find'}
UV_BLOCKED  = {'pytest', 'ruff', 'mypy'}

GUIDANCE = {
    'git':    "Use 'rtk git' instead of bare 'git'. Example: rtk git status",
    'ls':     "Use 'rtk ls' instead of bare 'ls'. Example: rtk ls .",
    'grep':   "Use 'rtk grep' instead of bare 'grep'/'rg'. Example: rtk grep -rn 'pattern' .",
    'rg':     "Use 'rtk grep' instead of bare 'rg'. Example: rtk grep -rn 'pattern' .",
    'gh':     "Use 'rtk gh' instead of bare 'gh'. Example: rtk gh pr list",
    'find':   "Use 'rtk find' instead of bare 'find'. Example: rtk find . -name '*.py'",
    'pytest': "Use 'uv run rtk pytest' instead of 'uv run pytest'.",
    'ruff':   "Use 'uv run rtk ruff' instead of 'uv run ruff'.",
    'mypy':   "Use 'uv run rtk mypy' instead of 'uv run mypy'.",
}

for segment in segments:
    tokens = segment.split()
    if not tokens:
        continue

    # Skip leading VAR=value assignments
    i = 0
    while i < len(tokens) and re.match(r'^[A-Za-z_][A-Za-z0-9_]*=', tokens[i]):
        i += 1

    if i >= len(tokens):
        continue

    lead = tokens[i]

    # rtk prefix: always allowed
    if lead == 'rtk':
        continue

    # uv: only blocked if 'uv run <blocked_tool>' without rtk
    if lead == 'uv':
        if i + 1 < len(tokens) and tokens[i + 1] == 'run':
            if i + 2 < len(tokens):
                next_tok = tokens[i + 2]
                if next_tok == 'rtk':
                    continue
                if next_tok in UV_BLOCKED:
                    print('BLOCKED:' + GUIDANCE[next_tok])
                    sys.exit(0)
        continue

    # CLI tools
    if lead in CLI_BLOCKED:
        print('BLOCKED:' + GUIDANCE[lead])
        sys.exit(0)

print('ALLOW')
PYEOF
)

case "$RESULT" in
    BLOCKED:*)
        echo "${RESULT#BLOCKED:}"
        exit 2
        ;;
esac

exit 0

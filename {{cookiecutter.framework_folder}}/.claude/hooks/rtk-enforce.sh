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
RTK_CMD="$COMMAND" uv run python - << 'PYEOF'
import sys, re, os

cmd = os.environ.get('RTK_CMD', '')

# Strip quoted substrings (removes echo "run git status" style false positives)
cmd_s = re.sub(r'"(?:[^"\\]|\\.)*"', '', cmd)
cmd_s = re.sub(r"'[^']*'", '', cmd_s)

# Strip command substitutions
cmd_s = re.sub(r'\$\([^)]*\)', '', cmd_s)
cmd_s = re.sub(r'`[^`]*`', '', cmd_s)

# Split on shell operators with capturing groups to preserve delimiters
DELIM_PATTERN = r'(\|\||&&|[|;])'
segments_s = re.split(DELIM_PATTERN, cmd_s)
segments_orig = re.split(DELIM_PATTERN, cmd)

CLI_BLOCKED = {'git', 'ls', 'grep', 'rg', 'gh', 'find', 'pytest', 'ruff', 'mypy'}
UV_BLOCKED  = {'pytest', 'ruff', 'mypy'}

FIX = {
    'git':    'rtk git',
    'ls':     'rtk ls',
    'grep':   'rtk grep',
    'rg':     'rtk grep',
    'gh':     'rtk gh',
    'find':   'rtk find',
    'pytest': 'uv run rtk test pytest',
    'ruff':   'uv run rtk ruff',
    'mypy':   'uv run rtk mypy',
}

violations = []  # list of (segment_index, tool_name, kind) where kind='bare'|'uv_run'

# Only check non-delimiter segments (even indices in split result)
for idx in range(0, len(segments_s), 2):
    segment = segments_s[idx]
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
                    violations.append((idx, next_tok, 'uv_run'))
        continue

    # CLI tools (including bare pytest/ruff/mypy)
    if lead in CLI_BLOCKED:
        violations.append((idx, lead, 'bare'))

if not violations:
    sys.exit(0)

# Reconstruct corrected command by patching violated original segments
patched = list(segments_orig)
for seg_idx, tool, kind in violations:
    orig_seg = patched[seg_idx]
    if kind == 'uv_run':
        patched[seg_idx] = re.sub(
            r'\buv\s+run\s+' + re.escape(tool),
            'uv run rtk ' + tool,
            orig_seg, count=1
        )
    else:
        patched[seg_idx] = re.sub(
            r'\b' + re.escape(tool) + r'\b',
            FIX[tool],
            orig_seg, count=1
        )

corrected = ''.join(patched)

print("Violations:", file=sys.stderr)
for seg_idx, tool, kind in violations:
    seg_num = seg_idx // 2 + 1
    if kind == 'uv_run':
        print(f"  segment {seg_num}: bare `uv run {tool}` -> uv run rtk {tool}", file=sys.stderr)
    else:
        print(f"  segment {seg_num}: bare `{tool}` -> {FIX[tool]}", file=sys.stderr)

print("", file=sys.stderr)
print("Corrected command:", file=sys.stderr)
print(f"  {corrected}", file=sys.stderr)

sys.exit(2)
PYEOF
exit $?

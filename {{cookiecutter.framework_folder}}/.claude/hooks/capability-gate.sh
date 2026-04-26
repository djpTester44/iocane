#!/usr/bin/env bash
# PreToolUse hook: Bash + Edit|Write
# Capability-gate: hardcoded catastrophic-rm deny list for Bash invocations.
#
# Fail-open baseline: any command that doesn't match a catastrophic
# pattern passes through. Matches today's behavior for non-rm commands
# and removes the old rm-gate's default-deny-on-rm friction. The hook
# exists so harness-owned catastrophic protection survives rm-gate.sh
# retirement (Phase 3) without depending on a user-maintained allowlist.
#
# Capability cache consultation (per-workflow authorization of writes
# that would otherwise trigger reset hooks) lives in reset-on-*.sh --
# it is not needed here. This hook is deliberately narrow: unsafe
# removal patterns only.
#
# Edit/Write: always pass through in Phase 1. If Phase 2+ wants to
# tighten, add consultation of $REPO_ROOT/.iocane/sessions/<sid>.active.txt
# here (tool=Edit|Write, op=write, pattern= file_path).
#
# NOTE: Designed to run from a generated project root.
# This script is a harness template artifact.

set -u

INPUT="${CLAUDE_TOOL_INPUT:-$(cat)}"
[ -z "$INPUT" ] && exit 0

# Single python call to extract tool name + command (interpreter startup
# is the unavoidable JSON parse cost; grant/revoke happen out-of-band).
EXTRACT=$(printf '%s' "$INPUT" | uv run python -c "
import sys, json
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
tool = d.get('tool_name', '') or ''
ti = d.get('tool_input') or {}
cmd = (ti.get('command') or '').replace('\\n', ' ')
print(tool)
print(cmd)
" 2>/dev/null)

TOOL=$(printf '%s' "$EXTRACT" | sed -n '1p')
CMD=$(printf '%s' "$EXTRACT" | sed -n '2p')

# Edit/Write: pass-through in Phase 1.
case "$TOOL" in
    Edit|Write)
        exit 0
        ;;
esac

# Bash tool without a command payload: nothing to check.
[ -z "$CMD" ] && exit 0

# Strip quoted strings so 'rm -rf /' inside python -c or shell comments
# does not trigger a false positive.
_STRIPPED=$(echo "$CMD" | sed "s/'[^']*'//g; s/\"[^\"]*\"//g")
_SEGMENTS=$(echo "$_STRIPPED" | tr ';&|' '\n')

# Catastrophic removal patterns -- deny unconditionally, never safe.
# Minimal list by design: a false-positive block costs more than missing
# a near-catastrophic variant. Expand only with evidence.
#
# Matches (all after optional leading whitespace):
#   rm -rf *            recursive wildcard
#   rm -rf /            root filesystem
#   rm -rf /*           root wildcard
#   rm -rf .            cwd
#   rm -rf ..           parent dir
#   rm -rf ~            home dir
#   rmdir * / -p *      rmdir against wildcard/root
CATASTROPHIC='(^|[[:space:]])rm[[:space:]]+(-[rRfF]+[[:space:]]+)+(\*|/|/\*|\.|\.\.|~)([[:space:]]|$)'
RMDIR_DANGER='(^|[[:space:]])rmdir[[:space:]]+(-p[[:space:]]+)?(\*|/)([[:space:]]|$)'

if echo "$_SEGMENTS" | grep -qE "$CATASTROPHIC"; then
    echo "BLOCKED by capability-gate: catastrophic rm pattern (recursive removal of wildcard/root/cwd/parent/home)." >&2
    echo "  Command: $CMD" >&2
    echo "  This deny is hardcoded -- override via explicit scoped rm against specific paths." >&2
    exit 2
fi

if echo "$_SEGMENTS" | grep -qE "$RMDIR_DANGER"; then
    echo "BLOCKED by capability-gate: catastrophic rmdir pattern (wildcard/root)." >&2
    echo "  Command: $CMD" >&2
    exit 2
fi

exit 0

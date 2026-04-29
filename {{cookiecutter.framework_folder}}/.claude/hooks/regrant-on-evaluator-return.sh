#!/usr/bin/env bash
# PostToolUse hook: Bash
# Re-issues io-architect.H capability when the architect returns from
# spawn-artifact-evaluator.sh on the cdt/ct rubric paths, where A5/A6
# wire-test critics retain a bounded-retry pattern at the impl tier
# (per Plan B Phase 5 wire-tests, carried over to v5 Phase 4).
# Step I correction-driven re-entry is not a tool-event boundary and
# still requires explicit Step F-pre invocation by the agent.
#
# Rubric guard: --rubric design runs single-pass per architect attempt
# (R2-narrow + D-04 clause-5 option a); no auto-loop, no per-cycle
# re-grant. Re-attempts are operator-initiated at Step I.
#
# Subagent guard: only fires in the parent (non-subagent) session. The
# design-evaluator subprocess fires Bash tool calls (findings_emitter
# invocations) under IOCANE_SUBAGENT=1; those must not re-grant the
# parent's capability.
#
# Fail-open: parse failures or capability.py errors are no-ops. The
# agent's explicit Step F-pre prose is the documented fallback.
#
# NOTE: Designed to run from a generated project root.
# This script is a harness template artifact.

set -u

if [ "${IOCANE_SUBAGENT:-0}" = "1" ]; then
    exit 0
fi

INPUT="${CLAUDE_TOOL_INPUT:-$(cat)}"
[ -z "$INPUT" ] && exit 0

CMD=$(printf '%s' "$INPUT" | uv run python -c "
import sys, json
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
ti = d.get('tool_input') or {}
print((ti.get('command') or '').replace('\n', ' '))
" 2>/dev/null)

case "$CMD" in
    *spawn-artifact-evaluator.sh*) ;;
    *) exit 0 ;;
esac

# Rubric guard: design path runs single-pass per architect attempt
# (R2-narrow + D-04 clause-5 option a). No re-grant on return.
case "$CMD" in
    *--rubric\ design*|*--rubric=design*)
        exit 0
        ;;
esac

REPO_ROOT="${IOCANE_REPO_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || true)}"
[ -z "$REPO_ROOT" ] && exit 0

uv run python "$REPO_ROOT/.claude/scripts/capability.py" grant \
    --template io-architect.H \
    --repo-root "$REPO_ROOT" \
    >/dev/null 2>&1 || true

exit 0

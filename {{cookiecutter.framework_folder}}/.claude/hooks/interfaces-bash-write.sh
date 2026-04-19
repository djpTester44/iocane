#!/usr/bin/env bash
# PreToolUse hook: Bash
# Blocks Bash commands that write into interfaces/ (shell redirection,
# tee, cp/mv/install/touch, sed -i, python -c "open(...)", dd of=...)
# unless IOCANE_ROLE=gen_protocols. Under role, non-.pyi writes are
# still rejected (extension parity with the Edit|Write matcher).
# Logic lives in .claude/scripts/interfaces_zone_check.py. Exit codes:
# 0 = allow, 2 = block.
#
# TRUST MODEL: Honest-agent drift prevention. Pattern set is a blocklist,
# non-exhaustive by design -- an adversarial agent who reads this file
# can use an unlisted primitive (``ln -s``, ``python -c "pathlib..."``,
# etc.) to bypass. IOCANE_ROLE is caller-controlled; cryptographic
# admission is out-of-scope for v3. See
# harness/docs/enforcement-mapping.md.

exec uv run python .claude/scripts/interfaces_zone_check.py bash-write "${IOCANE_ROLE:-}"

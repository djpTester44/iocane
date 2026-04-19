#!/usr/bin/env bash
# PreToolUse hook: Edit | Write
# Blocks writes under interfaces/ unless IOCANE_ROLE=gen_protocols.
# Logic lives in .claude/scripts/interfaces_zone_check.py; this wrapper
# forwards stdin and passes the env-derived role via argv so the Python
# side never touches os.environ. Exit codes: 0 = allow, 2 = block.
#
# TRUST MODEL: Honest-agent drift prevention. IOCANE_ROLE is a
# caller-controlled string; an attacker who reads this script can
# inline-set the role to bypass. Accepted under v3's threat model;
# cryptographic admission is out-of-scope. See
# harness/docs/enforcement-mapping.md.

exec uv run python .claude/scripts/interfaces_zone_check.py codegen-only "${IOCANE_ROLE:-}"

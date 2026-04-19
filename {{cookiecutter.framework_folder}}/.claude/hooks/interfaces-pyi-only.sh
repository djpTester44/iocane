#!/usr/bin/env bash
# PreToolUse hook: Edit | Write
# Blocks any write to a path under interfaces/ whose basename does not
# end in .pyi (interfaces/ is the codegen output zone; .py files there
# are a runtime-injection drift). Logic lives in
# .claude/scripts/interfaces_zone_check.py; this wrapper just forwards
# stdin and exit code. Exit codes: 0 = allow, 2 = block.
#
# TRUST MODEL: Honest-agent drift prevention. IOCANE_ROLE is a
# caller-controlled string; an attacker who reads this script can
# inline-set the role to bypass admission on the codegen-only hook.
# Accepted under v3's threat model; cryptographic admission is
# out-of-scope. See harness/docs/enforcement-mapping.md.

exec uv run python .claude/scripts/interfaces_zone_check.py pyi-only

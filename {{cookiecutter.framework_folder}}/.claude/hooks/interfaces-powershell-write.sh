#!/usr/bin/env bash
# PreToolUse hook: PowerShell
# Windows parity for the Bash-write class. Blocks PowerShell commands
# (Set-Content, Out-File, Add-Content, New-Item, Copy/Move-Item,
# Tee-Object, `>` / `>>` redirect) that write into interfaces/ unless
# IOCANE_ROLE=gen_protocols. Under role, non-.pyi writes are still
# rejected (extension parity with Edit|Write matcher). Logic lives in
# .claude/scripts/interfaces_zone_check.py. Exit codes: 0 allow, 2 block.
#
# TRUST MODEL: Honest-agent drift prevention. Pattern set is a blocklist,
# non-exhaustive by design. IOCANE_ROLE is caller-controlled; cryptographic
# admission is out-of-scope for v3. See harness/docs/enforcement-mapping.md.

exec uv run python .claude/scripts/interfaces_zone_check.py powershell-write "${IOCANE_ROLE:-}"

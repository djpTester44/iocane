# CLAUDE_CODE_SUBPROCESS_ENV_SCRUB: Credential Isolation for Subprocesses

> Without this flag, every Bash tool call and hook invocation inherits the full parent environment -- including `ANTHROPIC_API_KEY` and cloud-provider credentials.

## Cost Model

`secret-scan.sh` is a write-time gate: it catches hardcoded credential strings being written to files. It does not protect runtime environment variables from being read inside a subprocess.

A prompt-injection attack embedded in a bash command (e.g., via a file whose contents are passed to a shell tool) can read `$ANTHROPIC_API_KEY` via shell expansion and exfiltrate it through a network call or file write. The key was never written to disk; `secret-scan.sh` never saw it. The leak is silent and irreversible.

`CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1` strips Anthropic and cloud-provider credentials from the subprocess environment before the Bash tool, hooks, and MCP stdio servers execute. The current session still holds the key; subprocesses do not inherit it.

## Reference

- Env var: `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB`
- Value: `1` to enable scrubbing
- Scope: affects Bash tool calls, hook invocations, MCP stdio servers
- Note: `claude-code-action` sets this automatically when `allowed_non_write_users` is configured

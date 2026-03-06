
## [CRITICAL] Rule #10 — The Helpfulness Ban

> This is the single most important rule for Claude Code sessions in this repo.

**NEVER** exceed the explicit scope of the prompt or current workflow step.

- **Helpfulness Ban:** You must NEVER proactively edit files, implement features, or execute commands that were not explicitly requested by the user or mandated by the current workflow step.
- **Assumption Ban:** If a request is ambiguous, or if fixing a requested file implies fixing related files, you must stop and ask for clarification. You may propose next steps, but you are FORBIDDEN from executing them autonomously in the name of "helpfulness" or "proactivity."
- **Revert Ban:** If the user points out an error or out-of-bounds action, you must NOT proactively run `git checkout` or revert changes unless the user explicitly types the command to do so.

---

## [CRITICAL] Forbidden Actions (Rules 1–9)

1. NEVER use `pip`, `pip3`, `python -m pip`, or `poetry` — use `uv` exclusively.
2. NEVER hardcode secrets, API keys, or tokens.
3. NEVER use emojis in output, plans, or documentation.
4. NEVER use `view_file` without `StartLine` and `EndLine` arguments.
5. Prefer dedicated search tools for broad repo searches. Direct grep/find is acceptable for simple, well-scoped queries. Use smart_search.sh for token-efficient broad searches and Claude Code's native semantic search for symbol lookups.
6. NEVER use `os.environ`/`os.getenv` outside the Entrypoint Layer (`main.py`, `jobs/`, `config.py`); inject config via a typed `Settings` object.
7. NEVER instantiate stateful dependencies (DB/API clients) at module level — no global state.
8. NEVER import from a higher architectural layer (Layer 1 cannot import Layer 3, etc.).
9. NEVER use backslashes in file paths — always use forward slashes, even on Windows.

---

## Project Development Protocol

- **(a)** `.agent/` files govern this project's workflows and rules — never modify them without explicit instruction.
- **(b)** `.claude/commands/` and `.claude/hooks/` are active for this project — do not duplicate them elsewhere.

---

Full rules reference: `.agent/rules/AGENTS.md`
Workflow reference: `./.agent/workflows/`

# CLAUDE.md — Iocane Harness Repo Constitution

## System Context

This is the **Iocane harness repo** — a [cookiecutter](https://cookiecutter.readthedocs.io/) template for Contract-Driven Development (CDD) workflows. The active template lives in `{{cookiecutter.framework_folder}}/`. Claude must treat that directory as a **template root**, not as a live project: files inside it are scaffolding artifacts destined for generated projects, not sources to execute, test, or evolve independently. The `.claude/` directory at the repo root contains hooks and slash commands that are **active for this harness repo only** and are separate from any generated project's runtime configuration.

---

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
5. NEVER use native `grep`, `find`, or `ls -R` — use dedicated search tools.
6. NEVER use `os.environ`/`os.getenv` outside the Entrypoint Layer (`main.py`, `jobs/`, `config.py`); inject config via a typed `Settings` object.
7. NEVER instantiate stateful dependencies (DB/API clients) at module level — no global state.
8. NEVER import from a higher architectural layer (Layer 1 cannot import Layer 3, etc.).
9. NEVER use backslashes in file paths — always use forward slashes, even on Windows.

---

## Harness Evolution Protocol

These rules govern changes to the harness itself:

- **(a) Template internals are off-limits by default.** Never modify files inside `{{cookiecutter.framework_folder}}/.agent/` without an explicit instruction to do so. Those files are the canonical source of truth for generated projects.
- **(b) Evolve at the source.** When updating workflows, rules, skills, or scripts, edit the template source files directly — do not create parallel copies alongside the originals.
- **(c) Repo-level tooling stays repo-level.** The slash commands in `.claude/commands/` and hooks in `.claude/hooks/` are active for this harness repo. Do not duplicate or shadow them inside the template.

---

Full rules reference: `.agent/rules/AGENTS.md`
Workflow reference: `{{cookiecutter.framework_folder}}/.agent/workflows/`

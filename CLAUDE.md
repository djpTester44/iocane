# CLAUDE.md — Project Constitution

## System Context

This is **{{cookiecutter.project_name}}** — a project generated from the Iocane [cookiecutter](https://cookiecutter.readthedocs.io/) template for Contract-Driven Development (CDD) workflows. Claude must treat this as a **live project**: files here are active sources to develop, test, and evolve. The `.agent/` directory at the repo root contains the active Iocane harness governing this project's workflows, rules, and skills. The `.claude/` directory contains hooks and slash commands active for this project.

---

## [CRITICAL] Golden Rule — The Helpfulness Ban

> This is the single most important rule for Claude Code sessions in this repo.

**NEVER** exceed the explicit scope of the prompt or current workflow step.

- **Helpfulness Ban:** You must NEVER proactively edit files, implement features, or execute commands that were not explicitly requested by the user or mandated by the current workflow step.
- **Assumption Ban:** If a request is ambiguous, or if fixing a requested file implies fixing related files, you must stop and ask for clarification. You may propose next steps, but you are FORBIDDEN from executing them autonomously in the name of "helpfulness" or "proactivity."
- **Revert Ban:** If the user points out an error or out-of-bounds action, you must NOT proactively run `git checkout` or revert changes unless the user explicitly types the command to do so.

---

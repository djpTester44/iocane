# CLAUDE.md -- Project Constitution

## System Context

This is **DataFlow Orchestration Service** -- a cloud-native data orchestration service for automating multi-step data pipelines across heterogeneous systems. For Contract-Driven Development (CDD) workflows. Claude must treat this as a **live project**: files here are active sources to develop, test, and evolve. The `.claude/` directory contains hooks, scripts, skills, commands, and rules governing this project.

---

## Rules for Autonomous Execution

1. Before EVERY phase (triage, architect, checkpoint, validate, batch), re-read CLAUDE.md and the relevant workflow .md file — never work from memory
2. After each phase, write a one-line status to plans/validation-reports/chain-log.md with phase name, files modified, and pass/fail
3. If any phase produces output that doesn't match the expected schema in the workflow doc (or schema referenced by it), STOP and report the deviation instead of improvising
4. Between phases, re-read any file you plan to modify to prevent stale-content errors.

---

## [CRITICAL] Golden Rule — The Helpfulness Ban

> This is the single most important rule for Claude Code sessions in this repo.

**NEVER** exceed the explicit scope of the prompt or current workflow step.

- **Helpfulness Ban:** You must NEVER proactively edit files, implement features, or execute commands that were not explicitly requested by the user or mandated by the current workflow step.
- **Assumption Ban:** If a request is ambiguous, or if fixing a requested file implies fixing related files, you must stop and ask for clarification. You may propose next steps, but you are FORBIDDEN from executing them autonomously in the name of "helpfulness" or "proactivity."
- **Revert Ban:** If the user points out an error or out-of-bounds action, you must NOT proactively run `git checkout` or revert changes unless the user explicitly types the command to do so.

---

Full rules reference: `.claude/rules/`
Commands reference: `.claude/commands/`
Lessons learned: `AGENTS.md`

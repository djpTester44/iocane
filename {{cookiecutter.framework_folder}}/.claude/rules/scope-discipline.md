# SCOPE DISCIPLINE

> This is the single most important rule for Claude Code sessions in this repo.

**NEVER** exceed the explicit scope of the prompt or current workflow step.

- **Helpfulness Ban:** You must NEVER proactively edit files, implement features, or execute commands that were not explicitly requested by the user or mandated by the current workflow step.
- **Assumption Ban:** If a request is ambiguous, or if fixing a requested file implies fixing related files, stop and ask for clarification. You may propose next steps, but executing them autonomously is forbidden.
- **Revert Ban:** If the user points out an error or out-of-bounds action, do NOT proactively run `git checkout` or revert changes unless the user explicitly instructs you.

## [HARD] Workflow Step Ordering

Follow workflow step ordering strictly. Do not skip steps, combine steps, or apply changes directly when a workflow specifies an intermediate step (e.g., triage -> checkpoint -> plan, not triage -> direct edit). The sequence exists to preserve human approval gates.

## [HARD] Agent Tool Usage

When asked to use sub-agents or parallel execution, actually invoke the Agent tool. Do not silently fall back to inline sequential execution -- this defeats parallelization and sub-agent isolation.

## [HARD] No Hardcoded Secrets

secret-scan.sh cannot catch obfuscated formats. Cost of a leaked secret is catastrophic and irreversible -- treat any access-granting string as a secret.

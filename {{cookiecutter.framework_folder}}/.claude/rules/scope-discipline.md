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

## Plan Mode

Every delegation to a stronger model is a direct cost multiplier -- Opus costs ~15x Haiku per token. Over-delegation wastes budget on tasks the current agent or a cheaper model handles correctly. Under-delegation risks quality failures that cost more to fix than the delegation would have cost.

After completing the plan, assign each step the cheapest capable executor: self-execute trivial tasks, Haiku for mechanical transforms, Sonnet for moderate reasoning, Opus only for complex multi-file analysis or nuanced judgment.
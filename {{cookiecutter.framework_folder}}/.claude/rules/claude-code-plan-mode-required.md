# CLAUDE_CODE_PLAN_MODE_REQUIRED: Honor the Orchestrator's Approval Gate

When `CLAUDE_CODE_PLAN_MODE_REQUIRED=true`, Claude is operating as an agent-team teammate inside an orchestrator that declared plan approval required before execution.

## Cost of Bypassing

Executing without plan approval in this context bypasses the orchestrator's review gate -- allowing irreversible changes (file writes, tool calls, external side effects) to commit before the orchestrator has seen or approved the plan. In a multi-agent pipeline, this is unrecoverable: downstream agents may act on unapproved state.

## [HARD] Behavioral Constraint

This env var is read-only and set by Claude Code's agent-team infrastructure, not by the user. Its presence is an architectural signal, not a preference. Treat it as equivalent to a human gate: no implementation proceeds until plan mode has been entered and the orchestrator has approved.

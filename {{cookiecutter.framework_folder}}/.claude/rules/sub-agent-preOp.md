---
paths:
  - "plans/tasks/CP-*.md"
---

# SUB-AGENT PRE-OPERATION RULES

> **Context:** You are a headless sub-agent executing a single checkpoint in an isolated git worktree.
> Read your task file completely before taking any action.

## [HARD] Context Hygiene

Speculative reads in a headless sub-agent waste tokens against a fixed turn limit and risk acting on stale cross-checkpoint state. Your task file's Context Files list is the complete source of truth -- read nothing outside it.

## [CRITICAL] TDD

**No implementation without a test.** Untested code is invisible to the gate command -- a FAIL status wastes the entire sub-agent session. **YAGNI** -- do not add "just in case" helper functions.

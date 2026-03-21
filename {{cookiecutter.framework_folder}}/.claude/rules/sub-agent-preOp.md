---
paths:
  - "plans/tasks/CP-*.md"
---

# SUB-AGENT PRE-OPERATION RULES

> **Context:** You are a headless sub-agent executing a single checkpoint in an isolated git worktree.
> Read your task file completely before taking any action.

## [HARD] Context Hygiene

You are **FORBIDDEN** from reading files outside the `## Context Files` list in your task file. Do not speculatively read files to orient yourself — your task file is the complete source of truth for this execution.

## [HARD] Write Hygiene

You are **FORBIDDEN** from writing to files not listed in `## Write Targets` in your task file. The `write-gate.sh` PreToolUse hook enforces this and will block writes outside the worktree boundary.

## [HARD] No Directory Traversal

You are **FORBIDDEN** from using `cd ..` or any upward path traversal in Bash commands. You operate in the worktree root. If a tool reports "can't read file", the cause is that you wrote to the wrong path — fix the write, do not change directory.

## [CRITICAL] TDD CYCLE

1. **RED**: Write a failing test for the specific requirement. Verify it fails before proceeding.
2. **GREEN**: Write the *minimal* code to pass that test. Verify it passes.
3. **REFACTOR**: Run `uv run rtk ruff check <write-target-dir>` and `uv run rtk mypy <write-target-dir>`. Scope to your write targets only — never `.` (the whole repo).

**No implementation without a test.** If it's not tested, it doesn't exist. **YAGNI** — do not add "just in case" helper functions.

## [HARD] State Verification

Never trust cached line numbers or file contents across tool calls. When a formatter or linter modifies a file, re-read it before editing. For test regressions: `git stash` + run + `git stash pop` before investigating.

## [HARD] Completion

1. Run the gate command from your task file and capture the output as proof.
2. On success: write `PASS` to `../../plans/tasks/[CP-ID].status`.
3. On failure or blocker: write `FAIL: [reason]` and stop — do not attempt workarounds.

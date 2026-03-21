---
trigger: glob
description: Single Source of Truth for Backlog Ticket Labels and Routing
globs: plans/backlog.md
---

# TICKET TAXONOMY & ROUTING RULES

> **Context:** All items in `plans/backlog.md` MUST be prefixed with one of the following exact tags to govern workflow routing.
> Each item has a unique `**BL-NNN**` identifier on the line above it, auto-assigned by the
> `backlog-id-assign.sh` PostToolUse hook. Reference items by BL-ID in all downstream workflows.

## 1. Valid Tags & Definitions

*   **`[DESIGN]`** — A change that requires generating or updating a CRC card AND modifying/creating a `.pyi` contract.
    *   *Examples:* Adding a new collaborator, changing a method signature, removing global config consumption.
    *   *Required Execution Path:* `/io-architect` -> `/validate-plan` -> `/io-plan-batch` -> `/io-orchestrate`

*   **`[REFACTOR]`** — A behavioral change that requires a CRC update, but NO new `.pyi` interface (the contract signature remains exactly the same).
    *   *Examples:* Injecting a config value that is currently hardcoded, restructuring internal logic.
    *   *Required Execution Path:* `/io-architect` (CRC only) -> `/validate-plan` -> `/io-plan-batch` -> `/io-orchestrate`

*   **`[CLEANUP]`** — A pure internal code, style, or logic fix. No design or contract change needed.
    *   *Examples:* Dead code, unconventional imports, typos, missing docstrings.
    *   *Required Execution Path:* `/validate-plan` -> `/io-plan-batch` -> `/io-orchestrate` (bypasses `/io-architect`)

*   **`[DEFERRED]`** — Known technical debt implicitly accepted for the current phase. Ignored by execution gates.
    *   *Examples:* Async migration for a sync prototype, optimizing a dev-only tool.

*   **`[TEST]`** — Missing test coverage.
    *   *Connectivity test (CT) gaps:* Create the CT file from the spec in `plans/plan.md` and run the gate command. If `/io-ct-remediate` exists, use it.
    *   *Unit test gaps:* Amend the relevant checkpoint in `plans/plan.md` to include the missing test file in its write targets (or add a new checkpoint), then route through `/validate-plan` -> `/io-plan-batch` -> `/io-orchestrate`.

## 2. Gate Enforcement Rules

*   **Orchestration Blocker:** `/io-plan-batch` MUST NOT proceed if any open `[DESIGN]` or `[REFACTOR]` tickets exist in the active backlog without first running `/io-architect`.
*   **Architect Boundary:** `/io-architect` MUST NOT execute `.py` edits. Hybrid tickets must be left open or converted to `[CLEANUP]` so they cleanly pass to `/io-plan-batch`.

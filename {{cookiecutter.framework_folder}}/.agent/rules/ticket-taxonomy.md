---
trigger: glob
description: Single Source of Truth for Backlog Ticket Labels and Routing
globs: plans/PLAN.md
---

# TICKET TAXONOMY & ROUTING RULES

> **Context:** All items in `plans/PLAN.md` `## 3. Remediation Backlog` MUST be prefixed with one of the following exact tags to govern workflow routing.

## 1. Valid Tags & Definitions

*   **`[DESIGN]`** — A change that requires generating or updating a CRC card AND modifying/creating a `.pyi` contract.
    *   *Examples:* Adding a new collaborator, changing a method signature, removing global config consumption.
    *   *Required Execution Path:* `/io-architect` -> `/io-tasking` -> `/io-loop`

*   **`[REFACTOR]`** — A behavioral change that requires a CRC update, but NO new `.pyi` interface (the contract signature remains exactly the same).
    *   *Examples:* Injecting a config value that is currently hardcoded, restructuring internal logic.
    *   *Required Execution Path:* `/io-architect` (CRC only) -> `/io-tasking` -> `/io-loop`

*   **`[CLEANUP]`** — A pure internal code, style, or logic fix. No design or contract change needed.
    *   *Examples:* Dead code, unconventional imports, typos, missing docstrings.
    *   *Required Execution Path:* `/io-tasking` -> `/io-loop` (bypasses `/io-architect`)

*   **`[DEFERRED]`** — Known technical debt implicitly accepted for the current phase. Ignored by execution gates.
    *   *Examples:* Async migration for a sync prototype, optimizing a dev-only tool.

*   **`[TEST]`** — Missing test coverage.

## 2. Gate Enforcement Rules

*   **Handoff Blocker:** `/io-handoff` MUST HALT if any open `[DESIGN]` or `[REFACTOR]` tickets exist in the active backlog.
*   **Architect Boundary:** `/io-architect` MUST NOT execute `.py` edits. Hybrid tickets must be left open or converted to `[CLEANUP]` so they cleanly pass to `/io-loop`.

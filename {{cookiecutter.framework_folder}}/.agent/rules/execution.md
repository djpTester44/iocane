---
trigger: glob
description: Execution constraints for sub-agents implementing checkpoints.
globs: **/*.py
---

# EXECUTION MODE RULES

> **Context:** You are in the IMPLEMENTATION phase.
> You are actively editing `.py` files.

## [HARD] Context & Navigation Constraints

1. **Context Hygiene (Reads)**: You are **FORBIDDEN** from reading files outside the scope of your current task.
    You must only read the files listed in `## Context Files` in your task file (`plans/tasks/CP-XX.md`).
2. **Write Hygiene**: You are **FORBIDDEN** from writing to files not listed in `## Write Targets` in your task file.
    The `write-gate.sh` PreToolUse hook enforces this automatically.
3. **Task Source**: Your objective, write targets, gate command, and context files are all in your task file. Read it completely before taking any action.
4. **State Verification**: Never trust cached line numbers or file contents across session boundaries. When external tools (formatters, linters) modify files, you **MUST** re-read them before editing. For test regressions: `git stash` + run + `git stash pop` before investigating.

## [HARD] Architectural Guidance

> **Note:** The corresponding FORBIDDEN actions (no `os.environ` in domain, no global state, no upward imports) are enforced globally in `AGENTS.md` Section 3 (Rules 6-8). This section provides **positive guidance** on how to comply.

1. **Foundation Layer Verification (Layer 1)**:
    - Before modifying the Foundation layer, verify it has ZERO internal project dependencies.
    - It should only contain Config, Types, and Domain Primitives.

2. **Configuration Injection Pattern**:
    - Accept a typed `Settings` object (from Layer 1) in `__init__`.
    - Environment variables and raw config files are read only at the Entrypoint Layer.

3. **Side-Effect-Free Modules**:
    - Logic lives in functions or classes. Top-level code is exclusively definitions (classes, constants, functions).
    - Stateful dependencies (DB clients, API clients) are received via constructor injection.

## [HARD] Base Requirements

1. **Protocols are Law (Structure)**: The `.pyi` files in `interfaces/` are **BINDING CONTRACTS**.
    You are forbidden from changing the signature. You must implement it exactly as defined.
2. **Design is Intent (Behavior)**: You **MUST** implement the internal logic strictly as defined in the **Component Specification (CRC)** in `plans/project-spec.md`.
    - **Constraint:** Do not add side effects, state mutations, or external calls not explicitly listed in the CRC/Sequence.
    - **Drift:** If the implementation requires logic not in the CRC, you MUST stop and request a design update via `/io-architect`.
    - **Atomic CRC Sync:** Any behavioral change (new methods, exceptions, collaborators) requires an atomic CRC update in the same edit batch.
    - **Compliance Arbitration:** When automated scripts (e.g., `check_di_compliance.py`) flag a structural discrepancy, cross-reference the CRC first. If the implementation matches the CRC, classify as a `[DESIGN]` gap, not a code error.
3. **Test-Driven**: If you are fixing a bug or adding a feature, you **MUST** follow the Red/Green/Refactor state machine.
4. **Run Tests**: You **MUST** run `uv run pytest` (or specific test file) after every meaningful change.
    - **Token Efficiency:** Analyze the failure message first. Only increase verbosity or debug if the initial error is ambiguous.
5. **No Broken Windows**: You **MUST NOT** leave the build in a broken state between tool calls if possible.

## [CRITICAL] TDD CYCLE

### The Cycle

1. **RED**: Write a failing test for the specific requirement. Verify the test fails.
2. **GREEN**: Write the *minimal* code to pass that test. Verify the test passes.
3. **REFACTOR**: Clean up the code. Run `uv run ruff check .` and `uv run mypy .`.

### Constraints

- **No Implementation without Test**: If it's not tested, it doesn't exist.
- **YAGNI**: do not add "just in case" helper functions.

## PYTHON DEVELOPMENT STANDARDS

### Async I/O

- Use `httpx`, `aiofiles`, `asyncpg` for I/O.
- **NEVER** block the event loop with synchronous calls in async contexts.

### Error Handling

- Raise specific, custom exceptions defined in `interfaces/exceptions.pyi`.
- **NEVER** return `None` or sentinel values (`-1`, `False`) to indicate failure.
- Validate all inputs at function entry points.

### File Operations

- Use `pathlib.Path` for ALL path manipulation.
- **NEVER** concatenate strings to build paths.

### Module Docstrings

Every `.py` file you create **MUST** begin with a module-level docstring as the first statement, before any imports. One sentence stating what this module owns — not what it does step-by-step.

```python
"""Owns the inference routing logic. Routes validated payloads to the correct handler via InferenceRouterProtocol."""

from __future__ import annotations
```

The docstring must state:
- What the module is responsible for (ownership)
- Which Protocol it implements or collaborates with, if any

Do not describe implementation mechanics. The docstring is a navigation aid, not a tutorial.

### Naming Conventions

- **Functions/Variables**: `snake_case`
- **Classes**: `PascalCase`
- **Constants**: `UPPER_SNAKE`

## VERIFICATION REQUIREMENTS

1. **Status File**: Upon completing your gate command successfully, write `PASS` to `../../plans/tasks/[CP-ID].status`. On any escalation trigger, write `FAIL: [reason]` instead.
2. **Proof**: You **MUST** provide the gate command output as evidence before writing the status file.

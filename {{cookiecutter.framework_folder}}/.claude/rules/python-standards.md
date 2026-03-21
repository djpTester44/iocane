---
paths:
  - "**/*.py"
---

# PYTHON DEVELOPMENT STANDARDS

## [HARD] Test Integrity

You are **FORBIDDEN** from weakening test assertions to force a GREEN state. Catching `Exception` instead of a specific exception type, skipping assertions, or mocking away the code under test are all violations. A green test that lies is a worse outcome than a failing test.

## Async I/O

- Use `httpx`, `aiofiles`, `asyncpg` for I/O.
- **NEVER** block the event loop with synchronous calls in async contexts.

## Error Handling

- Raise specific, custom exceptions defined in `interfaces/exceptions.pyi`.
- **NEVER** return `None` or sentinel values (`-1`, `False`) to indicate failure.
- Validate all inputs at function entry points.

## File Operations

- Use `pathlib.Path` for ALL path manipulation.
- **NEVER** concatenate strings to build paths.

## Module Docstrings

Every `.py` file you create **MUST** begin with a module-level docstring as the first statement, before any imports. One sentence stating what this module owns — not what it does step-by-step.

```python
"""Owns the inference routing logic. Routes validated payloads to the correct handler via InferenceRouterProtocol."""

from __future__ import annotations
```

The docstring must state:

- What the module is responsible for (ownership)
- Which Protocol it implements or collaborates with, if any

Do not describe implementation mechanics. The docstring is a navigation aid, not a tutorial.

## Naming Conventions

- **Functions/Variables**: `snake_case`
- **Classes**: `PascalCase`
- **Constants**: `UPPER_SNAKE`

---
paths:
  - "**/*.py"
---

# PYTHON DEVELOPMENT STANDARDS

## [HARD] Test Integrity

You are **FORBIDDEN** from weakening test assertions to force a GREEN state. Catching `Exception` instead of a specific exception type, skipping assertions, or mocking away the code under test are all violations. A green test that lies is a worse outcome than a failing test.

## Async I/O

Blocking the event loop with synchronous calls in async contexts causes deadlocks. Use httpx/aiofiles/asyncpg for I/O.

## Error Handling

Sentinel returns (None, -1, False) hide failures from callers. Raise specific custom exceptions from interfaces/exceptions.pyi.

## Data Modeling Defaults

These defaults reduce hidden state and improve testability:

- **Dataclasses:** Use `frozen=True` by default. Mutable dataclasses require explicit justification.
- **Pydantic at boundaries:** Prefer Pydantic models over raw dicts at system boundaries (external input, API responses). Dicts are acceptable for internal, ephemeral data.

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

## File Operations

String-concatenated paths break across OS boundaries. Use pathlib.Path exclusively.

## Module Docstrings

A module docstring is a navigation aid: state what this module owns (not how), and which Protocol it implements or collaborates with.

## Code Quality Defaults

These defaults reduce hidden state and improve testability -- not style preferences:

- **Type hints:** All signatures must use modern syntax (`list[str]`, not `List[str]`). `Any` is forbidden -- if you don't know the type, define an interface.
- **Dataclasses:** Use `frozen=True` by default. Mutable dataclasses require explicit justification.
- **Dicts vs models:** Prefer Pydantic models over raw dicts at system boundaries. Dicts are acceptable for internal, ephemeral data.

## Logging

print() lacks log levels, structured output, and production-safe suppression -- production logs become unfiltered noise.

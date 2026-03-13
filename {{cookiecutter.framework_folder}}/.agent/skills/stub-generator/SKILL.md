---
name: stub-generator
description: Generate minimal class/function stubs from test file imports to enable TDD Red phase when pytest collection fails with ImportError due to missing classes/functions. Use when tests fail to collect because the implementation does not exist yet.
---

# Stub Generator

Generate implementation stubs from `.pyi` Protocol definitions for TDD.

## Trigger Examples

- "Create stubs for this Protocol"
- "Generate implementation skeleton from interface"
- "Tests fail with ImportError, need stubs"
- "Scaffold the implementation file"

## Workflow

### Mode A: From Protocol (.pyi-first)

1. **Read** the Protocol from `interfaces/<component>.pyi`
2. **Generate** implementation stub at `src/<component>.py`:
   - Import the Protocol for type checking
   - Create class implementing the Protocol
   - Method bodies: `raise NotImplementedError`
3. **Verify** type checker passes: `uv run rtk pyright src/<component>.py`

### Mode B: From Test Imports (legacy TDD)

1. **Analyze** the test file:

   ```bash
   uv run rtk python scripts/analyze_imports.py <test_file>
   ```

2. **Parse** the JSON output containing missing imports with:
   - `module`: The missing module path
   - `names`: List of classes/functions imported
   - `suggested_path`: Where to create the stub

3. **Generate** stub files at each `suggested_path`:
   - **Classes**: Empty with `pass` body
   - **Functions**: `raise NotImplementedError`
   - **Protocols/ABCs**: `...` for method bodies
   - **Pydantic models**: Inherit from `BaseModel` with `pass`

4. **Verify** collection succeeds:

   ```bash
   uv run rtk pytest --collect-only <test_file>
   ```

5. **Confirm** tests now fail via assertion, not ImportError

## Constraints

- Do NOT create full implementations (stubs only)
- Do NOT use actual logic in stub functions (use `raise NotImplementedError`)
- Do NOT leave classes without at least `pass` body
- Tests should fail by assertion after stubbing, NOT by ImportError

## Example Output (Mode A: From .pyi)

Given `interfaces/user_service.pyi`:

```python
class UserServiceProtocol(Protocol):
    def get_user(self, user_id: str) -> User: ...
    def create_user(self, name: str) -> User: ...
```

Generate `src/user_service.py`:

```python
"""UserService implementation."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from interfaces import UserServiceProtocol

from src.models import User


class UserService:
    """Implements UserServiceProtocol."""

    def get_user(self, user_id: str) -> User:
        raise NotImplementedError

    def create_user(self, name: str) -> User:
        raise NotImplementedError
```

## Example Output (Mode B: From Test)

```python
class UserService:
    pass


def create_user(name: str) -> None:
    raise NotImplementedError
```
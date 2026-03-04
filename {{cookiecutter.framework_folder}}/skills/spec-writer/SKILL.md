---
name: spec-writer
description: Generates granular Python Interfaces and Protocols with strict typing; no implementation logic allowed. Use when designing new components, defining contracts between modules, or documenting expected behavior before implementation.
---

# Spec Writer

Generate Python Interfaces and Protocols as `.pyi` stub files.

## Trigger Examples

- "Define the interface for X"
- "Create a Protocol for this component"
- "Design the contract before implementing"
- "Add a new interface to the project"

## Workflow

1. **Review** existing `interfaces/*.pyi` files to ensure consistency
2. **Define** interface as `typing.Protocol` class with full type hints
3. **Create** `.pyi` file at `interfaces/<component_name>.pyi`
4. **Update** `interfaces/__init__.pyi` to export the new Protocol
5. **Document** in `plans/project-spec.md` under **Interfaces (Ports)** (reference only)

## Constraints

- **NO LOGIC**: Method bodies must be `...` only
- **OUTPUT**: `.pyi` files in `interfaces/` directory (not markdown)
- **IMPORTS**: Use `from typing import Protocol` and relative imports for models

## File Structure

```
interfaces/
  __init__.pyi      # Re-exports all Protocols
  models.pyi        # Domain models (dataclasses, Pydantic)
  exceptions.pyi    # Custom exception hierarchy
  <component>.pyi   # One Protocol per file
```

## Template

```python
"""<ProtocolName> - One-line contract description."""

from typing import Protocol
from pathlib import Path

from .models import RelevantModel
from .exceptions import RelevantError


class ComponentNameProtocol(Protocol):
    """Contract for <component description>.

    Responsibility: <Single Responsibility description>.
    """

    def method_name(self, param: ParamType) -> ReturnType:
        """Action verb description.

        Args:
            param: Description.

        Returns:
            Description.

        Raises:
            RelevantError: When condition occurs.
        """
        ...
```

## Required Input

Caller MUST provide:

- `component_name`: Name of the component to define
- `responsibilities`: List of responsibilities/methods needed
- `context`: Existing `interfaces/__init__.pyi` content

## Output Format

Return file creation instructions:

```json
{
  "file_path": "interfaces/<component>.pyi",
  "protocol_code": "<full .pyi file content>",
  "init_export": "<line to add to __init__.pyi>"
}
```
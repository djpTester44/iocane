---
name: refactor-guru
description: Optimizes code for SOLID, DRY, and Readability principles. Use after minimal-coder phase to clean up working code, or when code review identifies maintainability issues.
---

# Refactor Guru

Optimize code for SOLID, DRY, and Readability.

## Workflow

1. **Analyze** - Identify DRY, SRP, DIP violations
2. **Refactor** - Rewrite code to fix identified issues
3. **Verify** - Ensure strict type hinting (Pydantic/Typing) is applied

## Checklist

### DRY Violations

- [ ] Repeated code blocks
- [ ] Similar functions with minor variations

### SRP Violations

- [ ] Functions longer than 20 lines
- [ ] Functions with multiple responsibilities

### DIP Violations

- [ ] Direct instantiation of dependencies
- [ ] Concrete types instead of abstractions in signatures

## Required Input

Caller MUST provide (do not fetch):

- `code`: The code to refactor (paste content directly)
- `focus`: "DRY" | "SRP" | "DIP" | "all"

## Output Format

Return refactored code with violations fixed:

```json
{
  "violations_found": [{"type": "DRY", "location": "lines 10-20"}],
  "code": "<refactored code with type hints and docstrings>"
}
```
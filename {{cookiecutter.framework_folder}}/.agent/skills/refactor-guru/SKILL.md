---
name: refactor-guru
description: Optimizes code for SOLID, DRY, and Readability principles. Use after minimal-coder phase to clean up working code, or when code review identifies maintainability issues.
---

# Refactor Guru

Optimize code for SOLID, DRY, and Readability.

## Workflow

1. **Analyze** - Identify violations of:
   - **DRY**: Duplicate logic should be abstracted
   - **SRP** (Single Responsibility): Functions doing too much should be split
   - **DIP** (Dependency Inversion): Hardcoded dependencies should be injected
2. **Refactor** - Rewrite code to fix identified issues
3. **Verify** - Ensure strict type hinting (Pydantic/Typing) is applied

## Checklist

### DRY Violations

- [ ] Repeated code blocks (3+ lines appearing twice or more)
- [ ] Similar functions with minor variations
- [ ] Copy-pasted logic with different variable names

### SRP Violations

- [ ] Functions longer than 20 lines
- [ ] Functions with multiple responsibilities (AND in description)
- [ ] Classes with unrelated methods

### DIP Violations

- [ ] Direct instantiation of dependencies inside functions
- [ ] Hardcoded configuration values
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
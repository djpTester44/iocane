---
name: test-writer
description: Writes comprehensive unit tests based on Interface definitions from the project specification. Use when creating tests for new or existing code, following AAA (Arrange-Act-Assert) structure with proper coverage of happy paths, edge cases, and error states.
---

# Test Writer

Write comprehensive unit tests based on Interface definitions.

## Workflow

1. **Read** the target Protocol from `interfaces/<component>.pyi`
2. **Import** the Protocol: `from interfaces import ComponentProtocol`
3. **Create** a `tests/test_<component>.py` file using pytest
4. **Ensure** coverage includes:
   - Happy Path (expected behavior)
   - Edge Cases (nulls, boundaries)
   - Error States (ensure exceptions are raised)

## Templates

- [conftest_template.py](assets/conftest_template.py) - Common fixtures and configuration
- [test_template.py](assets/test_template.py) - AAA structure test template

## Required Input

Caller MUST provide (do not fetch):

- `interface_file`: Path to `.pyi` file (e.g., `interfaces/extractor.pyi`)
- `interface_code`: Protocol definition from `.pyi` file (paste content directly)
- `impl_code`: Implementation to test if exists (paste content directly)
- `test_scope`: "unit" | "integration" | "e2e"

## Output Format

Return test file:

```json
{
  "test_code": "<full test file content>",
  "coverage": ["happy_path", "edge_cases", "error_states"]
}
```

Do NOT include explanations unless explicitly requested.
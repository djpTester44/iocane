---
name: test-writer
description: Writes comprehensive unit tests based on Interface definitions from the project specification. Use when creating tests for new or existing code, following AAA (Arrange-Act-Assert) structure with proper coverage of happy paths, edge cases, and error states.
---

# Test Writer

Write comprehensive unit tests based on Interface definitions.

## Trigger Examples

- "Write tests for X"
- "Create unit tests for this Protocol"
- "Add test coverage for the new component"
- "Test the implementation against its interface"

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

## AAA Structure

```python
def test_feature_does_something():
    # Arrange - Set up test data
    input_data = {"key": "value"}
    
    # Act - Execute the code under test
    result = function_under_test(input_data)
    
    # Assert - Verify expected outcomes
    assert result == expected_value
```

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

## Coverage Checklist

- [ ] Happy path returns expected result
- [ ] Empty input handled gracefully
- [ ] None/null input raises appropriate error
- [ ] Boundary values tested
- [ ] Dependency failures propagate correctly
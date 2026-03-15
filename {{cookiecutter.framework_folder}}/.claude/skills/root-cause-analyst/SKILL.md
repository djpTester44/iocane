---
name: root-cause-analyst
description: Analyzes errors to isolate the root cause by tracing execution paths and generating reproducible test cases. Use when debugging failures, especially when the error message alone does not reveal the underlying issue.
---

# Root Cause Analyst

Analyze errors to isolate the root cause.

## Workflow

1. **Trace** - Follow the execution path in the stack trace
   - Identify the failing line
   - Trace back through call stack
   - Identify variable states at each step

2. **Hypothesize** - Identify the exact variable state or logic gap causing the failure
   - What value was expected?
   - What value was actual?
   - Why did the discrepancy occur?

3. **Reproduce** - Generate a minimal Python script or `pytest` case that triggers the exact error
   - Isolate the failing condition
   - Remove unrelated code
   - Create minimal reproduction

## Required Input

Caller MUST provide (do not fetch):

- `error_output`: Full error message and stack trace (paste directly)
- `relevant_code`: Code files involved in the error (paste content directly)

## Output Format

```markdown
## Root Cause Analysis

### Error
[Error message and type]

### Stack Trace Summary
1. [file:line] - [function] - [what happened]
2. [file:line] - [function] - [what happened]

### Root Cause
[Explanation of why the error occurred]

### Reproduction
```python
# Minimal test case
def test_reproduction():
    # Arrange
    ...
    # Act
    ...
    # Assert - should raise [ErrorType]
```

### Suggested Fix

[Description of the fix]

```
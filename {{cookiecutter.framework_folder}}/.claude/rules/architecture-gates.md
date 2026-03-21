---
paths:
  - "src/**/*.py"
  - "tests/**/*.py"
---

# ARCHITECTURE GATES

> **Context:** These rules govern structural compliance checks during implementation.

## DI COMPLIANCE

### The AST Limitation

`.agent/scripts/check_di_compliance.py` uses static AST parsing. It will flag a `[CRITICAL]` violation if it cannot statically verify that a collaborator is injected via `__init__`. It cannot parse dynamic unpacking (`**kwargs`), factory patterns, or delayed initialization.

### [HARD] The Escape Hatch

If your implementation requires dynamic injection or a factory pattern that legitimately bypasses the AST parser, append `# noqa: DI` to the class definition line OR the `__init__` definition line.

```python
class ModelOrchestrator:  # noqa: DI
    def __init__(self, **kwargs):
        self.client = kwargs.get("client")
```

### [CRITICAL] Persistent Technical Debt Logging

Using `# noqa: DI` is an admission of architectural technical debt. **If you use `# noqa: DI`, the build will fail unless a matching active ticket exists in the Remediation Backlog.**

You **MUST**:

1. Add an inline comment above the `# noqa: DI` explaining exactly *why* the strict injection pattern could not be followed.
2. Document the deviation in the task log when marking your task complete.
3. Add a corresponding entry in `plans/plan.md` Remediation Backlog in exactly this format:
   `- [ ] [REFACTOR] ComponentName` or `- [ ] [CLEANUP] ComponentName`

**Forbidden:** Using `# noqa: DI` to bypass a failing test or save time writing proper injection boilerplate.

### [HARD] Layout Boundaries

All components in the Interface Registry must resolve to file paths strictly within `src/`. Any component mapped outside this boundary triggers a `[CRITICAL]` failure.

### Gate Exit Codes

- **[CRITICAL]:** Hardcoded internal instantiation, untracked `# noqa: DI`, or `src/` boundary violations. Exit Code 1.
- **[WARNING]:** A required collaborator is completely unresolvable. Exit Code 1.
- **[INFO]:** Legitimate tracked deferrals or factory-parameter heuristics. Exit Code 0.

---

## DEPENDENCY ANALYSIS

### [HARD] When to Run

Run `uv run rtk lint-imports` during `/io-review` pre-scan to surface coupling and contract compliance.

### [HARD] Contract Enforcement

- **Contracts are workspace-specific**: Read `pyproject.toml` `[tool.importlinter]` for the current workspace's root packages and contracts.
- **Self-layer imports are allowed**: Only **cross-layer** or **independence** boundaries are governed.

### Commands

```bash
# Full check (CI / verify steps)
uv run rtk lint-imports

# Visual exploration
uv run rtk import-linter explore <package>
```

### [CRITICAL] Technical Debt

1. **NEVER suppress a violation** by removing a contract.
2. If a violation cannot be fixed, add it to `ignore_imports` with a comment tracking it for a future phase.
3. Always check the `ignore_imports` list to understand current known architectural debt.

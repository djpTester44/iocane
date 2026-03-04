---
trigger: glob
description: Architectural constraints for resolving Dependency Injection AST parser failures and managing technical debt.
globs: **/*.py
---

# DI COMPLIANCE & ESCAPE HATCH PROTOCOL

> **Context:** These rules govern how to handle false positives or unavoidable violations caught by `.agent/scripts/check_di_compliance.py`.

## 1. The AST Limitation

The `.agent/scripts/check_di_compliance.py` script uses static AST parsing. It will flag a `[CRITICAL]` violation if it cannot statically verify that a collaborator is injected via `__init__`. It cannot parse dynamic unpacking (`**kwargs`), factory patterns, or delayed initialization.

## 2. [HARD] The Escape Hatch

If your implementation requires dynamic injection or a factory pattern that legitimately bypasses the AST parser, you are permitted to use an escape hatch.

You must append `# noqa: DI` to the class definition line OR the `__init__` definition line.

**Example:**

```python
class ModelOrchestrator:  # noqa: DI
    def __init__(self, **kwargs):
        self.client = kwargs.get("client")
```

## 3. [CRITICAL] Persistent Technical Debt Logging

Using `# noqa: DI` is an admission of architectural technical debt or a limitation in static verification. The pipeline enforces a strict gate: **If you use `# noqa: DI`, the build will fail unless a matching active ticket exists in the Remediation Backlog.**

If you use this escape hatch, you **MUST**:

1. Add an inline comment above the `# noqa: DI` explaining exactly *why* the strict injection pattern could not be followed.
2. Ensure this deviation is documented in the task log when marking your current task complete in `plans/tasks.json`.
3. **Persist the Debt:** There MUST be a corresponding entry in the `## 3. Remediation Backlog` section of `plans/PLAN.md`. The script validates this using strict regex matching. The format must be exactly:
   `- [ ] [REFACTOR] ComponentName` or `- [ ] [CLEANUP] ComponentName`

**Forbidden Action:** You are strictly forbidden from using `# noqa: DI` simply to bypass a failing test or to save time writing proper injection boilerplate.

## 4. [HARD] Layout Boundaries

The compliance script actively enforces the architectural workspace boundary. All components mapped in the Interface Registry must resolve to file paths strictly contained within the `src/` directory. Any component mapped outside this boundary will trigger a `[CRITICAL]` failure.

## 5. Strict Gate Enforcement

The script operates as a strict binary gate for the execution loop:
* **[CRITICAL]:** Hardcoded internal instantiation, untracked `# noqa: DI` suppressions, or `src/` boundary violations. Yields Exit Code 1.
* **[WARNING]:** A required collaborator is completely unresolvable from any injected source. Yields Exit Code 1.
* **[INFO]:** Legitimate, tracked deferrals or factory-parameter heuristics. Yields Exit Code 0.
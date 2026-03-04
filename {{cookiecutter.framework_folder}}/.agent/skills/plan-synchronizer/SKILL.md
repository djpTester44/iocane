---
name: plan-synchronizer
description: Ensures that progress in tactical documents (PLAN.md) is correctly reflected in strategic documents (implementation_plan.md). Use when syncing task completion status between different planning documents.
---

# Plan Synchronizer

Synchronize progress between tactical and strategic planning documents.

## Workflow

1. **Read Source** - Read the `source_plan` and identify all completed tasks (`- [x] ...`)
2. **Read Target** - Read the `target_plan` and identify all open tasks (`- [ ] ...`) or in-progress tasks (`- [/] ...`)
3. **Fuzzy Match** - Compare completed source tasks with target tasks using:
   - Direct Match (exact text)
   - Subset Match (partial text overlap)
   - ID Match (preferred, using `<!-- id: X -->` tags)
4. **Update Target** - If a source task is `[x]` and matching target task is NOT `[x]`, mark target as `[x]` while preserving existing IDs and structure
5. **Recursive Check** - If all subtasks of a target task are `[x]`, mark the parent task as `[x]`
6. **Report** - Output a list of what was changed

## Constraints

- **Conservative**: Only mark as complete if confident in the match
- **Report**: Must output a list of changes made

## ID Tag Format

Prefer explicit ID tags for reliable matching:

```markdown
- [ ] Implement user authentication <!-- id: auth-001 -->
  - [ ] Create login endpoint <!-- id: auth-001-a -->
  - [ ] Add JWT validation <!-- id: auth-001-b -->
```
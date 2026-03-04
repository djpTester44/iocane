---
description: Profile and analyze code for optimization opportunities. Reports findings - does not implement changes.
---

# WORKFLOW: CODE OPTIMIZATION ANALYSIS

> **Purpose:** Identify and report optimization opportunities with measured data.
> **Scope:** Research and recommendations only - no implementation.

---

## Procedure

### 1. GATHER CONTEXT

Ask if not provided:
- **Code:** Which function/module to analyze?
- **Concern:** Time, space, or both?
- **Context:** Typical input size?

### 2. MEASURE CURRENT PERFORMANCE

Run profiler to establish baseline:

```bash
# Function-level timing
uv run python -m cProfile -s cumtime <script.py> 2>&1 | head -30

# Or for specific function timing
uv run python -c "import timeit; print(timeit.timeit('<code>', number=1000))"
```

Record:
- Current execution time.
- Memory usage if relevant (`tracemalloc`).

### 3. ANALYZE WITH SKILL

**Read the skill:** `.agent/skills/code-optimizer/SKILL.md`

Using the skill's reference tables, identify:
- Current Big-O complexity.
- Applicable optimization techniques.
- Expected complexity after optimization.

### 4. REPORT FINDINGS

Present analysis to user:

```markdown
## Optimization Analysis: {function/module name}

### Current State
| Metric | Value |
|--------|-------|
| Time (n={size}) | {measured} |
| Complexity | O(?) |
| Bottleneck | {description} |

### Recommended Optimization
| Technique | Expected Result |
|-----------|-----------------|
| {technique from skill} | O(?) -> O(?) |

### Changes Required
- {file}:{location} - {what would change}
- {file}:{location} - {what would change}

**Action:** If approved, run `/io-architect` to update the Design Anchor before implementation.
```

---

## References
- Skill: `.agent/skills/code-optimizer/SKILL.md`
- Complexity cheatsheet: `.agent/skills/code-optimizer/references/complexity_cheatsheet.md`
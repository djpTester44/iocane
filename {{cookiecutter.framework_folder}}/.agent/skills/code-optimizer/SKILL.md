---
name: code-optimizer
description: Reference for code optimization techniques, Big-O complexity, and Python-specific performance patterns. Use when analyzing code efficiency or selecting optimization strategies.
---

# Code Optimizer - Reference

Quick reference for optimization techniques and complexity analysis.

> **Note:** For the full optimization workflow with profiling and verification, use `/optimize-code`.

---

## Profiling Tools

| Tool | Use Case | Command |
|------|----------|---------|
| `cProfile` | Function-level timing | `python -m cProfile -s cumtime script.py` |
| `line_profiler` | Line-by-line hotspots | `kernprof -l -v script.py` |
| `timeit` | Microbenchmarks | `python -m timeit '<expression>'` |
| `tracemalloc` | Memory tracking | `tracemalloc.start()` in code |

---

## Common Techniques

| Problem | Solution | Complexity Change |
|---------|----------|-------------------|
| Repeated lookups in list | Convert to `set` or `dict` | O(n) -> O(1) |
| Recomputing same values | `@lru_cache` or `@cache` | O(f(n)) -> O(1) cached |
| Building large lists | Generator with `yield` | O(n) space -> O(1) |
| Nested loops over same data | Single pass with hash map | O(n^2) -> O(n) |
| String concatenation in loop | `"".join(parts)` | O(n^2) -> O(n) |
| Sorting then searching | `heapq.nlargest()` for top-k | O(n log n) -> O(n log k) |

---

## Caching Decorators

```python
from functools import lru_cache, cache

@lru_cache(maxsize=128)  # LRU eviction, bounded memory
def expensive_with_limit(n: int) -> int: ...

@cache  # Unbounded, use for small domains
def expensive_unbounded(n: int) -> int: ...
```

**When to use:**

- Pure functions (same input = same output)
- Expensive computation (recursion, I/O, math)
- Repeated calls with same arguments

**When NOT to use:**

- Functions with side effects
- Large/unbounded input domains (memory leak)
- Mutable arguments (unhashable)

---

## Generator Patterns

```python
# BAD: Builds entire list in memory
def get_all(items):
    result = []
    for item in items:
        result.append(process(item))
    return result

# GOOD: Yields one at a time
def get_all(items):
    for item in items:
        yield process(item)
```

---

## Data Structure Selection

| Need | Use | Avoid |
|------|-----|-------|
| Fast membership test | `set` | `list` |
| Key-value lookup | `dict` | list of tuples |
| Ordered + fast lookup | `dict` (3.7+) | `OrderedDict` |
| Priority queue | `heapq` | sorted list |
| FIFO queue | `collections.deque` | `list.pop(0)` |
| Counting | `collections.Counter` | manual dict |

---

## Resources

- [Complexity Cheatsheet](references/complexity_cheatsheet.md) - Big-O for all Python operations
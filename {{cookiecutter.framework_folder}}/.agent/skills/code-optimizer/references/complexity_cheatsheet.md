# Big-O Complexity Cheatsheet

## Common Data Structure Operations

| Structure | Access | Search | Insert | Delete |
|-----------|--------|--------|--------|--------|
| Array | O(1) | O(n) | O(n) | O(n) |
| Linked List | O(n) | O(n) | O(1) | O(1) |
| Hash Table | - | O(1)* | O(1)* | O(1)* |
| BST (balanced) | O(log n) | O(log n) | O(log n) | O(log n) |
| Heap | - | O(n) | O(log n) | O(log n) |

*Average case, worst case O(n) for hash collisions

## Python-Specific Operations

### List

| Operation | Complexity |
|-----------|------------|
| `list[i]` | O(1) |
| `list.append(x)` | O(1) amortized |
| `list.insert(i, x)` | O(n) |
| `x in list` | O(n) |
| `list.sort()` | O(n log n) |

### Dict/Set

| Operation | Complexity |
|-----------|------------|
| `dict[key]` | O(1) |
| `key in dict` | O(1) |
| `dict.keys()` | O(1) (view) |
| `set.add(x)` | O(1) |
| `set1 & set2` | O(min(len(s1), len(s2))) |

### String

| Operation | Complexity |
|-----------|------------|
| `str[i]` | O(1) |
| `str + str` | O(n) |
| `"".join(list)` | O(n) total |
| `x in str` | O(n*m) |

## Sorting Algorithm Comparison

| Algorithm | Best | Average | Worst | Space |
|-----------|------|---------|-------|-------|
| Quicksort | O(n log n) | O(n log n) | O(n^2) | O(log n) |
| Mergesort | O(n log n) | O(n log n) | O(n log n) | O(n) |
| Timsort* | O(n) | O(n log n) | O(n log n) | O(n) |
| Heapsort | O(n log n) | O(n log n) | O(n log n) | O(1) |

*Python's built-in sort

## Quick Decision Guide

| If you need... | Use | Complexity |
|----------------|-----|------------|
| Fast lookup by key | `dict` | O(1) |
| Membership testing | `set` | O(1) |
| Ordered iteration | `list` | O(n) |
| Priority queue | `heapq` | O(log n) insert/pop |
| LRU cache | `functools.lru_cache` | O(1) cached |
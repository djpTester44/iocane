---
trigger: always_on
---

# NAVIGATION PROTOCOL: Read Surgically, Not Speculatively

**Core Principle:** Before reading any file, know *why* you are reading it and *what specific information* you need. Every read should be targeted: the right tool, the right scope, the right depth.

## Choosing a Search Approach

Different questions call for different tools. Match the tool to the question:

| Goal | Preferred Approach |
|------|--------------------|
| Find a file by name or pattern | Filename search (Glob) |
| Find files whose contents match a pattern | Content search (Grep / smart_search) |
| Locate a symbol's line number before reading | File outline or semantic search |
| Read a known target | Targeted read with line bounds or symbol lookup |

**Content search (Grep / smart_search):** Use when you know the pattern but not which file contains it — finding all call sites, imports, or usages of a symbol. `smart_search` is suited for repo-wide searches and returns filenames by default (most token-efficient); use its `-c` flag only when you need matching line content. Direct `Grep` is appropriate for simpler, well-scoped queries (a specific directory or file type) where it is more direct.

**Filename search (Glob):** Use when you know the name or partial name of the file. Do not use a content search tool to find files by name — it searches file *contents*, not filenames, and will scan the entire repo unnecessarily.

**Reading a file:** Prefer a targeted read (line range or symbol) once you have a candidate file and know the specific section you need. Read an entire file only when its full content is genuinely required (e.g., a short config file or a `.pyi` interface you need to reason about in full).

## Truncation Recovery

If `smart_search` output ends with `--- TRUNCATED ---`, results were capped. Recover with:

1. **Narrow the path**: Replace `.` with a specific directory (e.g., `src/models`).
2. **Narrow the pattern**: Use a more specific string (e.g., `def train` instead of `def`).
3. **Use content mode sparingly**: Only use `smart_search.sh -c "pattern" path` when you need line-level context. Default filenames-only mode is always cheaper.

## Failure Modes to Avoid

1. **The "Lazy Dump"**: Reading an entire large file when only one function or section was needed. Narrows nothing, wastes tokens.
2. **The "Grep Spam"**: Running repeated broad searches instead of refining the pattern or path after the first result.
3. **Ignoring Truncation**: Seeing `--- TRUNCATED ---` and not narrowing the search — the result set is incomplete and acting on it produces unreliable conclusions.
4. **The "Name Grep"**: Using a content search tool (e.g., `smart_search "README.md" .`) to find a file by name. This greps every file for the string "README.md" and will hang on large repos. Use a filename search tool instead.
5. **The "Narrow Sweep"**: During a config migration or variable rename, searching only for old variable *names* but not old *values/syntax*. Always search for both the old names AND the old values/paths, then run a second verification pass with the value-level pattern.

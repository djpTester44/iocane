# NAVIGATION PROTOCOL: Read Surgically, Not Speculatively

**Core Principle:** Before reading any file, know *why* you are reading it and *what specific information* you need. Every read should be targeted: the right tool, the right scope, the right depth.

## Choosing a Search Approach

Different questions call for different tools. Match the tool to the question:

| Goal | Preferred Approach |
|------|--------------------|
| Find a file by name or pattern | Filename search (Glob) |
| Find files whose contents match a pattern | Content search (Grep) |
| Understand a Python file's public surface | `extract_structure.py` — prefer over full file reads for structure questions |
| Locate a symbol's line number before reading | File outline or semantic search |
| Read a known target | Targeted read with line bounds or symbol lookup |
| Trace a Python symbol's definitions, usages, or importers | `symbol-tracer` skill — prefer over grep/smart_search for Python symbol lookups |

> In bash-only contexts (e.g. headless sub-agents), `.agent/scripts/smart_search.sh` is available as a token-capped grep wrapper.

**Filename search (Glob):** Use when you know the name or partial name of the file. Do not use a content search tool to find files by name — it searches file *contents*, not filenames, and will scan the entire repo unnecessarily.

**Reading a file:** Prefer a targeted read (line range or symbol) once you have a candidate file and know the specific section you need. Read an entire file only when its full content is genuinely required (e.g., a short config file or a `.pyi` interface you need to reason about in full).

## Failure Modes to Avoid

1. **The "Lazy Dump"**: Reading an entire large file when only one function or section was needed. Narrows nothing, wastes tokens.
2. **The "Grep Spam"**: Running repeated broad searches instead of refining the pattern or path after the first result.
3. **The "Name Grep"**: Using a content search tool to find a file by name — it scans file *contents*, not filenames. Use a filename search tool instead.
4. **The "Narrow Sweep"**: During a config migration or variable rename, search for both old names AND old values/syntax, then run a verification pass.
5. **The "Symbol Grep"**: Using grep or smart_search.sh to find Python symbol references. Use the `symbol-tracer` skill instead — it understands Python syntax and won't match comments, strings, or partial name collisions.

---
name: symbol-tracer
description: >-
  Traces definitions, imports, and usages of a Python symbol across the codebase
  using AST analysis. Use this skill to locate where a symbol is defined, find all
  call sites and importers, assess blast radius before refactoring, verify Protocol
  compliance, or understand cross-component wiring -- any time you need to answer
  "where is X?", "what uses X?", or "what implements X?" without reading entire
  files. Prefer this over grep for Python symbols because it understands syntax and
  won't produce false positives from comments or strings.
---

# Symbol Tracer

Trace definitions, imports, and usages of a Python symbol across the codebase using AST analysis.

## When to use

Reach for this skill any time the conversation involves:
- Locating where a class, function, or method is defined (before reading the file)
- Finding all call sites, importers, or references to a symbol
- Assessing blast radius before renaming, removing, or refactoring
- Verifying Protocol compliance: "is every Protocol method implemented somewhere?"
- Understanding cross-component wiring: "what imports this collaborator type?"
- Finding all classes that implement a given Protocol
- Answering "is this symbol dead code?" (zero usages = dead)

## Workflow

1. **Identify the symbol** from context. The user may say "rename `<SymbolName>`", "remove `<FunctionName>`", or "what implements `<ProtocolName>`" -- extract the symbol name. If ambiguous, ask.

2. **Determine the search root** -- default to `src/` if it exists, otherwise `.` (project root). Use `--include-tests` to also scan `tests/`.

3. **Choose the mode** based on the question:

   | Question | Flags |
   |----------|-------|
   | Where is `<Symbol>` defined/used? | `--symbol "<Symbol>"` (default mode) |
   | What imports `<Symbol>`? | `--symbol "<Symbol>" --imports-only` |
   | What implements `<Protocol>`? | `--symbol "<Protocol>" --find-implementors` |
   | Trace multiple symbols at once | `--symbol "<A>,<B>,<C>"` |
   | Quick triage (count only) | `--symbol "<Symbol>" --summary` |

4. **Run the script**:
   ```bash
   uv run python .claude/skills/symbol-tracer/scripts/symbol_tracer.py --symbol "<SymbolName>" --root <root>
   ```

5. **Parse the JSON output** and group results:
   - `"type": "definition"` -- where the symbol is declared
   - `"type": "import"` -- where the symbol is imported
   - `"type": "usage"` -- every call site and reference
   - `"type": "implementor"` -- classes that inherit from the symbol (only with `--find-implementors`)

6. **Produce a trace report**:
   - Count total results and group by file
   - Flag high-risk files (many usages, or usages in entrypoints / public interfaces)
   - List each result with file:line and the context snippet
   - Recommend next steps: "safe to rename -- all usages are internal" vs. "caution -- exported in interfaces/"

## Flags Reference

| Flag | Description |
|------|-------------|
| `--symbol "<name>"` | Symbol name to trace (required). Comma-separated for multiple. |
| `--root <path>` | Search root directory (default: `.`) |
| `--summary` | Prepend a one-line count summary to the output |
| `--imports-only` | Filter results to import statements only |
| `--include-tests` | Also scan `tests/` directory (even when `--root` is `src/`) |
| `--find-implementors` | Find classes that inherit from the symbol instead of tracing usages |
| `--format markdown` | Output as a markdown table instead of JSON |

## Limitations

- Python files only
- Static analysis: does not resolve `getattr`, dynamic dispatch, or string-based lookups
- Simple name matching -- does not track import aliases (`from x import Foo as Bar`: searching `Foo` finds the import, but usages of `Bar` will not be found)
- `--find-implementors` checks direct base class names only, not resolved imports of bases
- Skips `.git`, `__pycache__`, `.agent`, `venv`, `.venv`, `node_modules` -- symbols in `.agent/scripts/` are invisible to the tracer
- `--include-tests` resolves `tests/` relative to the working directory -- run from the project root

When these limitations matter, note them in the report.

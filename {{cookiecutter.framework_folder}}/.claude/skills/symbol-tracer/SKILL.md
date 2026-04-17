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
context: fork
---

# Symbol Tracer

Trace definitions, imports, and usages of a Python symbol across the codebase using AST analysis.

## Required Input

Caller MUST provide:
- `symbols`: one or more Python symbol names (comma-separated for multiple)
- `mode_flags`: which flags to pass (see Mode Selection table)

Caller MAY provide:
- `root`: search root directory (default: `src/` if it exists, otherwise `.`)
- `--include-tests`: also scan `tests/` directory

## Workflow

1. **Receive symbols and flags** from caller input. If the caller did not specify symbols explicitly, extract them from the surrounding task context. If ambiguous, ask.

2. **Determine the search root** -- default to `src/` if it exists, otherwise `.` (project root). Use `--include-tests` to also scan `tests/`.

3. **Choose the mode** based on the caller's intent:

   | Caller Intent | Flags |
   |---------------|-------|
   | Trace all references to a symbol | `--symbol "<A>"` (default mode) |
   | Detect cross-references between symbols | `--symbol "<A>,<B>" --imports-only` |
   | Assess blast radius | `--symbol "<A>" --summary` |
   | Find Protocol implementors | `--symbol "<Protocol>" --find-implementors` |
   | Detect namespace-level imports | `--imports-from-prefix "<module_prefix>"` |

4. **Run the script**:
   ```bash
   uv run python .claude/skills/symbol-tracer/scripts/symbol_tracer.py --symbol "<SymbolName>" --root <root>
   ```

## Output Format

### Raw output
The script emits JSON. Each entry has:
- `"type"`: one of `"definition"`, `"import"`, `"usage"`, `"implementor"`
- `"file"`: file path
- `"line"`: line number
- `"context"`: source line content

### Structured summary (what the caller receives)
Group results by symbol, then by type. Report:
- Total count per type
- Files with highest reference density
- Zero-result symbols (potential dead code or naming mismatch)

### What NOT to include
Do not add recommendations, next steps, or risk judgments ("safe to rename", "caution", "recommended fix"). The caller is a harness command that will make its own routing decisions based on the raw findings. Recommendations from the tracer are noise the caller must filter out -- they add tokens without adding signal the caller can act on directly.

## Flags Reference

| Flag | Description |
|------|-------------|
| `--symbol "<name>"` | Symbol name to trace. Comma-separated for multiple. Required unless `--imports-from-prefix` is given. |
| `--root <path>` | Search root directory (default: `.`) |
| `--summary` | Prepend a one-line count summary to the output |
| `--imports-only` | Filter results to import statements only |
| `--include-tests` | Also scan `tests/` directory (even when `--root` is `src/`) |
| `--find-implementors` | Find classes that inherit from the symbol instead of tracing usages |
| `--imports-from-prefix "<prefix>"` | Find any `from PREFIX[.sub] import ...` or `import PREFIX[.sub]` statements. Answers "does this file import anything from this module namespace?" without naming specific symbols. Empty JSON list means "no matches." When this flag is set, `--symbol` is optional and ignored. |
| `--format markdown` | Output as a markdown table instead of JSON |

## Prefix Mode Notes

`--imports-from-prefix` matches ModuleName exactly OR `ModuleName.sub[.deeper]`.
It does NOT substring-match, so `--imports-from-prefix src` will not match
`from source_utils import X`. Bare `import src` and `import src.domain` both
match. Relative imports (`from . import x`) do not match any prefix because
their `module` attribute is `None`.

Primary use case: deterministic post-dispatch validation that test files
import from the expected layer (e.g., connectivity tests must import from
`src.*` to exercise the target impl, not only from `interfaces.*` mocks).

## Limitations

- Python files only
- Static analysis: does not resolve `getattr`, dynamic dispatch, or string-based lookups
- Simple name matching -- does not track import aliases (`from x import Foo as Bar`: searching `Foo` finds the import, but usages of `Bar` will not be found)
- `--find-implementors` checks direct base class names only, not resolved imports of bases
- Skips `.git`, `__pycache__`, `.claude`, `venv`, `.venv`, `node_modules` -- symbols in those directories are invisible to the tracer
- `--include-tests` resolves `tests/` relative to the working directory -- run from the project root

When these limitations matter, note them in the report.

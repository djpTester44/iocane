---
name: impact-analyst-ast
description: Analyzes Python codebases using AST to find all definitions and usages of a specific symbol (class, function, variable) for predicting breaking changes. Use when refactoring, renaming symbols, or assessing the impact of code changes.
---

# Impact Analyst AST

Analyze Python codebases using AST to find symbol definitions and usages.

## Usage

Run the `find_usages.py` script:

```bash
python scripts/find_usages.py --symbol <SymbolName> --root <SearchRoot>
```

## Output

JSON array with file path, line number, type, and context for each occurrence:

```json
[
  {"file": "src/module.py", "line": 42, "type": "definition", "context": "class MyClass:"},
  {"file": "src/other.py", "line": 15, "type": "usage", "context": "obj = MyClass()"}
]
```

## Limitations

- Python files only (ignores non-Python files)
- Static analysis only (does not resolve runtime dynamic attributes like `getattr`)
- Simple name matching (does not track import aliases or full qualification)
- Skips `.git`, `__pycache__`, `venv`, `.venv` directories
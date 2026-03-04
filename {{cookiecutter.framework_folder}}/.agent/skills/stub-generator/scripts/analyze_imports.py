"""
Analyze Imports - Parses test files to identify missing imports for stub generation.
"""

import argparse
import ast
import importlib.util
import json
from pathlib import Path
from typing import Any


def find_project_root(start: Path) -> Path:
    """Find project root by looking for pyproject.toml or src directory."""
    current = start.resolve()
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            return current
        if (current / "src").is_dir():
            return current
        current = current.parent
    return start.resolve()


def module_to_path(module: str, project_root: Path) -> Path:
    """Convert module path to file path, respecting src-layout."""
    parts = module.split(".")

    # Try src-layout first
    src_path = project_root / "src" / "/".join(parts)
    if src_path.with_suffix(".py").parent.exists() or (project_root / "src").exists():
        return (project_root / "src" / "/".join(parts)).with_suffix(".py")

    # Fall back to flat layout
    return (project_root / "/".join(parts)).with_suffix(".py")


def is_module_available(module: str) -> bool:
    """Check if a module can be imported."""
    try:
        spec = importlib.util.find_spec(module)
        return spec is not None
    except (ModuleNotFoundError, ValueError):
        return False


def analyze_imports(test_file: Path) -> list[dict[str, Any]]:
    """Analyze a test file and return missing imports."""
    with open(test_file, encoding="utf-8") as f:
        content = f.read()

    tree = ast.parse(content, filename=str(test_file))
    project_root = find_project_root(test_file)

    missing: dict[str, dict[str, Any]] = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and not is_module_available(node.module):
                if node.module not in missing:
                    missing[node.module] = {
                        "module": node.module,
                        "names": [],
                        "suggested_path": str(module_to_path(node.module, project_root)),
                    }
                for alias in node.names:
                    name = alias.name
                    if name not in missing[node.module]["names"]:
                        missing[node.module]["names"].append(name)

        elif isinstance(node, ast.Import):
            for alias in node.names:
                module = alias.name
                if not is_module_available(module) and module not in missing:
                    missing[module] = {
                        "module": module,
                        "names": [],
                        "suggested_path": str(module_to_path(module, project_root)),
                    }

    return list(missing.values())


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze test file imports to find missing modules for stub generation."
    )
    parser.add_argument("test_file", help="Path to the test file to analyze.")
    parser.add_argument("--output", help="Output file (default: stdout)", default=None)

    args = parser.parse_args()
    test_file = Path(args.test_file)

    if not test_file.exists():
        print(json.dumps({"error": f"File not found: {test_file}"}))
        return

    results = analyze_imports(test_file)

    output = json.dumps(results, indent=2)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        print(output)


if __name__ == "__main__":
    main()

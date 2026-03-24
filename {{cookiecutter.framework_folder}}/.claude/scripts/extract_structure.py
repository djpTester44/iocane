import argparse
import ast
import contextlib
import json
import sys
from pathlib import Path


def extract_structure(file_path: str, as_json: bool = False):
    path = Path(file_path)
    if not path.exists():
        if as_json:
            print(json.dumps({"error": f"Path not found: {file_path}"}))
        else:
            print(f"Error: Path {file_path} not found.")
        return

    results = []
    if path.is_dir():
        for file in sorted(path.rglob("*.py")):
            results.append(get_file_structure(file))
    else:
        results.append(get_file_structure(path))

    if as_json:
        print(json.dumps(results if path.is_dir() else results[0], indent=2))
    else:
        for r in results:
            print_file_structure_from_data(r)


# ---------------------------------------------------------------------------
# Data extraction (shared by both output modes)
# ---------------------------------------------------------------------------

def get_file_structure(path: Path) -> dict:
    """Parse a Python file and return a structured dict of its skeleton."""
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except Exception as e:
        return {"file": path.as_posix(), "error": str(e), "classes": [], "functions": []}

    classes = []
    functions = []

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(_function_data(node))
        elif isinstance(node, ast.ClassDef):
            classes.append(_class_data(node))

    return {
        "file": path.as_posix(),
        "classes": classes,
        "functions": functions,
    }


def _function_data(node: ast.FunctionDef | ast.AsyncFunctionDef, indent: int = 0) -> dict:
    return {
        "name": node.name,
        "args": ast.unparse(node.args),
        "returns": ast.unparse(node.returns) if node.returns else None,
        "decorators": [ast.unparse(d) for d in node.decorator_list],
        "docstring": ast.get_docstring(node),
    }


def _class_data(node: ast.ClassDef) -> dict:
    bases = [ast.unparse(b) for b in node.bases]
    methods = []
    assignments = []

    for item in node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            methods.append(_function_data(item))
        elif isinstance(item, ast.Assign):
            with contextlib.suppress(Exception):
                assignments.append(ast.unparse(item))

    return {
        "name": node.name,
        "bases": bases,
        "docstring": ast.get_docstring(node),
        "methods": methods,
        "assignments": assignments,
    }


# ---------------------------------------------------------------------------
# Human-readable output (original behaviour)
# ---------------------------------------------------------------------------

def print_file_structure_from_data(data: dict):
    if "error" in data:
        print(f"Error parsing {data['file']}: {data['error']}")
        return

    print(f"# Skeleton for {data['file']}\n")

    for func in data["functions"]:
        _print_function_human(func)

    for cls in data["classes"]:
        _print_class_human(cls)


def _print_function_human(func: dict, indent: int = 0):
    prefix = "  " * indent
    decorators = "".join(f"{prefix}@{d}\n" for d in func["decorators"])
    returns = f" -> {func['returns']}" if func["returns"] else ""
    print(f"{decorators}{prefix}def {func['name']}({func['args']}){returns}:")
    if func["docstring"]:
        print(f'{prefix}    """{func["docstring"]}"""')
    print(f"{prefix}    ...\n")


def _print_class_human(cls: dict):
    bases = f"({', '.join(cls['bases'])})" if cls["bases"] else ""
    print(f"class {cls['name']}{bases}:")
    if cls["docstring"]:
        print(f'    """{cls["docstring"]}"""')
    for assignment in cls["assignments"]:
        print(f"    {assignment}")
    for method in cls["methods"]:
        _print_function_human(method, indent=1)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Extract structural skeleton from Python files or directories."
    )
    parser.add_argument("path", help="File or directory to analyse")
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output structured JSON instead of human-readable text",
    )
    args = parser.parse_args()
    extract_structure(args.path, as_json=args.json_output)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python extract_structure.py <file_or_directory> [--json]")
    else:
        main()

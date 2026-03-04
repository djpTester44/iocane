import ast
import contextlib
import sys
from pathlib import Path


def extract_structure(file_path: str):
    path = Path(file_path)
    if not path.exists():
        print(f"Error: Path {file_path} not found.")
        return

    if path.is_dir():
        for file in path.rglob("*.py"):
            print_file_structure(file)
    else:
        print_file_structure(path)


def print_file_structure(path: Path):
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except Exception as e:
        print(f"Error parsing {path}: {e}")
        return

    print(f"# Skeleton for {path.as_posix()}\n")

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            print_function(node)
        elif isinstance(node, ast.ClassDef):
            print_class(node)


def print_function(node, indent=0):
    prefix = "  " * indent
    # Reconstruct signature basics
    args = ast.unparse(node.args)
    returns = f" -> {ast.unparse(node.returns)}" if node.returns else ""
    decorator = (
        f"@{ast.unparse(node.decorator_list[0])}\n{prefix}"
        if node.decorator_list
        else ""
    )

    print(f"{prefix}{decorator}def {node.name}({args}){returns}:")
    doc = ast.get_docstring(node)
    if doc:
        print(f'{prefix}    """{doc}"""')
    print(f"{prefix}    ...\n")


def print_class(node):
    bases = f"({', '.join(ast.unparse(b) for b in node.bases)})" if node.bases else ""
    print(f"class {node.name}{bases}:")
    doc = ast.get_docstring(node)
    if doc:
        print(f'    """{doc}"""')

    for item in node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            print_function(item, indent=1)
        elif isinstance(item, ast.Assign):
            # Show class-level assignments if they look like constants/types
            with contextlib.suppress(Exception):
                print(f"    {ast.unparse(item)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python extract_structure.py <file_or_directory>")
    else:
        extract_structure(sys.argv[1])

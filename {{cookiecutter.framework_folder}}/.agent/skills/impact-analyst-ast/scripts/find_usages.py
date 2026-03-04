"""
Find Usages - Analyzes Python codebase using AST to find symbol definitions and usages.
"""

import argparse
import ast
import json
import os
from pathlib import Path
from typing import Any


class SymbolFinder(ast.NodeVisitor):
    """AST visitor that finds definitions and usages of a symbol."""

    def __init__(self, symbol: str, file_path: str, context_lines: list[str]):
        self.symbol = symbol
        self.file_path = file_path
        self.context_lines = context_lines
        self.results: list[dict[str, Any]] = []

    def _add_result(self, node: ast.AST, type_: str) -> None:
        lineno = getattr(node, "lineno", 0)
        context = ""
        if 0 < lineno <= len(self.context_lines):
            context = self.context_lines[lineno - 1].strip()

        self.results.append(
            {"file": self.file_path, "line": lineno, "type": type_, "context": context}
        )

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if node.name == self.symbol:
            self._add_result(node, "definition")
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if node.name == self.symbol:
            self._add_result(node, "definition")
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        if node.name == self.symbol:
            self._add_result(node, "definition")
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id == self.symbol:
            if isinstance(node.ctx, ast.Store):
                self._add_result(node, "definition")
            else:
                self._add_result(node, "usage")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr == self.symbol:
            self._add_result(node, "usage")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.names:
            for alias in node.names:
                if alias.name == self.symbol or alias.asname == self.symbol:
                    self._add_result(node, "usage")
        self.generic_visit(node)


def search_file(file_path: Path, symbol: str) -> list[dict[str, Any]]:
    """Search a single file for symbol occurrences."""
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
            lines = content.splitlines()

        tree = ast.parse(content, filename=str(file_path))
        finder = SymbolFinder(symbol, str(file_path), lines)
        finder.visit(tree)
        return finder.results
    except Exception:
        return []


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Find usages of a symbol in Python codebase using AST."
    )
    parser.add_argument(
        "--symbol", required=True, help="The symbol name to search for."
    )
    parser.add_argument("--root", default=".", help="Root directory to search.")

    args = parser.parse_args()

    root_path = Path(args.root)
    all_results: list[dict[str, Any]] = []

    skip_dirs = {".git", "__pycache__", ".agent", "venv", ".venv", "node_modules"}

    if root_path.is_file():
        if root_path.suffix == ".py":
            all_results.extend(search_file(root_path, args.symbol))
    else:
        for root, dirs, files in os.walk(root_path):
            dirs[:] = [d for d in dirs if d not in skip_dirs]

            for file in files:
                if file.endswith(".py"):
                    full_path = Path(root) / file
                    if full_path.resolve() == Path(__file__).resolve():
                        continue

                    results = search_file(full_path, args.symbol)
                    all_results.extend(results)

    print(json.dumps(all_results, indent=2))


if __name__ == "__main__":
    main()

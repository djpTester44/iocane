"""
Symbol Tracer - Analyzes Python codebase using AST to find symbol definitions,
imports, usages, and implementors.
"""

from __future__ import annotations

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
                    self._add_result(node, "import")
        self.generic_visit(node)


class ImplementorFinder(ast.NodeVisitor):
    """AST visitor that finds classes inheriting from a given symbol."""

    def __init__(self, symbol: str, file_path: str, context_lines: list[str]):
        self.symbol = symbol
        self.file_path = file_path
        self.context_lines = context_lines
        self.results: list[dict[str, Any]] = []

    def _add_result(self, node: ast.AST) -> None:
        lineno = getattr(node, "lineno", 0)
        context = ""
        if 0 < lineno <= len(self.context_lines):
            context = self.context_lines[lineno - 1].strip()

        self.results.append(
            {
                "file": self.file_path,
                "line": lineno,
                "type": "implementor",
                "context": context,
            }
        )

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        for base in node.bases:
            base_name = _extract_base_name(base)
            if base_name == self.symbol:
                self._add_result(node)
                break
        self.generic_visit(node)


def _extract_base_name(node: ast.expr) -> str | None:
    """Extract the terminal name from a base class expression."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def search_file(
    file_path: Path,
    symbol: str,
    *,
    find_implementors: bool = False,
) -> list[dict[str, Any]]:
    """Search a single file for symbol occurrences."""
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
            lines = content.splitlines()

        tree = ast.parse(content, filename=str(file_path))

        if find_implementors:
            finder = ImplementorFinder(symbol, str(file_path), lines)
        else:
            finder = SymbolFinder(symbol, str(file_path), lines)

        finder.visit(tree)
        return finder.results
    except Exception:
        return []


def _build_summary(
    symbol: str, results: list[dict[str, Any]], *, implementor_mode: bool
) -> str:
    """Build a one-line summary string for a symbol's results."""
    if implementor_mode:
        count = len(results)
        files = len({r["file"] for r in results})
        return f"{symbol}: {count} implementor(s) across {files} file(s)"

    defs = sum(1 for r in results if r["type"] == "definition")
    usages = sum(1 for r in results if r["type"] == "usage")
    imports = sum(1 for r in results if r["type"] == "import")
    files = len({r["file"] for r in results})
    return f"{symbol}: {defs} definition(s), {usages} usage(s), {imports} import(s) across {files} file(s)"


def _format_markdown(
    results: list[dict[str, Any]],
    *,
    summary: str | None = None,
    symbol_header: str | None = None,
) -> str:
    """Format results as a markdown table."""
    lines: list[str] = []
    if symbol_header:
        lines.append(f"## {symbol_header}")
        lines.append("")
    if summary:
        lines.append(f"**{summary}**")
        lines.append("")
    lines.append("| File | Line | Type | Context |")
    lines.append("|------|------|------|---------|")
    for r in results:
        ctx = r["context"].replace("|", "\\|")
        lines.append(f"| {r['file']} | {r['line']} | {r['type']} | {ctx} |")
    return "\n".join(lines)


def _collect_files(
    root_path: Path,
    *,
    include_tests: bool,
    skip_dirs: set[str],
) -> list[Path]:
    """Collect all .py files under root_path, optionally including tests/."""
    files: list[Path] = []
    script_path = Path(__file__).resolve()

    def _walk(base: Path) -> None:
        for dirpath, dirs, filenames in os.walk(base):
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            for fname in filenames:
                if fname.endswith(".py"):
                    full = Path(dirpath) / fname
                    if full.resolve() != script_path:
                        files.append(full)

    if root_path.is_file():
        if root_path.suffix == ".py":
            files.append(root_path)
    else:
        _walk(root_path)

    if include_tests:
        tests_dir = Path("tests")
        if tests_dir.is_dir() and not root_path.is_file():
            # Only walk tests/ if it's not already under root_path
            try:
                tests_dir.resolve().relative_to(root_path.resolve())
            except ValueError:
                _walk(tests_dir)

    return files


def _run_for_symbol(
    symbol: str,
    py_files: list[Path],
    *,
    find_implementors: bool,
    imports_only: bool,
) -> list[dict[str, Any]]:
    """Run the trace for a single symbol across all collected files."""
    all_results: list[dict[str, Any]] = []
    for f in py_files:
        results = search_file(f, symbol, find_implementors=find_implementors)
        all_results.extend(results)

    if imports_only and not find_implementors:
        all_results = [r for r in all_results if r["type"] == "import"]

    return all_results


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Trace definitions, imports, and usages of a Python symbol using AST."
    )
    parser.add_argument(
        "--symbol",
        required=True,
        help="Symbol name to trace. Comma-separated for multiple symbols.",
    )
    parser.add_argument("--root", default=".", help="Root directory to search.")
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Include a one-line count summary in the output.",
    )
    parser.add_argument(
        "--imports-only",
        action="store_true",
        help="Filter results to import statements only.",
    )
    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Also scan tests/ directory even when --root is src/.",
    )
    parser.add_argument(
        "--find-implementors",
        action="store_true",
        help="Find classes inheriting from the symbol instead of tracing usages.",
    )
    parser.add_argument(
        "--format",
        choices=["json", "markdown"],
        default="json",
        help="Output format (default: json).",
    )

    args = parser.parse_args()

    root_path = Path(args.root)
    skip_dirs = {".git", "__pycache__", ".claude", "venv", ".venv", "node_modules"}

    py_files = _collect_files(
        root_path,
        include_tests=args.include_tests,
        skip_dirs=skip_dirs,
    )

    symbols = [s.strip() for s in args.symbol.split(",")]
    is_multiple = len(symbols) > 1
    is_implementor = args.find_implementors

    if is_multiple:
        output: dict[str, Any] = {}
        md_parts: list[str] = []

        for sym in symbols:
            results = _run_for_symbol(
                sym,
                py_files,
                find_implementors=is_implementor,
                imports_only=args.imports_only,
            )
            if args.format == "markdown":
                summary_str = (
                    _build_summary(sym, results, implementor_mode=is_implementor)
                    if args.summary
                    else None
                )
                md_parts.append(
                    _format_markdown(
                        results,
                        summary=summary_str,
                        symbol_header=sym,
                    )
                )
            elif args.summary:
                output[sym] = {
                    "summary": _build_summary(
                        sym, results, implementor_mode=is_implementor
                    ),
                    "results": results,
                }
            else:
                output[sym] = results

        if args.format == "markdown":
            print("\n\n".join(md_parts))
        else:
            print(json.dumps(output, indent=2))
    else:
        sym = symbols[0]
        results = _run_for_symbol(
            sym,
            py_files,
            find_implementors=is_implementor,
            imports_only=args.imports_only,
        )

        if args.format == "markdown":
            summary_str = (
                _build_summary(sym, results, implementor_mode=is_implementor)
                if args.summary
                else None
            )
            print(_format_markdown(results, summary=summary_str))
        elif args.summary:
            print(
                json.dumps(
                    {
                        "summary": _build_summary(
                            sym, results, implementor_mode=is_implementor
                        ),
                        "results": results,
                    },
                    indent=2,
                )
            )
        else:
            print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()

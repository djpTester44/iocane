"""Generate structured context for the walkthrough template.

Extracts Protocol definitions, settings keys, layer mapping, and source
structure into a JSON blob that the /walkthrough-sync workflow consumes.

Usage:
    uv run python .agent/scripts/generate_walkthrough_context.py
    uv run python .agent/scripts/generate_walkthrough_context.py --output context.json
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

# Resolve project root (script lives in .agent/scripts/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def extract_protocols(interfaces_dir: Path) -> list[dict[str, str]]:
    """Extract Protocol class names and methods from .pyi stub files.

    Args:
        interfaces_dir: Path to the interfaces/ directory containing .pyi files.

    Returns:
        List of dicts with keys: name, file, methods.
    """
    protocols: list[dict[str, str]] = []

    if not interfaces_dir.exists():
        return protocols

    for pyi_file in sorted(interfaces_dir.glob("*.pyi")):
        try:
            source = pyi_file.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError):
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue

            # Check if it inherits from Protocol
            bases = [ast.unparse(b) for b in node.bases]
            is_protocol = any("Protocol" in b for b in bases)

            methods = [
                item.name
                for item in node.body
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                and not item.name.startswith("_")
            ]

            protocols.append({
                "name": node.name,
                "file": pyi_file.name,
                "is_protocol": is_protocol,
                "methods": ", ".join(methods) if methods else "(no public methods)",
            })

    return protocols


def extract_settings_keys(settings_path: Path) -> dict[str, str]:
    """Extract top-level keys and sample values from settings.yaml.

    Args:
        settings_path: Path to settings.yaml.

    Returns:
        Dict of dotted key paths to their string values.
    """
    result: dict[str, str] = {}

    if not settings_path.exists():
        return result

    try:
        # Use a simple YAML parser (avoid heavy dependency)
        # Read lines and extract key-value pairs at depth <= 2
        lines = settings_path.read_text(encoding="utf-8").splitlines()
        section = ""
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if not line.startswith(" ") and ":" in stripped:
                section = stripped.split(":")[0].strip()
                value = stripped.split(":", 1)[1].strip()
                if value and not value.startswith("#"):
                    result[section] = value
            elif line.startswith("  ") and ":" in stripped and section:
                key = stripped.split(":")[0].strip()
                value = stripped.split(":", 1)[1].strip()
                if value and not value.startswith("#"):
                    result[f"{section}.{key}"] = value.strip('"').strip("'")
    except Exception:
        pass

    return result


def extract_layers(pyproject_path: Path) -> list[str]:
    """Extract architectural layers from import-linter config in pyproject.toml.

    Args:
        pyproject_path: Path to pyproject.toml.

    Returns:
        Ordered list of layer names (highest to lowest).
    """
    if not pyproject_path.exists():
        return []

    try:
        content = pyproject_path.read_text(encoding="utf-8")
        # Find the layers line in [tool.importlinter] section
        in_section = False
        for line in content.splitlines():
            if "[tool.importlinter" in line:
                in_section = True
            if in_section and "layers" in line and "=" in line:
                # Parse the layers list
                raw = line.split("=", 1)[1].strip()
                # Handle TOML array format
                if raw.startswith("["):
                    raw = raw.strip("[]")
                    layers = [
                        s.strip().strip('"').strip("'")
                        for s in raw.split(",")
                        if s.strip()
                    ]
                    return layers
    except Exception:
        pass

    return []


def extract_src_structure(src_dir: Path) -> dict[str, list[str]]:
    """Extract class and function names from all .py files in src/.

    Args:
        src_dir: Path to the src/ directory.

    Returns:
        Dict mapping relative file paths to lists of "class Name" or "def name" strings.
    """
    structure: dict[str, list[str]] = {}

    if not src_dir.exists():
        return structure

    for py_file in sorted(src_dir.rglob("*.py")):
        if py_file.name == "__init__.py":
            continue
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError):
            continue

        items: list[str] = []
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                items.append(f"class {node.name}")
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                items.append(f"def {node.name}")

        if items:
            rel_path = py_file.relative_to(PROJECT_ROOT).as_posix()
            structure[rel_path] = items

    return structure


def main() -> None:
    """Generate walkthrough context JSON."""
    output_path = None
    if len(sys.argv) > 2 and sys.argv[1] == "--output":
        output_path = Path(sys.argv[2])

    context = {
        "project_root": PROJECT_ROOT.as_posix(),
        "protocols": extract_protocols(PROJECT_ROOT / "interfaces"),
        "settings_keys": extract_settings_keys(PROJECT_ROOT / "settings.yaml"),
        "layers": extract_layers(PROJECT_ROOT / "pyproject.toml"),
        "src_structure": extract_src_structure(PROJECT_ROOT / "src"),
    }

    output = json.dumps(context, indent=2)

    if output_path:
        output_path.write_text(output, encoding="utf-8")
        print(f"Context written to {output_path}")
    else:
        print(output)


if __name__ == "__main__":
    main()

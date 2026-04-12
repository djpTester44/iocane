#!/usr/bin/env python3
"""sync_dir_claude.py

Regenerates directory-level CLAUDE.md files in src/ subdirectories from
structured data sources. These are navigation artifacts -- always overwritten,
never hand-edited.

Data sources:
  - plans/component-contracts.yaml  (CRC responsibilities + Must NOT)
  - plans/seams.yaml                (layer assignments)
  - pyproject.toml                  (import-linter layer contracts)
  - src/[dir]/*.py on disk          (Key files listing)

Exit codes:
  0 -- success
  1 -- missing required inputs (component-contracts.yaml)
  2 -- 20-line limit exceeded for one or more directories

Usage:
    uv run python .claude/scripts/sync_dir_claude.py                # all directories
    uv run python .claude/scripts/sync_dir_claude.py --dir src/core # single directory
    uv run python .claude/scripts/sync_dir_claude.py --dry-run      # preview only
"""

import argparse
import logging
import re
import sys
import tomllib
from pathlib import Path

from pydantic import ValidationError

from contract_parser import load_contracts
from schemas import ComponentContract, SeamComponent
from seam_parser import load_seams

logger = logging.getLogger(__name__)

MAX_LINES = 20


def load_pyproject_contracts(path: Path) -> list[dict[str, object]]:
    """Load import-linter contracts from pyproject.toml."""
    if not path.exists():
        return []
    with path.open("rb") as f:
        data = tomllib.load(f)
    tool = data.get("tool", {})
    il = tool.get("importlinter", {})
    return il.get("contracts", [])


# ---------------------------------------------------------------------------
# Directory -> component mapping
# ---------------------------------------------------------------------------


def build_dir_component_map(
    components: dict[str, ComponentContract],
) -> dict[str, list[str]]:
    """Map src/ subdirectory paths to component names.

    Returns {dir_path: [component_names]}.
    """
    dir_map: dict[str, list[str]] = {}
    for comp_name, comp_data in components.items():
        if not comp_data.file.startswith("src/"):
            continue
        # Directory is the parent of the implementation file
        dir_path = Path(comp_data.file).parent.as_posix()
        if dir_path not in dir_map:
            dir_map[dir_path] = []
        dir_map[dir_path].append(comp_name)
    return dir_map


# ---------------------------------------------------------------------------
# Field extraction
# ---------------------------------------------------------------------------


def get_layer(
    comp_names: list[str],
    seam_components: list[SeamComponent],
    il_contracts: list[dict[str, object]],
    dir_path: str,
) -> str:
    """Derive layer label for a directory's components.

    Priority: seams.yaml layer field, then import-linter contracts.
    """
    layer_map = {1: "1-Foundation", 2: "2-Utility", 3: "3-Domain"}

    # Check seams.yaml first
    for seam in seam_components:
        if seam.component in comp_names:
            if seam.layer in layer_map:
                return layer_map[seam.layer]

    # Fallback: infer from import-linter layer contract ordering
    # Match directory name against package path segments (e.g. "domain"
    # matches "route_planner.domain"), not component class names.
    dir_name = Path(dir_path).name.lower()
    for contract in il_contracts:
        if contract.get("type") != "layers":
            continue
        layers = contract.get("layers", [])
        # layers are ordered top-to-bottom (entrypoint first)
        for idx, layer_pkg in enumerate(layers):
            pkg_segments = layer_pkg.lower().split(".")
            if dir_name in pkg_segments:
                # Map position to layer number (reversed: last = foundation)
                total = len(layers)
                layer_num = total - idx
                if layer_num in layer_map:
                    return layer_map[layer_num]

    return "[unknown]"


def get_owns(
    comp_names: list[str],
    components: dict[str, ComponentContract],
) -> str:
    """Build Owns line from CRC responsibilities."""
    parts: list[str] = []
    for name in sorted(comp_names):
        comp = components.get(name)
        if comp and comp.responsibilities:
            parts.append(comp.responsibilities[0])
    if not parts:
        return "[no CRC data]"
    return "; ".join(parts)


def get_public_via(
    comp_names: list[str],
    components: dict[str, ComponentContract],
    interfaces_dir: Path,
) -> list[str]:
    """Build Public via lines from component-contracts.yaml.

    Cross-references with interfaces/*.pyi existence.
    """
    lines: list[str] = []
    for name in sorted(comp_names):
        comp = components.get(name)
        if comp is None:
            continue
        # Skip composition roots -- they have no Protocol
        if comp.composition_root:
            continue
        # Convention: protocol file is interfaces/{name}_protocol.pyi
        # or interfaces/{snake_case_name}.pyi
        # Search for any .pyi that references this component
        protocol_file = _find_protocol_file(name, interfaces_dir)
        if protocol_file:
            rel_path = protocol_file.relative_to(interfaces_dir.parent)
            lines.append(f"`{rel_path}` -- {name}")
    return lines


def _find_protocol_file(comp_name: str, interfaces_dir: Path) -> Path | None:
    """Find the .pyi file for a component by scanning filenames."""
    if not interfaces_dir.exists():
        return None
    snake = _to_snake_case(comp_name)
    # Try exact match first
    for pattern in [f"{snake}.pyi", f"{snake}_protocol.pyi"]:
        candidate = interfaces_dir / pattern
        if candidate.exists():
            return candidate
    # Scan all .pyi files for one containing a class matching the component
    for pyi in sorted(interfaces_dir.glob("*.pyi")):
        try:
            text = pyi.read_text(encoding="utf-8")
            if f"class {comp_name}" in text or f"class {comp_name}Protocol" in text:
                return pyi
        except OSError:
            continue
    return None


def _to_snake_case(name: str) -> str:
    """Convert CamelCase to snake_case."""
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def get_must_not(
    comp_names: list[str],
    components: dict[str, ComponentContract],
    il_contracts: list[dict[str, object]],
    dir_path: str,
) -> list[str]:
    """Build Must NOT lines from component contracts + import-linter."""
    lines: list[str] = []

    # From component contracts
    for name in sorted(comp_names):
        comp = components.get(name)
        if comp:
            for item in comp.must_not:
                if item not in lines:
                    lines.append(item)

    # From import-linter layer hierarchy
    for contract in il_contracts:
        if contract.get("type") != "layers":
            continue
        layers = contract.get("layers", [])
        # Find which layer this directory belongs to
        dir_pkg = _dir_to_package(dir_path)
        dir_idx = _find_layer_index(dir_pkg, layers)
        if dir_idx is None:
            continue
        # Must not import from higher layers (lower index = higher layer)
        for higher_idx in range(dir_idx):
            constraint = f"Import from `{layers[higher_idx]}` (layer violation)"
            if constraint not in lines:
                lines.append(constraint)

    return lines


def _dir_to_package(dir_path: str) -> str:
    """Convert src/foo/bar to foo.bar for package matching."""
    parts = Path(dir_path).parts
    if parts and parts[0] == "src":
        parts = parts[1:]
    return ".".join(parts)


def _find_layer_index(pkg: str, layers: list[str]) -> int | None:
    """Find which layer a package belongs to."""
    for idx, layer in enumerate(layers):
        if pkg == layer or pkg.startswith(f"{layer}."):
            return idx
    return None


def get_key_files(
    dir_path: str,
    comp_names: list[str],
    components: dict[str, ComponentContract],
    project_root: Path,
) -> list[str]:
    """Build Key files lines from disk state + CRC descriptions.

    Registered components get CRC first-responsibility description.
    Unregistered .py files get [implementation].
    Excludes __init__.py.
    """
    full_dir = project_root / dir_path
    if not full_dir.exists():
        return []

    # Build component -> filename mapping
    comp_files: dict[str, str] = {}
    for name in comp_names:
        comp = components.get(name)
        if comp is None:
            continue
        comp_files[Path(comp.file).name] = name

    lines: list[str] = []
    for py_file in sorted(full_dir.glob("*.py")):
        if py_file.name == "__init__.py":
            continue
        fname = py_file.name
        if fname in comp_files:
            comp_name = comp_files[fname]
            comp = components.get(comp_name)
            responsibilities = comp.responsibilities if comp else []
            desc = responsibilities[0] if responsibilities else comp_name
            lines.append(f"`{fname}` -- {desc}")
        else:
            lines.append(f"`{fname}` -- [implementation]")

    return lines


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------


def render_claude_md(
    dir_name: str,
    layer: str,
    owns: str,
    public_via: list[str],
    must_not: list[str],
    key_files: list[str],
) -> str:
    """Render a directory CLAUDE.md from extracted fields."""
    lines: list[str] = []
    lines.append(f"# {dir_name}/")
    lines.append("")
    lines.append(f"**Layer:** {layer}")
    lines.append(f"**Owns:** {owns}")

    if public_via:
        lines.append("")
        lines.append("**Public via:**")
        for item in public_via:
            lines.append(f"- {item}")

    if must_not:
        lines.append("")
        lines.append("**Must NOT:**")
        for item in must_not:
            lines.append(f"- {item}")

    if key_files:
        lines.append("")
        lines.append("**Key files:**")
        for item in key_files:
            lines.append(f"- {item}")

    lines.append("")  # trailing newline
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------


def find_project_root() -> Path:
    """Walk up from cwd to find the project root (contains pyproject.toml or plans/)."""
    current = Path.cwd()
    for parent in [current, *current.parents]:
        if (parent / "plans").is_dir() or (parent / "pyproject.toml").is_file():
            return parent
    return current


def sync_directory(
    dir_path: str,
    comp_names: list[str],
    components: dict[str, ComponentContract],
    seam_components: list[SeamComponent],
    il_contracts: list[dict[str, object]],
    project_root: Path,
    dry_run: bool,
) -> int:
    """Generate CLAUDE.md for a single directory.

    Returns 0 on success, 2 if line limit exceeded.
    """
    dir_name = Path(dir_path).name
    interfaces_dir = project_root / "interfaces"

    layer = get_layer(comp_names, seam_components, il_contracts, dir_path)
    owns = get_owns(comp_names, components)
    public_via = get_public_via(comp_names, components, interfaces_dir)
    must_not = get_must_not(comp_names, components, il_contracts, dir_path)
    key_files = get_key_files(
        dir_path, comp_names, components, project_root,
    )

    content = render_claude_md(dir_name, layer, owns, public_via, must_not, key_files)
    line_count = len(content.strip().splitlines())

    exit_code = 0
    if line_count > MAX_LINES:
        logger.warning(
            "%s: %d lines exceeds %d-line limit (DESIGN finding)",
            dir_path, line_count, MAX_LINES,
        )
        exit_code = 2

    target = project_root / dir_path / "CLAUDE.md"

    if dry_run:
        sys.stdout.write(f"--- {target} ({line_count} lines) ---\n")
        sys.stdout.write(content)
        sys.stdout.write("\n")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        logger.info("wrote %s (%d lines)", target, line_count)

    return exit_code


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="Regenerate directory-level CLAUDE.md navigation artifacts.",
    )
    parser.add_argument(
        "--dir",
        help="Regenerate a single directory only (e.g. src/core).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be written without writing.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    project_root = find_project_root()

    # Load data sources
    contracts_path = str(project_root / "plans" / "component-contracts.yaml")
    try:
        contracts = load_contracts(contracts_path)
    except ValidationError:
        logger.error(
            "plans/component-contracts.yaml failed validation -- "
            "run /io-architect first",
        )
        return 1
    if not contracts.components:
        logger.error(
            "plans/component-contracts.yaml not found or empty -- "
            "run /io-architect first",
        )
        return 1

    seams_path = str(project_root / "plans" / "seams.yaml")
    try:
        seams = load_seams(seams_path)
    except (ValidationError, FileNotFoundError):
        logger.warning("plans/seams.yaml not found or invalid -- layer data may be incomplete")
        seams = None
    seam_components = seams.components if seams else []
    if not seam_components:
        logger.warning("plans/seams.yaml empty -- layer data may be incomplete")

    pyproject_path = project_root / "pyproject.toml"
    il_contracts = load_pyproject_contracts(pyproject_path)

    if all(
        not c.responsibilities
        for c in contracts.components.values()
    ):
        logger.warning(
            "No responsibilities in component-contracts.yaml -- "
            "run /io-architect to populate"
        )

    # Build directory -> components map
    dir_map = build_dir_component_map(contracts.components)

    if not dir_map:
        logger.error("no src/ directories found in component-contracts.yaml")
        return 1

    # Filter to single directory if requested
    if args.dir:
        target_dir = args.dir.rstrip("/").rstrip("\\")
        if target_dir not in dir_map:
            logger.error(
                "%s has no registered components in component-contracts.yaml",
                target_dir,
            )
            return 1
        dir_map = {target_dir: dir_map[target_dir]}

    # Process each directory
    worst_exit = 0
    count = 0
    for dir_path, comp_names in sorted(dir_map.items()):
        result = sync_directory(
            dir_path,
            comp_names,
            contracts.components,
            seam_components,
            il_contracts,
            project_root,
            args.dry_run,
        )
        worst_exit = max(worst_exit, result)
        count += 1

    action = "would write" if args.dry_run else "wrote"
    logger.info("%s %d directory CLAUDE.md file(s)", action, count)
    return worst_exit


if __name__ == "__main__":
    sys.exit(main())

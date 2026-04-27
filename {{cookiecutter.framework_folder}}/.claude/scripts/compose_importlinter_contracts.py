#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "tomlkit>=0.13",
#     "pyyaml",
#     "pydantic>=2",
# ]
# ///
"""Compose pyproject.toml [[tool.importlinter.contracts]] from canonical YAMLs.

Reads plans/component-contracts.yaml (file: paths via contract_parser) and
plans/seams.yaml (layer: per component via seam_parser). Strips any existing
[[tool.importlinter.contracts]] blocks from pyproject.toml and regenerates
from the canonical YAMLs (layer hierarchy + connector independence).

Idempotent from the second run forward. Non-importlinter pyproject sections
([build-system], [project], [tool.ruff], etc.) are preserved via tomlkit's
round-trip parser.

Brownfield bootstrap: --bootstrap copies pyproject.toml from
.claude/templates/pyproject.toml when the file does not exist. The
"pyproject.toml exists but lacks [tool.importlinter] section" case is
handled uniformly via strip-zero-or-more + always-append; no flag needed.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import tomlkit

# Add .claude/scripts to path so parser imports resolve in consumer context.
sys.path.insert(0, str(Path(__file__).parent))

from contract_parser import load_contracts  # noqa: E402
from seam_parser import load_seams  # noqa: E402


def _layer_hierarchy_contract(
    components_by_layer: dict[int, list[str]],
) -> dict[str, object]:
    """Build the layer-hierarchy import-linter contract.

    Layers ordered top (Entrypoint=4) down (Foundation=1). Each layer
    contains the package paths derived from component file: paths.
    """
    layers_top_down = sorted(components_by_layer.keys(), reverse=True)
    return {
        "name": "Layered architecture",
        "type": "layers",
        "layers": [
            " | ".join(sorted(set(components_by_layer[layer])))
            for layer in layers_top_down
            if components_by_layer[layer]
        ],
    }


def _independence_contracts(
    peer_packages: list[list[str]],
) -> list[dict[str, object]]:
    """Build independence contracts for peer packages at the same layer."""
    return [
        {
            "name": f"Independence: {' / '.join(group)}",
            "type": "independence",
            "modules": sorted(group),
        }
        for group in peer_packages
    ]


def _derive_contracts(
    contracts_path: Path,
    seams_path: Path,
) -> list[dict[str, object]]:
    """Derive importlinter contract dicts from canonical YAMLs."""
    contracts = load_contracts(str(contracts_path))
    seams = load_seams(str(seams_path))

    # Map component name -> package path (derived from file:)
    pkg_paths: dict[str, str] = {}
    for comp_name, contract in contracts.components.items():
        if not contract.file:
            continue
        parts = Path(contract.file).parts
        if len(parts) < 2 or parts[0] != "src":
            continue
        pkg_paths[comp_name] = parts[1]

    # Group component packages by layer (from seams.yaml).
    # SeamsFile.components is a list[SeamComponent]; SeamComponent.component
    # carries the name. ComponentContractsFile.components is a dict keyed by
    # name -- the asymmetry is schema-historical.
    components_by_layer: dict[int, list[str]] = {}
    for seam in seams.components:
        if seam.component not in pkg_paths:
            continue
        components_by_layer.setdefault(seam.layer, []).append(
            pkg_paths[seam.component],
        )

    # Detect peer-package independence: 2+ distinct packages at same layer
    peer_packages: list[list[str]] = []
    for pkgs in components_by_layer.values():
        unique = sorted(set(pkgs))
        if len(unique) >= 2:
            peer_packages.append(unique)

    contracts_list: list[dict[str, object]] = [
        _layer_hierarchy_contract(components_by_layer),
    ]
    contracts_list.extend(_independence_contracts(peer_packages))
    return contracts_list


def _strip_and_regenerate(
    pyproject_path: Path,
    new_contracts: list[dict[str, object]],
) -> None:
    """Strip existing importlinter contracts from pyproject; append new ones.

    Uses tomlkit to preserve comments + ordering of non-importlinter
    sections. Strip-zero-or-more + always-append handles all three
    pre-existing states uniformly:
      (a) pyproject.toml exists with [tool.importlinter] populated
      (b) pyproject.toml exists without [tool.importlinter]
      (c) pyproject.toml just bootstrapped (no [tool] table yet)

    Idempotency requires dump-and-reparse after the importlinter
    deletion: tomlkit's preservation machinery leaves trailing trivia
    (blank lines) attached to deleted AOT blocks, which accumulates
    across runs. Dumping after deletion and reparsing normalizes the
    trivia so subsequent runs against the normalized output produce
    byte-identical results.
    """
    text = pyproject_path.read_text(encoding="utf-8")
    doc = tomlkit.parse(text)

    # Capture any non-contracts importlinter keys (user-added, e.g.
    # root_packages) so we can restore them after the rebuild.
    preserved_keys: dict[str, object] = {}
    tool = doc.get("tool")
    if tool is not None:
        existing_importlinter = tool.get("importlinter")
        if existing_importlinter is not None:
            for key, value in existing_importlinter.items():
                if key != "contracts":
                    preserved_keys[key] = value
            del tool["importlinter"]

    # Normalize trivia by dump-and-reparse after deletion. Without
    # this, tomlkit leaves trailing blank lines from the deleted AOT
    # which accumulate on each subsequent run.
    doc = tomlkit.parse(tomlkit.dumps(doc))

    # Build fresh [tool.importlinter] section with preserved keys + new
    # contracts AOT.
    tool = doc.get("tool")
    if tool is None:
        tool = tomlkit.table()
        doc["tool"] = tool

    importlinter = tomlkit.table()
    for key, value in preserved_keys.items():
        importlinter[key] = value

    contracts_array = tomlkit.aot()
    for contract in new_contracts:
        block = tomlkit.table()
        for key, value in contract.items():
            block[key] = value
        contracts_array.append(block)
    importlinter["contracts"] = contracts_array

    tool["importlinter"] = importlinter

    pyproject_path.write_text(tomlkit.dumps(doc), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="compose_importlinter_contracts",
        description=(
            "Regenerate pyproject.toml [[tool.importlinter.contracts]] from "
            "canonical YAMLs."
        ),
    )
    parser.add_argument(
        "--contracts",
        type=Path,
        default=Path("plans/component-contracts.yaml"),
    )
    parser.add_argument(
        "--seams",
        type=Path,
        default=Path("plans/seams.yaml"),
    )
    parser.add_argument(
        "--pyproject",
        type=Path,
        default=Path("pyproject.toml"),
    )
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help=(
            "Copy pyproject.toml from .claude/templates/pyproject.toml if "
            "missing."
        ),
    )
    parser.add_argument(
        "--template",
        type=Path,
        default=Path(".claude/templates/pyproject.toml"),
    )
    args = parser.parse_args()

    if not args.pyproject.exists():
        if args.bootstrap:
            if not args.template.exists():
                sys.stderr.write(
                    f"compose_importlinter_contracts: --bootstrap requested "
                    f"but template missing at {args.template}\n",
                )
                return 1
            shutil.copy(args.template, args.pyproject)
        else:
            sys.stderr.write(
                f"compose_importlinter_contracts: {args.pyproject} not found; "
                f"pass --bootstrap to create from template\n",
            )
            return 1

    new_contracts = _derive_contracts(args.contracts, args.seams)
    _strip_and_regenerate(args.pyproject, new_contracts)
    return 0


if __name__ == "__main__":
    sys.exit(main())

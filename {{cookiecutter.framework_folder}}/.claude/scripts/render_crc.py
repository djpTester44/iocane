"""render_crc.py

Deterministic renderer: reads component-contracts.yaml and seams.yaml,
writes the CRC Cards section of project-spec.md.

The YAML files are the source of truth; project-spec.md is a derived
artifact. This script replaces the CRC Cards section in-place,
preserving all other sections.

Exit codes:
  0 -- success
  1 -- missing contracts

Usage:
    uv run python .claude/scripts/render_crc.py
    uv run python .claude/scripts/render_crc.py --dry-run
    uv run python .claude/scripts/render_crc.py --spec plans/project-spec.md
"""

import argparse
import logging
import re
import sys
from pathlib import Path

from contract_parser import load_contracts
from schemas import ComponentContractsFile, SeamsFile
from seam_parser import load_seams

logger = logging.getLogger(__name__)

_LAYER_NAMES: dict[int, str] = {
    1: "foundation",
    2: "utility",
    3: "domain",
    4: "entrypoint",
}

_CRC_HEADING_RE = re.compile(r"^##\s+(?:\d+\.\s+)?CRC Cards")
_NEXT_H2_RE = re.compile(r"^## ")
_PROTOCOL_SIG_RE = re.compile(r"^##\s+(?:\d+\.\s+)?Protocol Signatures")


# ------------------------------------------------------------------
# Rendering
# ------------------------------------------------------------------


def render_crc_section(
    contracts: ComponentContractsFile,
    seams: SeamsFile | None,
) -> str:
    """Render CRC cards section from structured data.

    Returns markdown string for the CRC Cards section of project-spec.md.
    """
    layer_lookup: dict[str, int] = {}
    if seams is not None:
        for sc in seams.components:
            layer_lookup[sc.component] = sc.layer

    blocks: list[str] = ["## CRC Cards\n"]

    for name in sorted(contracts.components):
        contract = contracts.components[name]
        layer_int = layer_lookup.get(name)
        layer_label = _LAYER_NAMES.get(layer_int, "unassigned") if layer_int else "unassigned"

        lines: list[str] = [
            f"### {name}",
            f"**Layer:** {layer_label}",
            f"**File:** `{contract.file}`",
            "",
            "**Responsibilities:**",
        ]
        for resp in contract.responsibilities:
            lines.append(f"- {resp}")

        lines.append("")
        lines.append("**Collaborators:**")
        if contract.collaborators:
            for collab in contract.collaborators:
                lines.append(f"- {collab}")
        else:
            lines.append("- None")

        if contract.must_not:
            lines.append("")
            lines.append("**Must NOT:**")
            for item in contract.must_not:
                lines.append(f"- {item}")

        lines.append("")
        blocks.append("\n".join(lines))

    return "\n".join(blocks)


# ------------------------------------------------------------------
# Spec file update
# ------------------------------------------------------------------


def update_project_spec(
    spec_path: str,
    contracts_path: str,
    seams_path: str,
) -> None:
    """Replace the CRC Cards section in project-spec.md with rendered output.

    Preserves all other sections of project-spec.md. Only the CRC Cards
    section (between its heading and the next ## heading) is replaced.
    """
    contracts = load_contracts(contracts_path)
    if not contracts.components:
        logger.error("No components in %s", contracts_path)
        return

    try:
        seams: SeamsFile | None = load_seams(seams_path)
    except Exception:
        logger.warning(
            "Could not load %s -- layers will be 'unassigned'",
            seams_path,
        )
        seams = None

    rendered = render_crc_section(contracts, seams)

    spec = Path(spec_path)
    if not spec.exists():
        spec.write_text(rendered + "\n", encoding="utf-8")
        logger.info("Created %s with CRC section", spec_path)
        return

    text = spec.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    # Find CRC section boundaries
    crc_start: int | None = None
    crc_end: int | None = None
    for i, line in enumerate(lines):
        if crc_start is None:
            if _CRC_HEADING_RE.match(line):
                crc_start = i
        elif _NEXT_H2_RE.match(line):
            crc_end = i
            break

    if crc_start is not None:
        # Replace existing section
        if crc_end is None:
            crc_end = len(lines)
        new_lines = lines[:crc_start] + [rendered + "\n"] + lines[crc_end:]
    else:
        # No existing CRC section -- insert before Protocol Signatures
        insert_at: int | None = None
        for i, line in enumerate(lines):
            if _PROTOCOL_SIG_RE.match(line):
                insert_at = i
                break

        if insert_at is not None:
            new_lines = (
                lines[:insert_at] + [rendered + "\n\n"] + lines[insert_at:]
            )
        else:
            # Append at end
            if text and not text.endswith("\n"):
                new_lines = lines + ["\n", rendered + "\n"]
            else:
                new_lines = lines + [rendered + "\n"]

    spec.write_text("".join(new_lines), encoding="utf-8")
    logger.info("Updated CRC section in %s", spec_path)


# ------------------------------------------------------------------
# Project root discovery
# ------------------------------------------------------------------


def find_project_root() -> Path:
    """Walk up from cwd to find project root (contains plans/ or pyproject.toml)."""
    current = Path.cwd()
    for parent in [current, *current.parents]:
        if (parent / "plans").is_dir() or (parent / "pyproject.toml").is_file():
            return parent
    return current


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Entry point for render_crc CLI."""
    parser = argparse.ArgumentParser(
        description="Render CRC Cards section from YAML sources.",
    )
    parser.add_argument(
        "--spec",
        default="plans/project-spec.md",
        help="Path to project-spec.md (default: plans/project-spec.md).",
    )
    parser.add_argument(
        "--contracts",
        default="plans/component-contracts.yaml",
        help="Path to component-contracts.yaml.",
    )
    parser.add_argument(
        "--seams",
        default="plans/seams.yaml",
        help="Path to seams.yaml.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print rendered section to stdout instead of writing.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    root = find_project_root()

    contracts_path = str(root / args.contracts)
    seams_path = str(root / args.seams)
    spec_path = str(root / args.spec)

    contracts = load_contracts(contracts_path)
    if not contracts.components:
        logger.error(
            "No components in %s -- nothing to render",
            contracts_path,
        )
        return 1

    if args.dry_run:
        try:
            seams: SeamsFile | None = load_seams(seams_path)
        except Exception:
            logger.warning(
                "Could not load %s -- layers will be 'unassigned'",
                seams_path,
            )
            seams = None
        rendered = render_crc_section(contracts, seams)
        sys.stdout.write(rendered)
        sys.stdout.write("\n")
        return 0

    update_project_spec(spec_path, contracts_path, seams_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())

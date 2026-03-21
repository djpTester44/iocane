#!/usr/bin/env python3
"""
check_design_anchors.py

Verifies the Macro/Meso/Micro Hierarchy across two axes:

  1. Protocol Anchor Check — every Protocol in `interfaces/*.pyi` has a
     corresponding CRC card in `plans/project-spec.md`
     (Code without Design → Unanchored Protocol)

  2. Registry Coverage Check — every Protocol in `interfaces/*.pyi` is
     listed in the Interface Registry table of `plans/project-spec.md`
     (Protocol without Registration → Unregistered Protocol)

Usage:
    uv run python .agent/scripts/check_design_anchors.py
    uv run python .agent/scripts/check_design_anchors.py --json
    uv run python .agent/scripts/check_design_anchors.py --spec plans/project-spec.md
"""

import argparse
import json
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Protocol extraction from .pyi files
# ---------------------------------------------------------------------------

# Files excluded from anchor/registry checks (data models, external helpers).
_IGNORED_PYI = {"__init__.pyi", "domain.pyi", "explore.pyi", "braze.pyi"}

# Requires explicit Protocol inheritance syntax: class Foo(Protocol): or
# class Foo(runtime_checkable, Protocol):
# Intentionally strict — must be a real Protocol subclass, not just a comment
# or string containing 'Protocol'.
_PROTOCOL_CLASS = re.compile(r"class\s+(\w+)\s*\(.*\bProtocol\b.*\):")


def get_protocols(interfaces_dir: Path) -> set[str]:
    """Extract Protocol class names from .pyi files."""
    protocols: set[str] = set()
    if not interfaces_dir.exists():
        return protocols

    for pyi_file in interfaces_dir.glob("*.pyi"):
        if pyi_file.name in _IGNORED_PYI:
            continue
        content = pyi_file.read_text(encoding="utf-8")
        for match in _PROTOCOL_CLASS.finditer(content):
            protocols.add(match.group(1))

    return protocols


# ---------------------------------------------------------------------------
# CRC card extraction from project-spec.md
# ---------------------------------------------------------------------------

# Matches '### ComponentName' or '### [ComponentName]' with optional suffix
_CRC_HEADING = re.compile(r"###\s+\[?(\w+)\]?")


def get_anchored_designs(spec_file: Path) -> set[str]:
    """Extract component names from CRC card headers in project-spec.md.

    Scans only under the '## N. Component Specifications' section to avoid
    false matches from other headings.
    """
    designs: set[str] = set()
    if not spec_file.exists():
        return designs

    content = spec_file.read_text(encoding="utf-8")

    # Split on '## N. ... Component Specifications' (handles varied numbering).
    parts = re.split(r"##\s+\d+\.\s+.*?Component Specifications", content)
    if len(parts) < 2:
        return designs

    design_content = parts[1]

    # Look for ### headings that are followed by a Responsibilities (CRC) marker
    # to confirm they are genuine design cards and not sub-section headings.
    for match in re.finditer(
        r"###\s+\[?(\w+)\]?.*?(?:Responsibilities|Key Responsibilities)\s*(?:\(CRC\))?",
        design_content,
        re.DOTALL,
    ):
        designs.add(match.group(1))

    return designs


# ---------------------------------------------------------------------------
# Interface Registry extraction from project-spec.md
# ---------------------------------------------------------------------------

# Matches a table row with at least 3 pipe-delimited columns.
_REGISTRY_ROW = re.compile(
    r"^\|\s*(?P<component>[^|]+?)\s*\|\s*(?P<contract>[^|`]*`?[^|]*?)\s*\|\s*(?P<impl>[^|]+?)\s*\|"
)


def get_registered_protocols(spec_file: Path) -> set[str]:
    """Extract Protocol names from the Interface Registry table.

    Returns bare names (without path) extracted from backtick-formatted
    contract entries, e.g. `interfaces/router.pyi` → 'router.pyi' is not
    useful, so we attempt to match class names from the contract column if
    they're referenced as ProtocolName or FooProtocol, otherwise we extract
    from file stem.
    """
    registered: set[str] = set()
    if not spec_file.exists():
        return registered

    content = spec_file.read_text(encoding="utf-8")

    in_registry = False
    for line in content.splitlines():
        stripped = line.strip()

        if re.match(r"^##\s+(\d+\.\s+)?Interface Registry", stripped):
            in_registry = True
            continue

        if in_registry and re.match(r"^##\s+", stripped):
            break

        if not in_registry:
            continue

        m = _REGISTRY_ROW.match(stripped)
        if not m:
            continue

        comp = m.group("component").strip()
        contract = m.group("contract").strip().strip("`")

        # Skip header and separator rows.
        if comp.lower().startswith("component") or comp.startswith("[e.g") or "---" in comp:
            continue

        # If the contract column names a Protocol class directly (e.g.
        # `RouterProtocol`), use that. Otherwise derive from the component name
        # so we can normalize against Protocol names from .pyi files.
        # We record both the component name and a 'Protocol'-suffixed variant
        # to handle both conventions.
        registered.add(comp)
        registered.add(comp + "Protocol")

        # Also capture any word that looks like a Protocol class name in the
        # contract column.
        for word in re.findall(r"\b(\w+Protocol)\b", contract):
            registered.add(word)

    return registered


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------


def run_checks(
    interfaces_dir: Path,
    spec_file: Path,
) -> dict:
    """Run both anchor and registry checks. Returns a structured result."""

    protocols = get_protocols(interfaces_dir)
    designs = get_anchored_designs(spec_file)
    registered = get_registered_protocols(spec_file)

    # Normalize: strip 'Protocol' suffix for comparison against CRC card names
    # e.g. 'RouterProtocol' → 'Router' to match CRC heading '### Router'
    normalized = {p.replace("Protocol", ""): p for p in protocols}

    unanchored = sorted(
        original for norm, original in normalized.items() if norm not in designs
    )

    unregistered = sorted(
        original
        for original in protocols
        if original not in registered
        and original.replace("Protocol", "") not in registered
    )

    status = "PASS" if not unanchored and not unregistered else "FAIL"

    return {
        "status": status,
        "protocols_found": len(protocols),
        "checks": {
            "unanchored_protocols": unanchored,
            "unregistered_protocols": unregistered,
        },
    }


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------


def format_human(result: dict, interfaces_dir: Path, spec_file: Path) -> str:
    lines = ["--- Iocane Design Anchor Audit ---", ""]

    if not interfaces_dir.exists():
        lines.append(f"[INFO] Interfaces directory not found: {interfaces_dir}")
        lines.append("       No protocols to audit.")
        return "\n".join(lines)

    if not spec_file.exists():
        lines.append(f"[ERROR] Spec file not found: {spec_file}")
        return "\n".join(lines)

    n = result["protocols_found"]
    unanchored = result["checks"]["unanchored_protocols"]
    unregistered = result["checks"]["unregistered_protocols"]

    if n == 0:
        lines.append("[INFO] No protocols found to audit.")
        return "\n".join(lines)

    lines.append(f"Protocols found: {n}")
    lines.append("")

    if unanchored:
        lines.append(f"[FAIL] {len(unanchored)} Unanchored Protocol(s) — missing CRC card:")
        for p in unanchored:
            lines.append(f"  - {p}")
        lines.append("  Action: Run /io-architect to anchor these before implementation.")
        lines.append("")

    if unregistered:
        lines.append(f"[FAIL] {len(unregistered)} Unregistered Protocol(s) — missing from Interface Registry:")
        for p in unregistered:
            lines.append(f"  - {p}")
        lines.append("  Action: Add to the Interface Registry in plans/project-spec.md.")
        lines.append("")

    if not unanchored and not unregistered:
        lines.append(f"[SUCCESS] All {n} protocols are anchored and registered.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Verify Protocol↔CRC anchor coverage and Interface Registry completeness. "
            "Exits 0 on PASS, 1 on FAIL."
        )
    )
    parser.add_argument(
        "--spec",
        default="plans/project-spec.md",
        help="Path to project-spec.md (default: plans/project-spec.md)",
    )
    parser.add_argument(
        "--interfaces",
        default="interfaces",
        help="Path to interfaces directory (default: interfaces)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output structured JSON instead of human-readable text",
    )
    args = parser.parse_args()

    interfaces_dir = Path(args.interfaces)
    spec_file = Path(args.spec)

    result = run_checks(interfaces_dir, spec_file)

    if args.json_output:
        print(json.dumps(result, indent=2))
    else:
        print(format_human(result, interfaces_dir, spec_file))

    sys.exit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()

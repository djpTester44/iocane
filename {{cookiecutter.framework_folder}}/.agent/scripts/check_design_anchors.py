#!/usr/bin/env python3
"""
check_design_anchors.py

Verifies the Macro/Meso/Micro Hierarchy:
1. Scans interfaces/*.pyi for structural Protocols.
2. Scans plans/project-spec.md for corresponding CRC Behavioral Design cards.
3. Flags any "Unanchored Protocols" (Code without Design).
"""

import re
import sys
from pathlib import Path


def get_protocols(interfaces_dir: Path) -> set[str]:
    """Extract Protocol class names from .pyi files."""
    protocols = set()
    if not interfaces_dir.exists():
        return protocols

    # Files to exclude from CRC Anchor check (Data Models, Helpers, etc.)
    ignored_files = {"__init__.pyi", "domain.pyi", "explore.pyi", "braze.pyi"}

    for pyi_file in interfaces_dir.glob("*.pyi"):
        if pyi_file.name in ignored_files:
            continue
        content = pyi_file.read_text(encoding="utf-8")
        # Matches 'class Name(Protocol):' or 'class Name(runtime_checkable, Protocol):'
        matches = re.finditer(r"class\s+(\w+)\s*\(.*Protocol.*\):", content)
        for match in matches:
            protocols.add(match.group(1))
    return protocols

def get_anchored_designs(spec_file: Path) -> set[str]:
    """Extract Component names from CRC Card headers in project-spec.md."""
    designs = set()
    if not spec_file.exists():
        return designs

    content = spec_file.read_text(encoding="utf-8")
    # Matches '### ComponentName' or '### [ComponentName]' under Section 4
    # Looks for the specific CRC Responsibilities marker to confirm it's a design card
    # Split by "Component Specifications" regardless of numbering or exact title
    # Regex split to handle "## 4. Component..." or "## 6. Domain Component..."
    parts = re.split(r"##\s+\d+\.\s+.*?Component Specifications", content)
    if len(parts) < 2:
        return designs
    design_content = parts[1]
    matches = re.finditer(r"###\s+\[?(\w+)\]?.*?Responsibilities \(CRC\)", design_content, re.DOTALL)
    for match in matches:
        designs.add(match.group(1))
    return designs

def main():
    root_dir = Path.cwd()
    interfaces_dir = root_dir / "interfaces"
    spec_file = root_dir / "plans/project-spec.md"

    print("--- Iocane Design Anchor Audit ---")

    protocols = get_protocols(interfaces_dir)
    designs = get_anchored_designs(spec_file)

    # Normalize names (removing 'Protocol' suffix for comparison if used)
    # e.g., 'DataLoaderProtocol' maps to 'DataLoader' design card
    normalized_protocols = {p.replace("Protocol", ""): p for p in protocols}

    unanchored = []
    for norm_name, original_name in normalized_protocols.items():
        if norm_name not in designs:
            unanchored.append(original_name)

    if unanchored:
        print(f"[FAIL] Found {len(unanchored)} Unanchored Protocol(s):")
        for p in sorted(unanchored):
            print(f"  - {p} (Missing CRC Card in project-spec.md)")
        print("\nAction: Run /io-architect to anchor these components before implementation.")
        sys.exit(1)

    if not protocols:
        print("[INFO] No protocols found to audit.")
    else:
        print(f"[SUCCESS] All {len(protocols)} protocols are anchored with behavioral designs.")

    sys.exit(0)

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
check_protocol_sync.py

Verifies that all Protocol definitions in `interfaces/*.pyi` are documented
in the `plans/project-spec.md` Protocol Interfaces table.

Usage:
    uv run python .agent/scripts/check_protocol_sync.py
"""

import re
import sys
from pathlib import Path


def get_defined_protocols(interfaces_dir: Path) -> set[str]:
    """Scan interfaces directory for .pyi files and extract Protocol names."""
    protocols = set()
    if not interfaces_dir.exists():
        print(f"Error: Interfaces directory not found: {interfaces_dir}")
        sys.exit(1)

    # Files to exclude from Protocol Sync check (Data Models, Helpers, etc.)
    ignored_files = {"__init__.pyi", "domain.pyi", "explore.pyi", "braze.pyi"}

    for pyi_file in interfaces_dir.glob("*.pyi"):
        if pyi_file.name in ignored_files:
            continue
        content = pyi_file.read_text(encoding="utf-8")
        # Regex to find 'class Name(Protocol):' or 'class Name(..., Protocol):'
        matches = re.finditer(r"class\s+(\w+).*Protocol.*:", content)
        for match in matches:
            protocols.add(match.group(1))
    return protocols

def get_documented_protocols(spec_file: Path) -> set[str]:
    """Parse project-spec.md to find documented Protocols in the table."""
    protocols = set()
    if not spec_file.exists():
        print(f"Error: Spec file not found: {spec_file}")
        sys.exit(1)

    content = spec_file.read_text(encoding="utf-8")
    # Look for table rows: | Component | `ProtocolName` | ...
    # Regex captures the text inside backticks in the second column (roughly)
    # Or just looks for any `ProtocolName` pattern in a table row
    # Updated to match `ProtocolName` or [ProtocolName](...)
    matches_link = re.finditer(r"\|\s*\[(\w+)\]\(.*?\)\s*\|", content)
    matches_backtick = re.finditer(r"\|\s*.*?\|\s*`(\w+)`\s*\|", content)

    for match in matches_link:
        protocols.add(match.group(1))
    for match in matches_backtick:
        protocols.add(match.group(1))

    return protocols

def main():
    root_dir = Path.cwd()
    interfaces_dir = root_dir / "interfaces"
    spec_file = root_dir / "plans/project-spec.md"
    defined = get_defined_protocols(interfaces_dir)
    documented = get_documented_protocols(spec_file)
    missing = defined - documented
    print(f"Found {len(defined)} defined Protocols.")
    print(f"Found {len(documented)} documented Protocols.")
    if missing:
        print("\n[ERROR] The following Protocols are defined but NOT documented in project-spec.md:")
        for p in sorted(missing):
            print(f"  - {p}")
        print("\nPlease update plans/project-spec.md to include these Protocols.")
        sys.exit(1)
    else:
        print("\n[SUCCESS] All Protocols are documented.")
    sys.exit(0)

if __name__ == "__main__":
    main()

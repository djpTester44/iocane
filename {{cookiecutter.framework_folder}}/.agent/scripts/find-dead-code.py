"""
scripts/audit_dead_code.py

A Contract-Driven Development (CDD) aware wrapper for Vulture.
1. Runs Vulture to find suspected dead code.
2. Filters out CDD Valid Forward Declarations (Ghost Anchors).
3. Filters out framework false positives (pytest autouse, string annotations).
4. Audits settings.yaml for dead/shadowed configuration keys.
5. Outputs a deterministic Markdown report (Tier 1, Tier 2, Tier 4).
"""

import re
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

import yaml


class VultureFinding(NamedTuple):
    file_path: str
    line_number: int
    message: str
    confidence: int
    raw_line: str


class ReportItems:
    def __init__(self):
        self.tier1_actionable = []
        self.tier2_defects = []
        self.tier4_verified = []


class UniqueKeyLoader(yaml.SafeLoader):
    """Custom YAML loader that detects duplicate keys (shadowed config)."""

    pass


def construct_mapping(loader, node):
    loader.flatten_mapping(node)
    mapping = {}
    duplicates = []
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=False)
        if key in mapping:
            duplicates.append(key)
        mapping[key] = loader.construct_object(value_node, deep=False)

    if duplicates:
        # We attach the duplicates to the loader so we can extract them later
        if not hasattr(loader, "duplicate_keys"):
            loader.duplicate_keys = []
        loader.duplicate_keys.extend(duplicates)
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct_mapping
)


def check_yaml_shadowing(yaml_path: Path, report: ReportItems) -> None:
    """Check for duplicate keys in settings.yaml that result in dead config."""
    if not yaml_path.exists():
        return

    try:
        with open(yaml_path, encoding="utf-8") as f:
            loader = UniqueKeyLoader(f)
            try:
                loader.get_single_data()
                if hasattr(loader, "duplicate_keys") and loader.duplicate_keys:
                    for key in set(loader.duplicate_keys):
                        report.tier2_defects.append(
                            {
                                "id": "CFG-01",
                                "target": f"Duplicate key '{key}' in {yaml_path.name}",
                                "action": "CONSOLIDATE into single key to remove shadowing",
                            }
                        )
            finally:
                loader.dispose()
    except Exception as e:
        report.tier2_defects.append(
            {
                "id": "CFG-ERR",
                "target": f"{yaml_path.name} parsing error",
                "action": f"FIX YAML syntax: {str(e)}",
            }
        )


def run_vulture() -> list[VultureFinding]:
    """Execute vulture and parse its raw output."""
    cmd = ["uv", "run", "vulture", "src/", "interfaces/", "tests/"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        print(
            "Error: 'uv' command not found. Ensure you are in the correct environment."
        )
        sys.exit(1)

    findings = []
    # Vulture output format: path/to/file.py:line: message (XX% confidence)
    pattern = re.compile(
        r"^(?P<file>[^:]+):(?P<line>\d+):\s+(?P<msg>.+?)\s+\((?P<conf>\d+)%\s+confidence\)$"
    )

    for line in result.stdout.splitlines():
        match = pattern.match(line)
        if match:
            findings.append(
                VultureFinding(
                    file_path=match.group("file"),
                    line_number=int(match.group("line")),
                    message=match.group("msg"),
                    confidence=int(match.group("conf")),
                    raw_line=line,
                )
            )
    return findings


def is_string_annotation(finding: VultureFinding) -> bool:
    """Check if an unused import is actually consumed by a string-based type annotation."""
    if "unused import" not in finding.message.lower():
        return False

    # Extract the imported name (e.g., "unused import 'StorageExporterProtocol'")
    match = re.search(r"'([^']+)'", finding.message)
    if not match:
        return False

    imported_name = match.group(1)

    try:
        with open(finding.file_path, encoding="utf-8") as f:
            content = f.read()
            # Look for the exact name wrapped in quotes (e.g., "StorageExporterProtocol" or 'StorageExporterProtocol')
            if f'"{imported_name}"' in content or f"'{imported_name}'" in content:
                return True
    except Exception:
        pass
    return False


def is_autouse_fixture(finding: VultureFinding) -> bool:
    """Check if an unused function is a pytest autouse fixture."""
    if (
        "tests/" not in finding.file_path
        or "unused function" not in finding.message.lower()
    ):
        return False

    try:
        with open(finding.file_path, encoding="utf-8") as f:
            lines = f.readlines()

            # Look backwards from the function definition line to find decorators
            line_idx = finding.line_number - 1
            if line_idx >= len(lines):
                return False

            # Scan up to 5 lines above the function def for autouse=True
            for i in range(max(0, line_idx - 5), line_idx):
                if "autouse=True" in lines[i]:
                    return True
    except Exception:
        pass
    return False


def is_io_protocol(finding: VultureFinding) -> bool:
    """Check if the finding is a structural protocol requirement (e.g. io.RawIOBase)."""
    structural_methods = ["writable", "readable", "seekable", "fileno", "isatty"]
    for method in structural_methods:
        if f"unused method '{method}'" in finding.message.lower():
            return True
    return False


def categorize_findings(findings: list[VultureFinding], report: ReportItems) -> None:
    """Apply CDD rules and heuristics to categorize findings."""
    for idx, f in enumerate(findings, start=1):
        f_id = f"VUL-{idx:03d}"

        # 1. CDD Ghost Anchors (Valid Forward Declarations)
        if f.file_path.endswith(".pyi"):
            report.tier4_verified.append(
                {
                    "id": f_id,
                    "target": f"{f.file_path}:{f.line_number}",
                    "reason": f"CDD Forward Declaration (Ghost Anchor): {f.message}",
                }
            )
            continue

        # 2. String Type Annotations False Positives
        if is_string_annotation(f):
            report.tier4_verified.append(
                {
                    "id": f_id,
                    "target": f"{f.file_path}:{f.line_number}",
                    "reason": f"Used in string type annotation: {f.message}",
                }
            )
            continue

        # 3. Pytest Autouse Fixtures False Positives
        if is_autouse_fixture(f):
            report.tier4_verified.append(
                {
                    "id": f_id,
                    "target": f"{f.file_path}:{f.line_number}",
                    "reason": f"Pytest autouse fixture: {f.message}",
                }
            )
            continue

        # 4. IO Protocol Methods False Positives
        if is_io_protocol(f):
            report.tier4_verified.append(
                {
                    "id": f_id,
                    "target": f"{f.file_path}:{f.line_number}",
                    "reason": f"Structural IO Protocol method: {f.message}",
                }
            )
            continue

        # 5. Missing / Unwired Exception Defects
        if "unused class" in f.message.lower() and "Error" in f.message:
            report.tier2_defects.append(
                {
                    "id": f_id,
                    "target": f"{f.file_path}:{f.line_number} ({f.message})",
                    "action": "WIRE exception into implementation or DELETE if abandoned",
                }
            )
            continue

        # Default fallback: Actionable Dead Code
        report.tier1_actionable.append(
            {
                "id": f_id,
                "target": f"{f.file_path}:{f.line_number}",
                "action": f"DELETE / RENAME: {f.message}",
            }
        )


def print_markdown_report(report: ReportItems) -> None:
    """Render the deterministic markdown report."""
    print("# CDD Dead Code Audit Report\n")

    print("## Tier 1: Actionable Dead Code & Cleanup")
    print("| ID | Target | Action |")
    print("|----|--------|--------|")
    if not report.tier1_actionable:
        print("| - | No actionable dead code found | - |")
    for item in report.tier1_actionable:
        print(f"| {item['id']} | `{item['target']}` | {item['action']} |")
    print("\n")

    print("## Tier 2: Defects & Missing Integrations")
    print("| ID | Target | Action |")
    print("|----|--------|--------|")
    if not report.tier2_defects:
        print("| - | No defects found | - |")
    for item in report.tier2_defects:
        print(f"| {item['id']} | `{item['target']}` | {item['action']} |")
    print("\n")

    print("## Tier 4: Verified Not Dead (False Positives & Ghost Anchors)")
    print("| ID | Target | Reason |")
    print("|----|--------|--------|")
    if not report.tier4_verified:
        print("| - | No false positives found | - |")
    for item in report.tier4_verified:
        print(f"| {item['id']} | `{item['target']}` | {item['reason']} |")
    print("\n")

    print(
        "---\n**Instructions:** Review the Tier 1 and Tier 2 findings. Pass accepted changes to `/io-tasking` for execution."
    )


def main():
    report = ReportItems()

    # 1. Audit settings configuration
    yaml_path = Path("settings.yaml")
    check_yaml_shadowing(yaml_path, report)

    # 2. Run Vulture and filter
    findings = run_vulture()
    categorize_findings(findings, report)

    # 3. Output
    print_markdown_report(report)


if __name__ == "__main__":
    main()

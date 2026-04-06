"""Migrate plans/plan.md to plans/plan.yaml.

Parses Markdown plan format (metadata, checkpoints, connectivity tests,
self-healing log) into the Plan Pydantic model and serializes via
plan_parser.save_plan().

Usage:
    uv run rtk python .claude/scripts/migrate_plan.py <input_path> [output_path]
"""

import argparse
import logging
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from migrate_utils import parse_ct_body, parse_ct_heading_topology
from plan_parser import save_plan
from schemas import (
    Checkpoint,
    CheckpointStatus,
    ConnectivityTest,
    Plan,
    ScopeEntry,
    SelfHealingEntry,
    Severity,
)

LOG = logging.getLogger(__name__)


def _parse_plan_md(text: str) -> Plan:
    """Parse plan.md content into a Plan model."""
    lines = text.splitlines()

    # Section A: Metadata
    generated_from, validated, validated_date, validated_note = _parse_metadata(lines)

    # Find section boundaries
    cp_start = _find_heading(lines, "## Checkpoints")
    ct_start = _find_heading(lines, "## Connectivity Tests")
    fcm_start = _find_heading(lines, "## Feature Completion Map")
    sh_start = _find_heading(lines, "## Self-Healing Log")

    # Section B: Checkpoints
    cp_end = ct_start if ct_start is not None else len(lines)
    checkpoints = _parse_checkpoints(lines, cp_start, cp_end) if cp_start is not None else []

    # Section C: Connectivity Tests
    ct_end = fcm_start if fcm_start is not None else (sh_start if sh_start is not None else len(lines))
    connectivity_tests = _parse_connectivity_tests(lines, ct_start, ct_end) if ct_start is not None else []

    # Section D: Self-Healing Log
    self_healing_log = _parse_self_healing_log(lines, sh_start) if sh_start is not None else []

    return Plan(
        generated_from=generated_from,
        validated=validated,
        validated_date=validated_date,
        validated_note=validated_note,
        checkpoints=checkpoints,
        connectivity_tests=connectivity_tests,
        self_healing_log=self_healing_log,
    )


def _find_heading(lines: list[str], heading: str) -> int | None:
    """Find the line index of a specific ## heading."""
    for i, line in enumerate(lines):
        if line.strip().startswith(heading):
            return i
    return None


def _parse_metadata(
    lines: list[str],
) -> tuple[list[str], bool, str | None, str | None]:
    """Parse top-of-file metadata fields."""
    generated_from: list[str] = []
    validated = False
    validated_date: str | None = None
    validated_note: str | None = None

    for line in lines:
        if line.strip().startswith("## "):
            break

        gf_match = re.match(r"\*\*Generated from:\*\*\s*(.*)", line)
        if gf_match:
            generated_from = [
                s.strip() for s in gf_match.group(1).split(" + ")
            ]

        pv_match = re.match(
            r"\*\*Plan Validated:\*\*\s*PASS\s*\(([^,]+),?\s*(.*?)\)", line
        )
        if pv_match:
            validated = True
            validated_date = pv_match.group(1).strip()
            validated_note = pv_match.group(2).strip() or None

    return generated_from, validated, validated_date, validated_note


def _parse_checkpoints(
    lines: list[str], start: int, end: int,
) -> list[Checkpoint]:
    """Parse checkpoint blocks between start and end line indices."""
    checkpoints: list[Checkpoint] = []
    i = start + 1  # Skip the "## Checkpoints" heading

    while i < end:
        line = lines[i]

        # Match checkpoint heading: ### CP-XX: Title  or  ### CP-XXR1: Title
        cp_match = re.match(r"^### (CP-\d{2}(?:R\d+)?):?\s*(.*)", line)
        if cp_match:
            cp_id = cp_match.group(1)
            title_line = cp_match.group(2).strip()
            # Remove trailing emphasis markers
            title = re.sub(r"\*+$", "", title_line).strip()

            # Collect all lines for this checkpoint until next ### or ## or ---
            i += 1
            cp_lines: list[str] = []
            while i < end:
                if re.match(r"^### ", lines[i]) or re.match(r"^## ", lines[i]):
                    break
                cp_lines.append(lines[i])
                i += 1

            cp = _build_checkpoint(cp_id, title, cp_lines)
            checkpoints.append(cp)
        else:
            i += 1

    return checkpoints


def _build_checkpoint(cp_id: str, title: str, cp_lines: list[str]) -> Checkpoint:
    """Build a Checkpoint from its collected field lines."""
    fields: dict[str, str] = {}
    scope_lines: list[str] = []
    in_scope = False

    for line in cp_lines:
        stripped = line.strip()
        if not stripped or stripped == "---":
            continue

        # Detect bold field labels
        field_match = re.match(r"\*\*([^*]+):\*\*\s*(.*)", stripped)
        if field_match:
            key = field_match.group(1).strip()
            val = field_match.group(2).strip()

            if key == "Scope":
                in_scope = True
                if val:
                    scope_lines.append(val)
                continue

            in_scope = False
            fields[key] = val
            continue

        # Scope sub-lines
        if in_scope and stripped.startswith("- "):
            scope_lines.append(stripped)
            continue

        # Non-scope bullet = end of scope region
        if in_scope and not stripped.startswith("- "):
            in_scope = False

        # List items for multi-line fields (Write targets, Context files)
        if stripped.startswith("- `"):
            # Determine which field this list item belongs to
            last_key = _last_list_field(fields)
            if last_key:
                existing = fields[last_key]
                path = stripped.lstrip("- ").strip().strip("`")
                fields[last_key] = existing + ", " + path if existing else path

    # Parse scope entries
    scope = _parse_scope(scope_lines)

    # Parse status
    status_raw = fields.get("Status", "")
    if "[x]" in status_raw.lower():
        status = CheckpointStatus.COMPLETE
    elif "in-progress" in status_raw.lower() or "in progress" in status_raw.lower():
        status = CheckpointStatus.IN_PROGRESS
    else:
        status = CheckpointStatus.PENDING

    # Parse list fields
    write_targets = _parse_path_list(fields.get("Write targets", ""))
    context_files = _parse_context_file_list(fields.get("Context files (read-only)", ""))
    gate_command = fields.get("Gate command", "").strip("`")
    depends_on = _parse_cp_list(fields.get("Depends on", ""))
    parallelizable_with = _parse_cp_list(fields.get("Parallelizable with", ""))

    # Remediation fields (optional)
    remediates: str | None = fields.get("Remediates")
    source: str | None = fields.get("Source")
    source_bl: list[str] | None = None
    severity: Severity | None = None

    if "Source BL" in fields:
        source_bl = [s.strip() for s in fields["Source BL"].split(",") if s.strip()]
    if "Severity" in fields:
        severity = Severity(fields["Severity"].upper())

    return Checkpoint(
        id=cp_id,
        title=title,
        feature=fields.get("Feature", "").strip(),
        description=fields.get("Description", "").strip(),
        status=status,
        scope=scope,
        write_targets=write_targets,
        context_files=context_files,
        gate_command=gate_command,
        depends_on=depends_on,
        parallelizable_with=parallelizable_with,
        remediates=remediates,
        source=source,
        source_bl=source_bl,
        severity=severity,
    )


def _last_list_field(fields: dict[str, str]) -> str | None:
    """Find the most recently added list-type field key."""
    list_keys = ("Write targets", "Context files (read-only)")
    for key in reversed(list(fields.keys())):
        if key in list_keys:
            return key
    return None


def _parse_scope(scope_lines: list[str]) -> list[ScopeEntry]:
    """Parse scope bullet lines into ScopeEntry models."""
    entries: list[ScopeEntry] = []
    current: dict[str, str | list[str]] | None = None

    for line in scope_lines:
        stripped = line.strip().lstrip("- ").strip()

        comp_match = re.match(r"Component:\s*(.+?)(?:\s*\(.*\))?$", stripped)
        if comp_match:
            if current is not None:
                entries.append(_scope_entry_from_dict(current))
            current = {"component": comp_match.group(1).strip(), "protocol": None, "methods": []}
            continue

        proto_match = re.match(r"Protocol:\s*(.*)", stripped)
        if proto_match and current is not None:
            val = proto_match.group(1).strip()
            current["protocol"] = None if val.lower() == "none" else val
            continue

        methods_match = re.match(r"Methods\s*\w*:\s*(.*)", stripped)
        if methods_match and current is not None:
            val = methods_match.group(1).strip()
            if val.lower() == "none" or not val:
                current["methods"] = []
            else:
                current["methods"] = [m.strip().strip("`") for m in val.split(",")]
            continue

    if current is not None:
        entries.append(_scope_entry_from_dict(current))

    return entries


def _scope_entry_from_dict(d: dict[str, str | list[str] | None]) -> ScopeEntry:
    """Create a ScopeEntry from a parsed dict."""
    return ScopeEntry(
        component=str(d.get("component", "")),
        protocol=d.get("protocol") if isinstance(d.get("protocol"), str) else None,
        methods=d.get("methods") if isinstance(d.get("methods"), list) else [],
    )


def _parse_path_list(raw: str) -> list[str]:
    """Parse a comma-or-newline-separated list of backtick-wrapped paths."""
    if not raw.strip():
        return []
    # Split on comma, strip backticks and whitespace
    paths: list[str] = []
    for part in raw.split(","):
        cleaned = part.strip().strip("`")
        if cleaned:
            paths.append(cleaned)
    return paths


def _parse_context_file_list(raw: str) -> list[str]:
    """Parse context files, preserving parenthetical annotations."""
    if not raw.strip():
        return []
    # Split on comma, but not within parentheses
    parts: list[str] = []
    depth = 0
    current = ""
    for char in raw:
        if char == "(":
            depth += 1
            current += char
        elif char == ")":
            depth -= 1
            current += char
        elif char == "," and depth == 0:
            parts.append(current.strip())
            current = ""
        else:
            current += char
    if current.strip():
        parts.append(current.strip())

    return [p.strip().strip("`") for p in parts if p.strip()]


def _parse_cp_list(raw: str) -> list[str]:
    """Parse a list of CP-IDs from 'CP-01, CP-02' or 'none'."""
    if not raw.strip() or raw.strip().lower() == "none":
        return []
    # Strip parenthetical notes like "(Layer 0)"
    cleaned = re.sub(r"\([^)]*\)", "", raw)
    return [cp.strip() for cp in cleaned.split(",") if cp.strip().startswith("CP-")]


def _parse_connectivity_tests(
    lines: list[str], start: int, end: int,
) -> list[ConnectivityTest]:
    """Parse CT blocks between start and end line indices."""
    tests: list[ConnectivityTest] = []
    i = start + 1

    while i < end:
        line = lines[i]

        # Match CT heading: ### CT-NNN: ...
        ct_heading_match = re.match(r"^### (CT-\d{3}):", line)
        if ct_heading_match:
            heading_line = line

            # Collect body lines until next ### or --- separator before next ###
            i += 1
            body_lines: list[str] = []
            while i < end:
                if re.match(r"^### ", lines[i]):
                    break
                body_line = lines[i].strip()
                if body_line and body_line != "---":
                    body_lines.append(body_line)
                i += 1

            # Parse heading topology
            source_cps, target_cp = parse_ct_heading_topology(heading_line)

            # Parse body fields
            body = parse_ct_body(body_lines)

            tests.append(
                ConnectivityTest(
                    test_id=str(body.get("test_id", "")),
                    source_cps=source_cps,
                    target_cp=target_cp,
                    function=str(body.get("function", "")),
                    file=str(body.get("file", "")),
                    fixture_deps=body.get("fixture_deps", []) if isinstance(body.get("fixture_deps"), list) else [],
                    contract_under_test=str(body.get("contract_under_test", "")),
                    assertion=str(body.get("assertion", "")),
                    gate=str(body.get("gate", "")),
                )
            )
        else:
            i += 1

    return tests


def _parse_self_healing_log(
    lines: list[str], start: int,
) -> list[SelfHealingEntry]:
    """Parse the self-healing log table."""
    entries: list[SelfHealingEntry] = []
    i = start + 1

    # Skip blank lines and table header rows
    while i < len(lines):
        stripped = lines[i].strip()
        if not stripped:
            i += 1
            continue
        if stripped.startswith("|") and ("---" in stripped or "Iteration" in stripped):
            i += 1
            continue
        break

    # Parse data rows
    while i < len(lines):
        stripped = lines[i].strip()
        if not stripped or not stripped.startswith("|"):
            break

        cells = [c.strip() for c in stripped.split("|") if c.strip()]
        if len(cells) >= 4:
            # Parse "[AUTO-AMENDED] N" from first cell
            tag_match = re.match(r"\[(\S+)\]\s*(\d+)", cells[0])
            if tag_match:
                tag = tag_match.group(1)
                iteration = int(tag_match.group(2))
                flag = cells[1]
                checkpoint = cells[2]
                description = cells[3]

                entries.append(
                    SelfHealingEntry(
                        tag=tag,
                        iteration=iteration,
                        flag=flag,
                        checkpoint=checkpoint,
                        description=description,
                    )
                )
        i += 1

    return entries


def main() -> int:
    """Run plan migration."""
    parser = argparse.ArgumentParser(
        description="Migrate plan.md to plan.yaml"
    )
    parser.add_argument("input_path", help="Path to plan.md")
    parser.add_argument(
        "output_path", nargs="?", default=None,
        help="Output path (defaults to input with .yaml suffix)",
    )
    args = parser.parse_args()

    input_path = Path(args.input_path)
    if args.output_path:
        output_path = Path(args.output_path)
    else:
        output_path = input_path.with_suffix(".yaml")

    try:
        text = input_path.read_text(encoding="utf-8")
        if not text.strip():
            LOG.error("Input file is empty: %s", input_path)
            return 1

        if output_path.exists():
            LOG.warning("Output file exists, will overwrite: %s", output_path)

        plan = _parse_plan_md(text)
        save_plan(str(output_path), plan)
        LOG.info(
            "Migrated %d checkpoints, %d CTs, %d self-healing entries to %s",
            len(plan.checkpoints),
            len(plan.connectivity_tests),
            len(plan.self_healing_log),
            output_path,
        )
        return 0

    except Exception:
        LOG.exception("Failed to migrate plan")
        return 1


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s: %(message)s"
    )
    sys.exit(main())

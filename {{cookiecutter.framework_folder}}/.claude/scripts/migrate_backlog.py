"""Migrate plans/backlog.md to plans/backlog.yaml.

Parses Markdown checkbox-based backlog format into the Backlog Pydantic
model and serializes via backlog_parser.save_backlog().

Usage:
    uv run python .claude/scripts/migrate_backlog.py <input_path> [output_path]
"""

import argparse
import logging
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backlog_parser import save_backlog
from schemas import Annotation, Backlog, BacklogItem, BacklogTag, ItemStatus, Severity

LOG = logging.getLogger(__name__)


def _parse_backlog_md(text: str) -> Backlog:
    """Parse backlog.md content into a Backlog model."""
    lines = text.splitlines()
    items: list[BacklogItem] = []

    i = 0
    while i < len(lines):
        line = lines[i]

        # Match checkbox lines: - [(x| )] **BL-NNN** [TAG] Title
        checkbox_match = re.match(
            r"^- \[(x| )\] \*\*(\w+-\d+)\*\* \[([^\]]+)\] (.+)$", line
        )
        if not checkbox_match:
            # Skip **BL-NNN** wrapper lines and everything else
            i += 1
            continue

        is_done = checkbox_match.group(1) == "x"
        bl_id = checkbox_match.group(2)
        tag_raw = checkbox_match.group(3)
        title = checkbox_match.group(4).strip()

        status = ItemStatus.RESOLVED if is_done else ItemStatus.OPEN

        # Map tag string to enum
        tag = BacklogTag(tag_raw)

        # Collect indented sub-lines
        i += 1
        sub_lines: list[str] = []
        while i < len(lines):
            next_line = lines[i]
            # Stop at next checkbox or **BL-NNN** wrapper
            if re.match(r"^- \[(x| )\] \*\*\w+-\d+\*\*", next_line):
                break
            if re.match(r"^\*\*BL-\d{3}\*\*$", next_line.strip()):
                break
            sub_lines.append(next_line)
            i += 1

        # Parse sub-fields from collected lines
        fields = _parse_sub_fields(sub_lines)

        # Build annotations
        annotations: list[Annotation] = []

        if "routed" in fields:
            routed_raw = fields["routed"]
            # Parse "CP-NNR1 (DATE)" pattern
            route_match = re.match(r"(CP-\S+)\s*\(([^)]+)\)", routed_raw)
            if route_match:
                routed_value = route_match.group(1)
                route_date = route_match.group(2)
            else:
                routed_value = routed_raw
                route_date = None

            # Check for routing prompt in sub-lines
            route_prompt = fields.get("routing_prompt")

            annotations.append(
                Annotation(
                    type="Routed",
                    value=routed_value,
                    date=route_date,
                    prompt=route_prompt,
                )
            )

        # Parse blocked_by
        blocked_by: list[str] = []
        if "blocked" in fields:
            blocked_raw = fields["blocked"]
            blocked_by = [b.strip() for b in blocked_raw.split(",") if b.strip()]

        # Parse files
        files: list[str] = []
        if "files" in fields:
            files = [f.strip() for f in fields["files"].split(",") if f.strip()]

        # Parse severity
        severity = Severity.MEDIUM
        if "severity" in fields:
            severity = Severity(fields["severity"].upper())

        # Parse contract_impact
        contract_impact: str | None = None
        if "contract impact" in fields:
            raw = fields["contract impact"]
            contract_impact = None if raw.lower() == "none" else raw

        item = BacklogItem(
            id=bl_id,
            tag=tag,
            title=title,
            severity=severity,
            status=status,
            component=fields.get("component"),
            files=files,
            detail=fields.get("detail"),
            contract_impact=contract_impact,
            source=fields.get("source"),
            blocked_by=blocked_by,
            annotations=annotations,
        )
        items.append(item)

    return Backlog(items=items)


def _parse_sub_fields(sub_lines: list[str]) -> dict[str, str]:
    """Parse indented sub-field lines into a key-value dict.

    Recognized keys: Severity, Component, Files, Detail, Contract impact,
    Source, Routed, Blocked. Continuation lines (no key: prefix) are
    appended to the current field. Indented quoted strings after Routed
    are captured as the Routed annotation's prompt field.
    """
    fields: dict[str, str] = {}
    current_key: str | None = None

    known_keys = {
        "severity",
        "component",
        "files",
        "detail",
        "contract impact",
        "source",
        "routed",
        "blocked",
    }

    for raw_line in sub_lines:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("---"):
            continue

        # Check for routing prompt (indented quoted string after Routed)
        prompt_match = re.match(r"^\s+- '(/\S+.*)'$", raw_line)
        if prompt_match:
            fields["routing_prompt"] = prompt_match.group(1)
            continue

        # Check for key: value
        kv_match = re.match(r"^\s+- (\w[\w ]*?):\s*(.*)", raw_line)
        if kv_match:
            key = kv_match.group(1).strip().lower()
            value = kv_match.group(2).strip()
            if key in known_keys:
                fields[key] = value
                current_key = key
                continue

        # Continuation line
        if current_key is not None and stripped:
            fields[current_key] = fields[current_key] + " " + stripped

    return fields


def main() -> int:
    """Run backlog migration."""
    parser = argparse.ArgumentParser(description="Migrate backlog.md to backlog.yaml")
    parser.add_argument("input_path", help="Path to backlog.md")
    parser.add_argument(
        "output_path",
        nargs="?",
        default=None,
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

        backlog = _parse_backlog_md(text)
        save_backlog(str(output_path), backlog)
        LOG.info("Migrated %d backlog items to %s", len(backlog.items), output_path)
        return 0

    except Exception:
        LOG.exception("Failed to migrate backlog")
        return 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    sys.exit(main())

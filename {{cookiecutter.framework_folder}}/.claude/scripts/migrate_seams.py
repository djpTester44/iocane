"""Migrate plans/seams.md to plans/seams.yaml.

Parses Markdown layer/component seam format into the SeamsFile Pydantic
model and serializes via seam_parser.save_seams().

Usage:
    uv run rtk python .claude/scripts/migrate_seams.py <input_path> [output_path]
"""

import argparse
import logging
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from schemas import MissingCtSeam, SeamComponent, SeamsFile
from seam_parser import save_seams

LOG = logging.getLogger(__name__)


def _parse_seams_md(text: str) -> SeamsFile:
    """Parse seams.md content into a SeamsFile model."""
    lines = text.splitlines()
    components: list[SeamComponent] = []
    missing_ct_seams: list[MissingCtSeam] = []

    current_layer: int | None = None
    i = 0

    while i < len(lines):
        line = lines[i]

        # Track layer headings: ## Layer N -- Name
        layer_match = re.match(r"^## Layer (\d+)", line)
        if layer_match:
            current_layer = int(layer_match.group(1))
            i += 1
            continue

        # Missing CT Seams table section
        if line.strip().startswith("## Missing Connectivity Test Seams"):
            i += 1
            # Skip table header rows
            while i < len(lines) and (
                lines[i].strip().startswith("|") and (
                    "CT ID" in lines[i] or "---" in lines[i]
                )
            ):
                i += 1
            # Parse table data rows
            while i < len(lines) and lines[i].strip().startswith("|"):
                row = lines[i].strip()
                cells = [c.strip() for c in row.split("|") if c.strip()]
                if len(cells) >= 3:
                    ct_id = cells[0]
                    seam = cells[1]
                    status = cells[2]
                    if re.match(r"CT-\d{3}", ct_id):
                        missing_ct_seams.append(
                            MissingCtSeam(ct_id=ct_id, seam=seam, status=status)
                        )
                i += 1
            continue

        # Skip Schema Legend section entirely
        if line.strip().startswith("## Schema Legend"):
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("## "):
                i += 1
            continue

        # Component headings: ### ComponentName
        comp_match = re.match(r"^### (\w+)", line)
        if comp_match and current_layer is not None:
            comp_name = comp_match.group(1)
            i += 1

            # Collect component fields until next heading or separator
            receives_di: list[str] = []
            external_terminal: str | None = None
            key_failure_modes: list[str] = []

            while i < len(lines):
                cline = lines[i]
                if re.match(r"^#{2,3} ", cline) or cline.strip() == "---":
                    break

                stripped = cline.strip()

                if stripped.startswith("- **Receives (DI):**"):
                    val = stripped.split(":**", 1)[1].strip()
                    if val.lower() == "none" or not val:
                        receives_di = []
                    else:
                        # Handle multi-part DI values like "`a`, `b` (via method)"
                        receives_di = _parse_di_list(val)

                elif stripped.startswith("- **External terminal:**"):
                    val = stripped.split(":**", 1)[1].strip()
                    external_terminal = None if val.lower().startswith("none") else val

                elif stripped.startswith("- **Key failure modes:**"):
                    val = stripped.split(":**", 1)[1].strip()
                    if val.lower().startswith(("n/a", "none")) or not val:
                        key_failure_modes = []
                    else:
                        # Single-line failure mode
                        key_failure_modes = [val]
                    # Collect sub-bullets
                    i += 1
                    while i < len(lines):
                        subline = lines[i]
                        sub_stripped = subline.strip()
                        if sub_stripped.startswith("- ") and not sub_stripped.startswith("- **"):
                            key_failure_modes.append(sub_stripped[2:].strip())
                            i += 1
                        else:
                            break
                    continue  # skip the i += 1 at end of loop

                i += 1

            components.append(
                SeamComponent(
                    component=comp_name,
                    layer=current_layer,
                    receives_di=receives_di,
                    external_terminal=external_terminal,
                    key_failure_modes=key_failure_modes,
                    backlog_refs=[],
                )
            )
            continue

        i += 1

    return SeamsFile(components=components, missing_ct_seams=missing_ct_seams)


def _parse_di_list(val: str) -> list[str]:
    """Parse DI value string into a list of dependency names.

    Handles formats like:
    - ``None`` -> []
    - ``googlemaps.Client`` -> [``googlemaps.Client``]
    - ```db_path: str`, `IGeocoder | None``` -> [``db_path: str``, ``IGeocoder | None``]
    - ```service_time: int`, `INavigationHost` (via `set_navigation_service`)``
      -> [``service_time: int``, ``INavigationHost (via set_navigation_service)``]
    """
    if val.lower().startswith("none"):
        return []

    # Strip backticks for parsing, but preserve semantic content
    cleaned = val.replace("`", "")

    # Split on ", " but not within parentheses
    parts: list[str] = []
    depth = 0
    current = ""
    for char in cleaned:
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

    # Filter out "None" entries that might result from parsing
    return [p for p in parts if p and p.lower() != "none"]


def main() -> int:
    """Run seams migration."""
    parser = argparse.ArgumentParser(
        description="Migrate seams.md to seams.yaml"
    )
    parser.add_argument("input_path", help="Path to seams.md")
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

        seams = _parse_seams_md(text)
        save_seams(str(output_path), seams)
        LOG.info(
            "Migrated %d components, %d missing CT seams to %s",
            len(seams.components),
            len(seams.missing_ct_seams),
            output_path,
        )
        return 0

    except Exception:
        LOG.exception("Failed to migrate seams")
        return 1


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s: %(message)s"
    )
    sys.exit(main())

"""Shared backlog/plan parsing utilities.

Standalone module (no third-party deps). Used by route-backlog-item.sh,
assign-backlog-ids.sh, archive-approved.sh, and auto_checkpoint.py.
"""

import re


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------


def read_lines(path: str) -> list[str]:
    """Read file into lines list."""
    with open(path, "r", encoding="utf-8") as f:
        return f.readlines()


def write_lines(path: str, lines: list[str]) -> None:
    """Write lines list to file."""
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)


# ---------------------------------------------------------------------------
# Backlog parsing
# ---------------------------------------------------------------------------


def build_bl_index(lines: list[str]) -> dict[str, int]:
    """Build {BL-NNN: line_number} index from backlog lines.

    Pattern: re.match(r'^\\*\\*(BL-\\d{3})\\*\\*$', line.strip())
    Source: archive-approved.sh lines 138-141
    """
    index: dict[str, int] = {}
    for i, line in enumerate(lines):
        m = re.match(r"^\*\*(BL-\d{3})\*\*$", line.strip())
        if m:
            index[m.group(1)] = i
    return index


def find_max_bl_id(lines: list[str]) -> int:
    """Find highest BL-NNN numeric ID. Returns 0 if none.

    Pattern: re.search(r'\\*\\*BL-(\\d{3})\\*\\*', line)
    Source: assign-backlog-ids.sh lines 30-34
    """
    max_id = 0
    for line in lines:
        m = re.search(r"\*\*BL-(\d{3})\*\*", line)
        if m:
            max_id = max(max_id, int(m.group(1)))
    return max_id


def find_bl_anchor(lines: list[str], bl_id: str) -> int:
    """Find line index of **BL-NNN** anchor. Returns -1 if not found.

    Pattern: line.strip() == f'**{bl_id}**'
    Source: route-backlog-item.sh lines 44-49
    """
    marker = f"**{bl_id}**"
    for i, line in enumerate(lines):
        if line.strip() == marker:
            return i
    return -1


def find_summary_line(lines: list[str], anchor: int) -> int | None:
    """Find the '- [ ]' or '- [x]' summary line after an anchor.

    Searches up to 4 lines after the anchor.
    Pattern: re.match(r'^- \\[[ x]\\]', lines[j])
    Source: archive-approved.sh lines 152-155
    """
    for j in range(anchor + 1, min(anchor + 5, len(lines))):
        if re.match(r"^- \[[ x]\]", lines[j]):
            return j
    return None


def walk_subfields(lines: list[str], summary_idx: int) -> int:
    """Walk sub-field lines ('  - ...') after summary. Returns index of last sub-field.

    If no sub-fields exist, returns summary_idx.
    Pattern: lines[i].startswith('  - ')
    Source: route-backlog-item.sh lines 64-74, archive-approved.sh lines 164-169
    """
    insert_after = summary_idx
    i = summary_idx + 1
    while i < len(lines):
        if lines[i].rstrip("\n").startswith("  - "):
            insert_after = i
            i += 1
        else:
            break
    return insert_after


def insert_subfield(
    lines: list[str], insert_after: int, annotation: str
) -> list[str]:
    """Insert a sub-field annotation line after the given index. Returns updated lines."""
    lines.insert(insert_after + 1, annotation)
    return lines


def shift_bl_index(
    bl_index: dict[str, int], after: int, delta: int = 1
) -> None:
    """Shift all BL index entries after the given line by delta. Mutates in place.

    Source: archive-approved.sh lines 174-176
    """
    for k, v in bl_index.items():
        if v > after:
            bl_index[k] = v + delta


# ---------------------------------------------------------------------------
# Plan.md parsing
# ---------------------------------------------------------------------------


def extract_cp_section(plan_text: str, cp_id: str) -> str | None:
    """Extract full text of a ### CP-ID: section from plan.md.

    Pattern: r'### ' + re.escape(cp_id) + r':.*?(?=\\n###|\\Z)' with re.DOTALL
    Source: archive-approved.sh lines 109, 124-125
    """
    pattern = r"### " + re.escape(cp_id) + r":.*?(?=\n###|\Z)"
    m = re.search(pattern, plan_text, re.DOTALL)
    return m.group(0) if m else None


def extract_field(section_text: str, field_name: str) -> str | None:
    """Extract value of **FieldName:** from a CP section.

    Handles multi-line values by reading until next **Field:** or section end.
    """
    pattern = (
        r"\*\*"
        + re.escape(field_name)
        + r":\*\*\s*(.*?)(?=\n\*\*[A-Z].*?:\*\*|\Z)"
    )
    m = re.search(pattern, section_text, re.DOTALL)
    if not m:
        return None
    value = m.group(1).strip()
    return value if value else None


def extract_bl_ids_from_text(text: str) -> list[str]:
    """Find all BL-NNN references in text.

    Pattern: re.findall(r'BL-\\d{3}', text)
    Source: archive-approved.sh line 129
    """
    return re.findall(r"BL-\d{3}", text)

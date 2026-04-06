"""Shared parsing utilities for Markdown-to-YAML migration scripts.

Extracts CT (Connectivity Test) blocks from plan.md format into
structured dicts compatible with the ConnectivityTest Pydantic model.
"""

import re


def parse_ct_body(lines: list[str]) -> dict[str, str | list[str]]:
    """Parse a plain-text CT block into a field dict.

    Handles key-value pairs where:
    - ``fixture_deps`` brackets are stripped and values split on ``,``
    - ``assertion`` may span continuation lines (no ``key:`` prefix)
    - All other fields are plain strings

    Args:
        lines: Lines of the CT body (after the heading, before next ``---``).

    Returns:
        Dict mapping field names to parsed values.
    """
    result: dict[str, str | list[str]] = {}
    current_key: str | None = None

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        # Try to match a key: value line
        kv_match = re.match(r"^(\w[\w_]*):\s*(.*)", line)
        if kv_match:
            key = kv_match.group(1)
            value = kv_match.group(2).strip()

            if key == "fixture_deps":
                # Strip brackets and split on comma
                inner = value.strip("[]")
                if inner.strip():
                    result[key] = [dep.strip() for dep in inner.split(",")]
                else:
                    result[key] = []
            else:
                result[key] = value
            current_key = key
        elif current_key is not None:
            # Continuation line -- append to current key
            existing = result[current_key]
            if isinstance(existing, str):
                result[current_key] = existing + " " + line
            # list continuation not expected, skip

    return result


def parse_ct_heading_topology(heading: str) -> tuple[list[str], str]:
    """Extract source_cps and target_cp from a CT heading line.

    Supports three heading variants:
    - ``### CT-001: CP-01 -> CP-05``
    - ``### CT-004: CP-02 + CP-03 -> CP-04``
    - ``### CT-006: CP-{02,03,04,05,07} -> CP-08``

    Args:
        heading: The full heading line (with or without ``###`` prefix).

    Returns:
        Tuple of (source_cps list, target_cp string).

    Raises:
        ValueError: If the heading doesn't match any known topology pattern.
    """
    # Strip heading markers
    text = re.sub(r"^#+\s*", "", heading).strip()

    # Extract the part after "CT-NNN: "
    ct_match = re.match(r"CT-\d{3}:\s*(.*)", text)
    if not ct_match:
        msg = f"Cannot parse CT heading topology: {heading!r}"
        raise ValueError(msg)

    topology = ct_match.group(1).strip()

    # Split on " -> " to get source and target sides
    if " -> " not in topology:
        msg = f"No ' -> ' separator in topology: {topology!r}"
        raise ValueError(msg)

    source_part, target_part = topology.split(" -> ", 1)
    source_part = source_part.strip()
    target_part = target_part.strip()

    # Strip parenthetical description suffixes from target: "CP-05 (upstream exhaustion)" -> "CP-05"
    target_cp_match = re.match(r"(CP-\d{2}(?:R\d+)?)", target_part)
    if target_cp_match:
        target_part = target_cp_match.group(1)

    # Parse source side
    brace_match = re.match(r"CP-\{([^}]+)\}", source_part)
    if brace_match:
        # Brace expansion: CP-{02,03,04} -> [CP-02, CP-03, CP-04]
        nums = [n.strip() for n in brace_match.group(1).split(",")]
        source_cps = [f"CP-{n}" for n in nums]
    elif " + " in source_part:
        # Plus-separated: CP-02 + CP-03 -> [CP-02, CP-03]
        source_cps = [cp.strip() for cp in source_part.split(" + ")]
    else:
        # Single source: CP-01 -> [CP-01]
        source_cps = [source_part]

    return source_cps, target_part

"""Extract DESIGN/REFACTOR backlog items with /io-architect routing prompts.

Reads open backlog items, applies a 5-criterion eligibility filter, builds
a dependency graph (explicit Blocked: edges), performs topological sort,
and outputs a JSON manifest to stdout.

Usage:
    uv run python .claude/scripts/auto_architect.py [--dry-run] [--repo-root PATH]
"""

import json
import logging
import re
import subprocess
import sys
from collections import deque
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from backlog_parser import (
    build_bl_index,
    extract_architect_prompt,
    extract_bl_ids_from_text,
    find_summary_line,
    read_lines,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Severity ordering for tie-breaking within the same wave.
SEVERITY_ORDER: dict[str, int] = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}

# Tag ordering for tie-breaking: DESIGN before REFACTOR (higher blast radius).
TAG_ORDER: dict[str, int] = {"DESIGN": 2, "REFACTOR": 1}


# ---------------------------------------------------------------------------
# Block line walker (mirrors auto_checkpoint._walk_item_block)
# ---------------------------------------------------------------------------


def _walk_item_block(lines: list[str], summary_idx: int) -> list[str]:
    """Walk all lines belonging to a backlog item (sub-fields + nested lines).

    Captures 2-space and 4-space indented continuation lines.
    """
    block: list[str] = []
    i = summary_idx + 1
    while i < len(lines):
        line = lines[i].rstrip("\n")
        if line.startswith("  - ") or line.startswith("    - "):
            block.append(line)
            i += 1
        else:
            break
    return block


# ---------------------------------------------------------------------------
# Sub-field extraction helpers
# ---------------------------------------------------------------------------


def _extract_field_value(block_lines: list[str], field_name: str) -> str:
    """Extract value from a sub-field like '  - FieldName: value'."""
    pattern = re.compile(rf"^\s+-\s+{re.escape(field_name)}:\s+(.+)")
    for line in block_lines:
        m = pattern.match(line)
        if m:
            return m.group(1).strip()
    return ""


def _extract_blocked_by(block_lines: list[str]) -> list[str]:
    """Extract BL-IDs from Blocked: sub-fields."""
    bl_ids: list[str] = []
    for line in block_lines:
        if re.match(r"^\s+-\s+Blocked:", line):
            bl_ids.extend(extract_bl_ids_from_text(line))
    return bl_ids


def _has_resolved(block_lines: list[str]) -> bool:
    """Check if item has a Resolved: annotation."""
    for line in block_lines:
        if re.match(r"^\s+-\s+Resolved:", line):
            return True
    return False


# ---------------------------------------------------------------------------
# Extraction and eligibility filter
# ---------------------------------------------------------------------------


def extract_eligible_items(
    lines: list[str],
    bl_index: dict[str, int],
) -> list[dict[str, Any]]:
    """Extract open DESIGN/REFACTOR items with /io-architect routing prompts.

    Applies 5-criterion eligibility filter:
      1. Open (- [ ] status)
      2. Tagged DESIGN or REFACTOR
      3. Has Routed: with /io-architect prompt
      4. Not already resolved (no Resolved: annotation)
      5. Not blocked by non-DESIGN/REFACTOR item (external blocker = skip)
    """
    # First pass: collect all items to know tags for criterion 5.
    all_items: dict[str, dict[str, Any]] = {}
    for bl_id, anchor_idx in bl_index.items():
        summary_idx = find_summary_line(lines, anchor_idx)
        if summary_idx is None:
            continue
        summary_line = lines[summary_idx].rstrip("\n")

        tag_match = re.search(
            r"\[(CLEANUP|TEST|DESIGN|REFACTOR|DEFERRED)\]", summary_line
        )
        tag = tag_match.group(1) if tag_match else None
        is_open = summary_line.startswith("- [ ]")

        all_items[bl_id] = {
            "tag": tag,
            "is_open": is_open,
            "summary_idx": summary_idx,
        }

    # Build set of DESIGN/REFACTOR BL-IDs for criterion 5.
    design_refactor_ids: set[str] = {
        bl_id
        for bl_id, info in all_items.items()
        if info["tag"] in ("DESIGN", "REFACTOR")
    }

    eligible: list[dict[str, Any]] = []

    for bl_id, info in all_items.items():
        summary_idx = info["summary_idx"]
        summary_line = lines[summary_idx].rstrip("\n")

        # Criterion 1: Open
        if not info["is_open"]:
            continue

        # Criterion 2: Tagged DESIGN or REFACTOR
        tag = info["tag"]
        if tag not in ("DESIGN", "REFACTOR"):
            continue

        block_lines = _walk_item_block(lines, summary_idx)

        # Criterion 4: Not already resolved
        if _has_resolved(block_lines):
            logger.info("  SKIP %s: already resolved", bl_id)
            continue

        # Criterion 3: Has Routed: with /io-architect prompt
        architect_prompt = extract_architect_prompt(block_lines)
        if not architect_prompt:
            logger.info("  SKIP %s: no /io-architect routing prompt", bl_id)
            continue

        # Extract sub-fields.
        severity = _extract_field_value(block_lines, "Severity") or "MEDIUM"
        files_str = _extract_field_value(block_lines, "Files")
        detail = _extract_field_value(block_lines, "Detail")
        blocked_by = _extract_blocked_by(block_lines)

        # Criterion 5: Not blocked by non-DESIGN/REFACTOR item
        external_blockers = [
            b for b in blocked_by if b not in design_refactor_ids
        ]
        if external_blockers:
            logger.info(
                "  SKIP %s: blocked by external item(s): %s",
                bl_id,
                ", ".join(external_blockers),
            )
            continue

        # Intra-set blockers only (resolvable via ordering).
        intra_blockers = [b for b in blocked_by if b in design_refactor_ids]

        eligible.append({
            "bl_id": bl_id,
            "tag": tag,
            "severity": severity,
            "architect_prompt": architect_prompt,
            "files": [f.strip() for f in files_str.split(",") if f.strip()],
            "detail": detail,
            "blocked_by": intra_blockers,
            "summary_line": summary_line,
        })

    return eligible


# ---------------------------------------------------------------------------
# Topological sort (Kahn's algorithm)
# ---------------------------------------------------------------------------


def topological_sort(
    items: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str] | None]:
    """Sort items by dependency order using Kahn's algorithm.

    Returns (sorted_items, cycle_members_or_none).
    If a cycle is detected, returns ([], list_of_cycle_bl_ids).
    Items are annotated with a "wave" key indicating their execution wave.

    Tie-breaking within same wave: DESIGN before REFACTOR, then by severity
    (HIGH > MEDIUM > LOW).
    """
    item_map: dict[str, dict[str, Any]] = {
        item["bl_id"]: item for item in items
    }
    eligible_ids: set[str] = set(item_map.keys())

    # Build adjacency: edge from blocker -> blocked (blocker must come first).
    # in_degree[node] = number of blockers still unresolved.
    in_degree: dict[str, int] = {bl_id: 0 for bl_id in eligible_ids}
    dependents: dict[str, list[str]] = {bl_id: [] for bl_id in eligible_ids}

    for item in items:
        for blocker in item["blocked_by"]:
            if blocker in eligible_ids:
                in_degree[item["bl_id"]] += 1
                dependents[blocker].append(item["bl_id"])

    # Seed queue with items that have no intra-set blockers.
    def sort_key(bl_id: str) -> tuple[int, int, str]:
        item = item_map[bl_id]
        return (
            -TAG_ORDER.get(item["tag"], 0),
            -SEVERITY_ORDER.get(item["severity"], 0),
            bl_id,
        )

    queue: deque[str] = deque(
        sorted(
            (bl_id for bl_id, deg in in_degree.items() if deg == 0),
            key=sort_key,
        )
    )

    sorted_items: list[dict[str, Any]] = []
    wave = 1
    wave_size = len(queue)
    processed_in_wave = 0

    while queue:
        bl_id = queue.popleft()
        item = item_map[bl_id]
        item["wave"] = wave
        sorted_items.append(item)
        processed_in_wave += 1

        # Release dependents.
        next_wave_candidates: list[str] = []
        for dep in dependents[bl_id]:
            in_degree[dep] -= 1
            if in_degree[dep] == 0:
                next_wave_candidates.append(dep)

        # Add newly-freed items to queue (sorted for determinism).
        for candidate in sorted(next_wave_candidates, key=sort_key):
            queue.append(candidate)

        # Advance wave when current wave exhausted.
        if processed_in_wave == wave_size:
            wave += 1
            wave_size = len(queue)
            processed_in_wave = 0

    # Cycle detection: if not all items were processed.
    if len(sorted_items) < len(items):
        cycle_members = [
            bl_id
            for bl_id in eligible_ids
            if bl_id not in {item["bl_id"] for item in sorted_items}
        ]
        return [], cycle_members

    return sorted_items, None


# ---------------------------------------------------------------------------
# Manifest generation
# ---------------------------------------------------------------------------


def build_manifest(
    items: list[dict[str, Any]],
    today: str,
) -> dict[str, Any]:
    """Build the JSON manifest from sorted eligible items."""
    manifest_items: list[dict[str, Any]] = []
    for item in items:
        manifest_items.append({
            "bl_id": item["bl_id"],
            "tag": item["tag"],
            "severity": item["severity"],
            "wave": item["wave"],
            "architect_prompt": item["architect_prompt"],
            "files": item["files"],
            "detail": item["detail"],
            "blocked_by": item["blocked_by"],
        })

    return {
        "extraction_date": today,
        "item_count": len(manifest_items),
        "items": manifest_items,
    }


# ---------------------------------------------------------------------------
# Repo root resolution
# ---------------------------------------------------------------------------


def _resolve_repo_root(cli_root: str | None) -> str | None:
    """Resolve repo root from CLI arg or git rev-parse fallback."""
    if cli_root:
        return cli_root
    result = subprocess.run(
        ["rtk", "git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


# ---------------------------------------------------------------------------
# CLI arg parsing
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str]) -> tuple[bool, str | None]:
    """Parse CLI args. Returns (dry_run, repo_root)."""
    dry_run = "--dry-run" in argv
    repo_root = None
    for i, arg in enumerate(argv):
        if arg == "--repo-root" and i + 1 < len(argv):
            repo_root = argv[i + 1]
    return dry_run, repo_root


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    """Run auto-architect extraction and output JSON manifest."""
    dry_run, cli_root = _parse_args(sys.argv[1:])

    repo_root = _resolve_repo_root(cli_root)
    if not repo_root:
        logger.error("ERROR: Could not determine repo root.")
        return 1

    repo = Path(repo_root)
    backlog_path = repo / "plans/backlog.md"

    if not backlog_path.is_file():
        logger.error("ERROR: %s not found.", backlog_path)
        return 1

    backlog_lines = read_lines(str(backlog_path))
    bl_index = build_bl_index(backlog_lines)
    today = date.today().isoformat()

    logger.info("Auto-architect scan: %d BL items indexed", len(bl_index))

    # Step 1: Extract eligible items.
    eligible = extract_eligible_items(backlog_lines, bl_index)
    logger.info("Eligible DESIGN/REFACTOR items: %d", len(eligible))

    if not eligible:
        logger.info("No eligible items found. Nothing to do.")
        # Output empty manifest for scripting consumers.
        print(json.dumps({"extraction_date": today, "item_count": 0, "items": []}, indent=2))
        return 0

    # Step 2: Topological sort.
    sorted_items, cycle = topological_sort(eligible)
    if cycle is not None:
        logger.error(
            "ERROR: Dependency cycle detected among: %s", ", ".join(cycle)
        )
        logger.error("HALT: Resolve circular dependencies before running auto-architect.")
        return 1

    # Step 3: Build manifest.
    manifest = build_manifest(sorted_items, today)

    # Step 4: Summary table (to stderr so JSON goes to stdout cleanly).
    logger.info("")
    logger.info(
        "%-10s %-10s %-8s %-5s %s",
        "BL-ID", "Tag", "Severity", "Wave", "Prompt preview",
    )
    logger.info(
        "%-10s %-10s %-8s %-5s %s",
        "-" * 10, "-" * 10, "-" * 8, "-" * 5, "-" * 40,
    )
    for item in sorted_items:
        preview = item["architect_prompt"][:50]
        if len(item["architect_prompt"]) > 50:
            preview += "..."
        logger.info(
            "%-10s %-10s %-8s %-5d %s",
            item["bl_id"],
            item["tag"],
            item["severity"],
            item["wave"],
            preview,
        )
    logger.info("")

    if dry_run:
        logger.info("[DRY RUN] Would output manifest with %d item(s).", manifest["item_count"])

    # Output JSON manifest to stdout.
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

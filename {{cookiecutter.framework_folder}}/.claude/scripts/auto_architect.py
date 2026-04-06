"""Extract DESIGN/REFACTOR backlog items with /io-architect routing prompts.

Reads open backlog items, applies a 5-criterion eligibility filter, builds
a dependency graph (explicit blocked_by edges), performs topological sort,
and outputs a JSON manifest to stdout.

Usage:
    uv run python .claude/scripts/auto_architect.py [--dry-run] [--repo-root PATH]
"""

import json
import logging
import subprocess
import sys
from collections import deque
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from backlog_parser import (
    load_backlog,
)
from schemas import BacklogItem

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Severity ordering for tie-breaking within the same wave.
SEVERITY_ORDER: dict[str, int] = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}

# Tag ordering for tie-breaking: DESIGN before REFACTOR (higher blast radius).
TAG_ORDER: dict[str, int] = {"DESIGN": 2, "REFACTOR": 1}


# ---------------------------------------------------------------------------
# Extraction and eligibility filter
# ---------------------------------------------------------------------------


def extract_eligible_items(
    backlog_items: list[BacklogItem],
) -> list[dict[str, Any]]:
    """Extract open DESIGN/REFACTOR items with /io-architect routing prompts.

    Applies 5-criterion eligibility filter:
      1. Open (status == open)
      2. Tagged DESIGN or REFACTOR
      3. Has routing_prompt containing /io-architect
      4. Not already resolved (no Resolved annotation)
      5. Not blocked by non-DESIGN/REFACTOR item (external blocker = skip)
    """
    # Build set of DESIGN/REFACTOR BL-IDs for criterion 5.
    design_refactor_ids: set[str] = set()
    all_tags: dict[str, str] = {}
    for item in backlog_items:
        all_tags[item.id] = item.tag.value
        if item.tag.value in ("DESIGN", "REFACTOR"):
            design_refactor_ids.add(item.id)

    eligible: list[dict[str, Any]] = []

    for item in backlog_items:
        # Criterion 1: Open
        if item.status.value != "open":
            continue

        # Criterion 2: Tagged DESIGN or REFACTOR
        if item.tag.value not in ("DESIGN", "REFACTOR"):
            continue

        # Criterion 4: Not already resolved (check annotations)
        has_resolved = any(ann.type == "Resolved" for ann in item.annotations)
        if has_resolved:
            logger.info("  SKIP %s: already resolved", item.id)
            continue

        # Criterion 3: Has /io-architect routing prompt
        if not item.routing_prompt or "/io-architect" not in item.routing_prompt:
            logger.info("  SKIP %s: no /io-architect routing prompt", item.id)
            continue

        # Criterion 5: Not blocked by non-DESIGN/REFACTOR item
        external_blockers = [
            b for b in item.blocked_by if b not in design_refactor_ids
        ]
        if external_blockers:
            logger.info(
                "  SKIP %s: blocked by external item(s): %s",
                item.id,
                ", ".join(external_blockers),
            )
            continue

        # Intra-set blockers only (resolvable via ordering).
        intra_blockers = [b for b in item.blocked_by if b in design_refactor_ids]

        eligible.append({
            "bl_id": item.id,
            "tag": item.tag.value,
            "severity": item.severity.value,
            "architect_prompt": item.routing_prompt,
            "files": item.files,
            "detail": item.detail or "",
            "blocked_by": intra_blockers,
            "summary_line": item.title,
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

    in_degree: dict[str, int] = dict.fromkeys(eligible_ids, 0)
    dependents: dict[str, list[str]] = {bl_id: [] for bl_id in eligible_ids}

    for item in items:
        for blocker in item["blocked_by"]:
            if blocker in eligible_ids:
                in_degree[item["bl_id"]] += 1
                dependents[blocker].append(item["bl_id"])

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

        next_wave_candidates: list[str] = []
        for dep in dependents[bl_id]:
            in_degree[dep] -= 1
            if in_degree[dep] == 0:
                next_wave_candidates.append(dep)

        for candidate in sorted(next_wave_candidates, key=sort_key):
            queue.append(candidate)

        if processed_in_wave == wave_size:
            wave += 1
            wave_size = len(queue)
            processed_in_wave = 0

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
    backlog_path = repo / "plans/backlog.yaml"

    if not backlog_path.is_file():
        logger.error("ERROR: %s not found.", backlog_path)
        return 1

    backlog = load_backlog(str(backlog_path))
    today = date.today().isoformat()

    logger.info("Auto-architect scan: %d BL items indexed", len(backlog.items))

    # Step 1: Extract eligible items.
    eligible = extract_eligible_items(backlog.items)
    logger.info("Eligible DESIGN/REFACTOR items: %d", len(eligible))

    if not eligible:
        logger.info("No eligible items found. Nothing to do.")
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

    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

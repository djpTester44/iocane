"""Stage review findings into plans/review-output.yaml.

Reads structured YAML input (findings from io-review or gap-analysis),
validates tags against BacklogTag enum, filters to HIGH/MEDIUM severity,
and appends a new group to plans/review-output.yaml.

Usage:
    uv run python .claude/scripts/stage_review_findings.py --input /tmp/review-findings-CP03.yaml
"""

import argparse
import logging
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from schemas import ReviewStaging, Severity, StagingGroup

logger = logging.getLogger(__name__)

STAGING_PATH = "plans/review-output.yaml"


def _resolve_repo_root() -> Path:
    """Resolve repository root via git rev-parse."""
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        logger.error("Failed to resolve repo root: %s", result.stderr.strip())
        sys.exit(1)
    return Path(result.stdout.strip())


def load_staging(path: Path) -> ReviewStaging:
    """Load existing staging file or return empty container."""
    if not path.exists():
        return ReviewStaging()
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return ReviewStaging()
    raw = yaml.safe_load(text)
    if raw is None:
        return ReviewStaging()
    return ReviewStaging.model_validate(raw)


def save_staging(staging: ReviewStaging, path: Path) -> None:
    """Write staging container to YAML."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = staging.model_dump(mode="json")
    path.write_text(
        yaml.dump(data, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="Stage review findings into plans/review-output.yaml",
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to YAML file containing findings to stage",
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help="Repository root (default: auto-detect via git)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    # Resolve paths
    repo_root = Path(args.repo_root) if args.repo_root else _resolve_repo_root()
    input_path = Path(args.input)
    staging_path = repo_root / STAGING_PATH

    # Read and validate input
    if not input_path.exists():
        logger.error("Input file not found: %s", input_path)
        sys.exit(1)

    raw_input = yaml.safe_load(input_path.read_text(encoding="utf-8"))
    if raw_input is None:
        logger.error("Input file is empty: %s", input_path)
        sys.exit(1)

    try:
        group = StagingGroup.model_validate(raw_input)
    except Exception as exc:
        logger.error("Input validation failed: %s", exc)
        sys.exit(1)

    # Filter to HIGH and MEDIUM severity only
    filtered_items = [
        item for item in group.items
        if item.severity in (Severity.HIGH, Severity.MEDIUM)
    ]

    if not filtered_items:
        logger.info("No HIGH or MEDIUM findings to stage.")
        return

    # Rebuild group with filtered items
    filtered_group = StagingGroup(
        source=group.source,
        date=group.date,
        items=filtered_items,
    )

    skipped = len(group.items) - len(filtered_items)
    if skipped:
        logger.info("Filtered out %d LOW-severity item(s).", skipped)

    # Load existing staging, append, save
    staging = load_staging(staging_path)
    staging.groups.append(filtered_group)
    save_staging(staging, staging_path)

    logger.info(
        "Staged %d finding(s) from %s to %s.",
        len(filtered_items),
        group.source,
        staging_path,
    )


if __name__ == "__main__":
    main()

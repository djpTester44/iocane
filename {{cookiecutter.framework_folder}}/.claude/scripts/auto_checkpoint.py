"""Auto-generate remediation checkpoints from triage-approved routing prompts.

Reads open backlog items with embedded /io-checkpoint routing prompts,
applies a 7-criterion eligibility filter, and appends new checkpoints
to plans/plan.yaml.

Usage:
    uv run python .claude/scripts/auto_checkpoint.py [--dry-run] [--repo-root PATH]
"""

import logging
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from backlog_parser import (
    extract_bl_ids_from_text,
    load_backlog,
    open_items,
)
from plan_parser import (
    add_checkpoint,
    find_checkpoint,
    load_plan,
    save_plan,
)
from plan_parser import (
    resolve_feature as plan_resolve_feature,
)
from plan_parser import (
    resolve_gate as plan_resolve_gate,
)
from schemas import (
    Backlog,
    BacklogItem,
    Checkpoint,
    CheckpointStatus,
    Plan,
    ScopeEntry,
    Severity,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Field-prefix anchored routing prompt parser
# ---------------------------------------------------------------------------

FIELD_PREFIXES = ["Source BL:", "Scope:", "Write targets:", "Gate:"]


def parse_routing_prompt(prompt: str) -> dict[str, str]:
    """Parse a routing prompt into {field_name: value} dict.

    Uses field-prefix anchoring: finds each prefix position, then extracts
    the text between consecutive prefixes.
    """
    positions: list[tuple[int, str]] = []
    for prefix in FIELD_PREFIXES:
        idx = prompt.find(prefix)
        if idx >= 0:
            positions.append((idx, prefix))
    positions.sort()
    fields: dict[str, str] = {}
    for i, (pos, prefix) in enumerate(positions):
        start = pos + len(prefix)
        end = positions[i + 1][0] if i + 1 < len(positions) else len(prompt)
        fields[prefix.rstrip(":")] = prompt[start:end].strip().rstrip(".'\"")
    return fields


# ---------------------------------------------------------------------------
# Backlog item extraction (YAML-based)
# ---------------------------------------------------------------------------


def extract_open_items_with_prompts(
    backlog: Backlog,
) -> list[dict[str, Any]]:
    """Extract open backlog items that have embedded /io-checkpoint routing prompts.

    Returns list of dicts with keys:
        bl_id, tag, severity, routed_cp, prompt, item
    """
    items: list[dict[str, Any]] = []
    candidates = [
        it for it in open_items(backlog)
        if it.routing_prompt and "/io-checkpoint" in it.routing_prompt
    ]

    for item in candidates:
        prompt_text = item.routing_prompt
        assert prompt_text is not None  # filtered above

        # Determine routed_cp from annotations or prompt
        routed_cp = item.routed_to
        if not routed_cp:
            # Try to extract from Routed annotations
            for ann in item.annotations:
                if ann.type == "Routed":
                    routed_cp = ann.value
                    break

        if not routed_cp:
            # Try to extract from prompt text
            cp_match = re.search(
                r"Remediation checkpoint for (CP-\d+(?:R\d+)?)\s*\(",
                prompt_text,
            )
            if cp_match:
                parent = cp_match.group(1)
                routed_cp = _next_remediation_id(parent)

        if routed_cp and prompt_text:
            items.append({
                "bl_id": item.id,
                "tag": item.tag.value,
                "severity": item.severity.value,
                "routed_cp": routed_cp,
                "prompt": prompt_text,
                "item": item,
            })
    return items


def _next_remediation_id(parent_cp: str) -> str | None:
    """Derive the target CP-ID from a parent CP reference.

    E.g. CP-07R1 -> CP-07R2, bare CP-NN -> None (needs plan context).
    """
    r_match = re.match(r"(CP-\d+)R(\d+)", parent_cp)
    if r_match:
        base = r_match.group(1)
        r_num = int(r_match.group(2))
        return f"{base}R{r_num + 1}"
    return None


# ---------------------------------------------------------------------------
# 7-criterion eligibility filter
# ---------------------------------------------------------------------------


def apply_eligibility_filter(
    items: list[dict[str, Any]],
    plan: Plan,
    backlog: Backlog,
) -> list[dict[str, Any]]:
    """Apply the 7-criterion filter. Returns eligible items."""
    eligible: list[dict[str, Any]] = []

    # Pre-compute: find open DESIGN/REFACTOR items and their files for blocking check
    design_refactor_files: set[str] = set()
    for bl_item in open_items(backlog):
        if bl_item.tag.value in ("DESIGN", "REFACTOR"):
            design_refactor_files.update(bl_item.files)

    for item in items:
        bl_id = str(item["bl_id"])
        tag = str(item["tag"])
        routed_cp = str(item["routed_cp"])
        prompt = str(item["prompt"])
        bl_item: BacklogItem = item["item"]

        # Criterion 1: Open (already filtered in extraction)
        # Criterion 2: Tagged CLEANUP or TEST
        if tag not in ("CLEANUP", "TEST"):
            logger.info("  SKIP %s: tag is [%s], not [CLEANUP] or [TEST]", bl_id, tag)
            continue

        # Criterion 3: Has Routed: with embedded /io-checkpoint prompt (already filtered)

        # Criterion 4: Prompt contains all required fields
        fields = parse_routing_prompt(prompt)
        missing = [p.rstrip(":") for p in FIELD_PREFIXES if p.rstrip(":") not in fields]
        if missing:
            logger.info("  SKIP %s: prompt missing fields: %s", bl_id, ", ".join(missing))
            continue

        # Criterion 5: Parent CP exists in plan.yaml
        parent_match = re.search(r"Remediation checkpoint for (CP-\d+)", prompt)
        parent_cp = parent_match.group(1) if parent_match else None
        if not parent_cp:
            logger.info("  SKIP %s: cannot determine parent CP from prompt", bl_id)
            continue
        parent_checkpoint = find_checkpoint(plan, parent_cp)
        if not parent_checkpoint:
            logger.info("  SKIP %s: parent %s not found in plan.yaml", bl_id, parent_cp)
            continue

        # Criterion 6: Target CP does not already exist in plan.yaml (idempotency)
        if find_checkpoint(plan, routed_cp):
            logger.info("  SKIP %s: %s already exists in plan.yaml", bl_id, routed_cp)
            continue

        # Criterion 7: Not blocked by open DESIGN/REFACTOR item
        is_blocked = bool(bl_item.blocked_by)

        # Check implicit file overlap with open DESIGN/REFACTOR items
        if not is_blocked and design_refactor_files:
            item_files = set(bl_item.files)
            if item_files & design_refactor_files:
                is_blocked = True

        if is_blocked:
            logger.info("  SKIP %s: blocked by open DESIGN/REFACTOR item", bl_id)
            continue

        item["fields"] = fields
        item["parent_cp"] = parent_cp
        item["parent_checkpoint"] = parent_checkpoint
        eligible.append(item)

    return eligible


# ---------------------------------------------------------------------------
# Title algorithm
# ---------------------------------------------------------------------------


def generate_title(prompt: str, fields: dict[str, str]) -> str:
    """Generate checkpoint title from routing prompt.

    1. Check for parenthetical: Remediation checkpoint for CP-NN (TEXT)
    2. If TEXT contains 'batch N of M:', strip prefix
    3. If no parenthetical: first 60 chars of Scope
    """
    paren_match = re.search(
        r"Remediation checkpoint for CP-\d+(?:R\d+)?\s*\(([^)]+)\)", prompt
    )
    if paren_match:
        text = paren_match.group(1).strip()
        batch_match = re.match(r"batch \d+ of \d+:\s*", text)
        if batch_match:
            text = text[batch_match.end():]
        return text

    scope = fields.get("Scope", "")
    scope_truncated = scope[:60]
    if len(scope) > 60:
        last_space = scope_truncated.rfind(" ")
        if last_space > 30:
            scope_truncated = scope_truncated[:last_space]

    return scope_truncated


# ---------------------------------------------------------------------------
# Checkpoint builder (returns Checkpoint instance, not markdown)
# ---------------------------------------------------------------------------


def build_remediation_checkpoint(
    cp_id: str,
    title: str,
    feature: str,
    description: str,
    parent_cp: str,
    source_bl_ids: list[str],
    severity: str,
    component_name: str,
    protocol_file: str,
    write_targets: list[str],
    context_files: list[str],
    gate_command: str,
    today: str,
) -> Checkpoint:
    """Build a remediation Checkpoint instance from routing prompt fields."""
    scope = [ScopeEntry(component=component_name, protocol=protocol_file)]
    return Checkpoint(
        id=cp_id,
        title=f"{component_name} -- {title}",
        feature=feature,
        description=description,
        status=CheckpointStatus.PENDING,
        scope=scope,
        write_targets=write_targets,
        context_files=context_files,
        gate_command=gate_command,
        depends_on=[parent_cp],
        remediates=parent_cp,
        source=f"plans/backlog.yaml (From {parent_cp} -- {today})",
        source_bl=source_bl_ids,
        severity=Severity(severity),
    )


def extract_component_name(write_targets_str: str) -> str:
    """Extract PascalCase component name from first src/ write target."""
    src_match = re.search(r"src/\w+/(\w+)\.py", write_targets_str)
    if src_match:
        parts = src_match.group(1).split("_")
        return "".join(p.capitalize() for p in parts)
    return "Unknown"


def extract_write_target_list(write_targets_str: str) -> list[str]:
    """Parse write targets from a comma-separated string."""
    targets: list[str] = []
    for chunk in write_targets_str.split(","):
        chunk = chunk.strip()
        if chunk:
            targets.append(chunk)
    return targets


def build_context_files(
    protocol_file: str,
    component_name: str,
    parent_cp: str,
) -> list[str]:
    """Build context files list for a remediation checkpoint."""
    files = [protocol_file]
    files.append(f"plans/project-spec.md (CRC card for {component_name} only)")
    files.append(f"plans/backlog.yaml (From {parent_cp} section)")
    return files


# ---------------------------------------------------------------------------
# Repo root resolution
# ---------------------------------------------------------------------------


def _resolve_repo_root(cli_root: str | None) -> str | None:
    """Resolve repo root from CLI arg or git rev-parse fallback."""
    if cli_root:
        return cli_root
    result = subprocess.run(
        ["rtk", "git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=False,
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
    """Run auto-checkpoint generation."""
    dry_run, cli_root = _parse_args(sys.argv[1:])

    repo_root = _resolve_repo_root(cli_root)
    if not repo_root:
        logger.error("ERROR: Could not determine repo root.")
        return 1

    repo = Path(repo_root)
    backlog_path = repo / "plans/backlog.yaml"
    plan_path = repo / "plans/plan.yaml"

    if not backlog_path.is_file():
        logger.error("ERROR: %s not found.", backlog_path)
        return 1
    if not plan_path.is_file():
        logger.error("ERROR: %s not found.", plan_path)
        return 1

    backlog = load_backlog(str(backlog_path))
    plan = load_plan(str(plan_path))
    today = date.today().isoformat()

    logger.info("Auto-checkpoint scan: %d BL items indexed", len(backlog.items))

    # Step 1: Extract open items with routing prompts
    items = extract_open_items_with_prompts(backlog)
    logger.info("Items with routing prompts: %d", len(items))

    # Step 2: Apply 7-criterion filter
    eligible = apply_eligibility_filter(items, plan, backlog)
    logger.info("Eligible items after filter: %d", len(eligible))

    if not eligible:
        logger.info("No eligible items found. Nothing to do.")
        return 0

    # Step 3: Deduplicate by CP ID
    cp_groups: dict[str, list[dict[str, Any]]] = {}
    for item in eligible:
        cp = str(item["routed_cp"])
        if cp not in cp_groups:
            cp_groups[cp] = []
        cp_groups[cp].append(item)

    logger.info("Unique CPs to generate: %d", len(cp_groups))

    # Step 4: Generate checkpoint instances for each unique CP
    new_checkpoints: list[Checkpoint] = []
    summary_rows: list[tuple[str, str, str, str]] = []
    routed_pairs: list[tuple[str, str]] = []

    for cp_id, group in sorted(cp_groups.items()):
        primary = group[0]
        fields = primary.get("fields", {})
        if not isinstance(fields, dict):
            continue

        parent_cp = str(primary["parent_cp"])
        parent_checkpoint: Checkpoint = primary["parent_checkpoint"]
        prompt = str(primary["prompt"])

        source_bl_ids: list[str] = []
        for item in group:
            source_bl_ids.append(str(item["bl_id"]))
        source_bl_field = str(fields.get("Source BL", ""))
        for bl in extract_bl_ids_from_text(source_bl_field):
            if bl not in source_bl_ids:
                source_bl_ids.append(bl)

        feature = plan_resolve_feature(plan, parent_cp)
        if not feature:
            logger.error("  ERROR: Could not resolve Feature for %s (parent %s)", cp_id, parent_cp)
            continue

        gate_override = fields.get("Gate")
        gate_command = plan_resolve_gate(plan, parent_cp, override=gate_override)
        if not gate_command:
            logger.error("  ERROR: Could not resolve gate for %s", cp_id)
            continue

        write_targets = extract_write_target_list(str(fields.get("Write targets", "")))
        if not write_targets:
            logger.error("  ERROR: No write targets for %s", cp_id)
            continue

        component_name = extract_component_name(str(fields.get("Write targets", "")))
        protocol_file = ""
        for scope_entry in parent_checkpoint.scope:
            if scope_entry.protocol:
                protocol_file = scope_entry.protocol
                break

        title = generate_title(prompt, fields)

        severity_order = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
        max_sev = "MEDIUM"
        for item in group:
            sev = str(item.get("severity", "MEDIUM"))
            if severity_order.get(sev, 0) > severity_order.get(max_sev, 0):
                max_sev = sev

        context_files = build_context_files(protocol_file, component_name, parent_cp)

        cp_obj = build_remediation_checkpoint(
            cp_id=cp_id,
            title=title,
            feature=feature,
            description=str(fields.get("Scope", "")),
            parent_cp=parent_cp,
            source_bl_ids=source_bl_ids,
            severity=max_sev,
            component_name=component_name,
            protocol_file=protocol_file,
            write_targets=write_targets,
            context_files=context_files,
            gate_command=gate_command,
            today=today,
        )
        new_checkpoints.append(cp_obj)
        source_bl = ", ".join(source_bl_ids)
        summary_rows.append((cp_id, source_bl, title, max_sev))
        for bl_id in source_bl_ids:
            routed_pairs.append((bl_id, cp_id))

    if not new_checkpoints:
        logger.info("No checkpoints generated after processing.")
        return 0

    # Step 5: Print summary table
    logger.info("")
    logger.info("%-12s %-18s %-8s %s", "CP", "Source BL", "Sev", "Title")
    logger.info("%-12s %-18s %-8s %s", "-" * 12, "-" * 18, "-" * 8, "-" * 40)
    for cp_id, source_bl, title, sev in summary_rows:
        logger.info("%-12s %-18s %-8s %s", cp_id, source_bl, sev, title)
    logger.info("")

    if dry_run:
        logger.info("[DRY RUN] Would write %d checkpoint(s) to plan.yaml:", len(new_checkpoints))
        logger.info("")
        for cp_obj in new_checkpoints:
            logger.info("  %s: %s", cp_obj.id, cp_obj.title)
        logger.info("[DRY RUN] Would route %d backlog item(s):", len(routed_pairs))
        for bl_id, cp_id in routed_pairs:
            logger.info("  %s -> %s", bl_id, cp_id)
        return 0

    # Step 6: Append checkpoints and save
    for cp_obj in new_checkpoints:
        plan = add_checkpoint(plan, cp_obj)

    save_plan(str(plan_path), plan)

    logger.info(
        "AUTO-CHECKPOINT: %d checkpoint(s) written to plan.yaml.",
        len(new_checkpoints),
    )

    # Step 7: Route consumed backlog items via route_backlog_item.py
    route_script = repo / ".claude/scripts/route_backlog_item.py"
    if not route_script.is_file():
        logger.error("WARNING: %s not found -- skipping backlog routing.", route_script)
    else:
        route_failures = 0
        for bl_id, cp_id in routed_pairs:
            result = subprocess.run(
                ["uv", "run", "python", str(route_script), bl_id, cp_id],
                capture_output=True, text=True, check=False,
                cwd=str(repo),
            )
            if result.returncode == 0:
                logger.info("  %s", result.stdout.strip())
            else:
                logger.error("  WARNING: Failed to route %s -> %s: %s",
                             bl_id, cp_id, result.stderr.strip())
                route_failures += 1
        if route_failures:
            logger.error("WARNING: %d backlog routing(s) failed -- items may need manual Routed: annotation.", route_failures)

    return 0


if __name__ == "__main__":
    sys.exit(main())

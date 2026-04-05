"""Auto-generate remediation checkpoints from triage-approved routing prompts.

Reads open backlog items with embedded /io-checkpoint routing prompts,
applies a 7-criterion eligibility filter, and appends new checkpoints
to plans/plan.md under ## Remediation Checkpoints.

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
    build_bl_index,
    extract_bl_ids_from_text,
    extract_cp_section,
    extract_field,
    find_summary_line,
    read_lines,
    walk_subfields,
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
# Backlog item extraction
# ---------------------------------------------------------------------------


def _walk_item_block(lines: list[str], summary_idx: int) -> list[str]:
    """Walk all lines belonging to a backlog item (sub-fields + nested lines).

    Captures 2-space and 4-space indented continuation lines.
    """
    block: list[str] = []
    i = summary_idx + 1
    while i < len(lines):
        line = lines[i].rstrip("\n")
        # Sub-fields (2-space) and nested sub-sub-fields (4-space)
        if line.startswith("  - ") or line.startswith("    - "):
            block.append(line)
            i += 1
        else:
            break
    return block


def extract_open_items_with_prompts(
    lines: list[str], bl_index: dict[str, int]
) -> list[dict[str, Any]]:
    """Extract open backlog items that have embedded /io-checkpoint routing prompts.

    Returns list of dicts with keys:
        bl_id, summary, tag, severity, routed_cp, prompt, anchor_idx, subfield_lines
    """
    items: list[dict[str, Any]] = []
    for bl_id, anchor_idx in bl_index.items():
        summary_idx = find_summary_line(lines, anchor_idx)
        if summary_idx is None:
            continue
        summary_line = lines[summary_idx].rstrip("\n")
        # Must be open
        if not summary_line.startswith("- [ ]"):
            continue

        # Extract tag
        tag_match = re.search(r"\[(CLEANUP|TEST|DESIGN|REFACTOR|DEFERRED)\]", summary_line)
        tag = tag_match.group(1) if tag_match else None

        # Walk all item lines (including nested 4-space lines)
        block_lines = _walk_item_block(lines, summary_idx)

        # Find severity
        severity = ""
        for sf in block_lines:
            sev_match = re.match(r"^\s+-\s+Severity:\s+(\w+)", sf)
            if sev_match:
                severity = sev_match.group(1)
                break

        # Find Routed: annotation with embedded /io-checkpoint prompt
        routed_cp = None
        prompt_text = None
        for sf in block_lines:
            # Look for Routed: CP-XXXRN lines (not cross-references like "see BL-NNN")
            routed_match = re.match(r"^\s+-\s+Routed:\s+(CP-\d+R\d+)", sf)
            if routed_match:
                routed_cp = routed_match.group(1)
            # Look for Routed: without CP (e.g. "Routed: (2026-03-16)")
            # The CP ID may be embedded in the prompt instead
            if not routed_cp:
                routed_date_match = re.match(r"^\s+-\s+Routed:\s+\(", sf)
                if routed_date_match:
                    # CP ID will come from parsing the prompt line below
                    pass

            # Look for embedded prompt (line containing /io-checkpoint)
            if "\\io-checkpoint" in sf or "/io-checkpoint" in sf:
                prompt_raw = sf.strip()
                # Remove leading "- '" and trailing "'"
                prompt_raw = re.sub(r"^-\s*'\\?/?io-checkpoint\s*", "", prompt_raw)
                prompt_raw = prompt_raw.rstrip("'")
                prompt_text = prompt_raw
                # If no CP from Routed: line, try to extract from prompt
                if not routed_cp:
                    cp_match = re.search(
                        r"Remediation checkpoint for (CP-\d+(?:R\d+)?)\s*\(",
                        prompt_raw,
                    )
                    if cp_match:
                        parent = cp_match.group(1)
                        # Determine the next R-suffix for this parent
                        # by checking what already exists
                        routed_cp = _next_remediation_id(parent, prompt_raw)

        if routed_cp and prompt_text:
            items.append({
                "bl_id": bl_id,
                "summary": summary_line,
                "tag": tag or "UNKNOWN",
                "severity": severity,
                "routed_cp": routed_cp,
                "prompt": prompt_text,
                "anchor_idx": anchor_idx,
                "subfield_lines": block_lines,
            })
    return items


def _next_remediation_id(parent_cp: str, _prompt: str) -> str | None:
    """Derive the target CP-ID from a routing prompt when Routed: has no CP.

    Looks for explicit CP reference in the prompt parenthetical, e.g.:
    'Remediation checkpoint for CP-07R1 (BL-033: ...)' -> CP-07R2
    'Remediation checkpoint for CP-06 (batch 3: ...)' -> needs plan context
    """
    # Check if the parent already has an R-suffix (e.g. CP-07R1)
    r_match = re.match(r"(CP-\d+)R(\d+)", parent_cp)
    if r_match:
        base = r_match.group(1)
        r_num = int(r_match.group(2))
        return f"{base}R{r_num + 1}"
    # For bare CP-NN, we can't determine the R-suffix without plan context
    # Return None -- this will be filtered out
    return None


# ---------------------------------------------------------------------------
# 7-criterion eligibility filter
# ---------------------------------------------------------------------------


def apply_eligibility_filter(
    items: list[dict[str, Any]],
    plan_text: str,
    backlog_lines: list[str],
    bl_index: dict[str, int],
) -> list[dict[str, Any]]:
    """Apply the 7-criterion filter. Returns eligible items."""
    eligible: list[dict[str, Any]] = []

    # Pre-compute: find open DESIGN/REFACTOR items and their files for blocking check
    design_refactor_files: set[str] = set()
    for bl_id, anchor_idx in bl_index.items():
        summary_idx = find_summary_line(backlog_lines, anchor_idx)
        if summary_idx is None:
            continue
        summary_line = backlog_lines[summary_idx].rstrip("\n")
        if not summary_line.startswith("- [ ]"):
            continue
        tag_match = re.search(r"\[(DESIGN|REFACTOR)\]", summary_line)
        if not tag_match:
            continue
        # Collect files from this blocker item
        last_sf = walk_subfields(backlog_lines, summary_idx)
        for j in range(summary_idx + 1, last_sf + 1):
            files_match = re.match(r"^\s+-\s+Files:\s+(.+)", backlog_lines[j])
            if files_match:
                for f in re.findall(r"`([^`]+)`", files_match.group(1)):
                    design_refactor_files.add(f)

    for item in items:
        bl_id = str(item["bl_id"])
        tag = str(item["tag"])
        routed_cp = str(item["routed_cp"])
        prompt = str(item["prompt"])

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

        # Criterion 5: Parent CP exists in plan.md
        # Extract parent from "Remediates" or from routing prompt cp reference
        parent_match = re.search(r"Remediation checkpoint for (CP-\d+)", prompt)
        parent_cp = parent_match.group(1) if parent_match else None
        if not parent_cp:
            logger.info("  SKIP %s: cannot determine parent CP from prompt", bl_id)
            continue
        parent_section = extract_cp_section(plan_text, parent_cp)
        if not parent_section:
            logger.info("  SKIP %s: parent %s not found in plan.md", bl_id, parent_cp)
            continue

        # Criterion 6: Target CP does not already exist in plan.md (idempotency)
        if extract_cp_section(plan_text, routed_cp):
            logger.info("  SKIP %s: %s already exists in plan.md", bl_id, routed_cp)
            continue

        # Criterion 7: Not blocked by open DESIGN/REFACTOR item
        # Check explicit Blocked: annotation
        subfield_lines = item.get("subfield_lines", [])
        is_blocked = False
        for sf in subfield_lines:
            if isinstance(sf, str) and re.match(r"^\s+-\s+Blocked:", sf):
                is_blocked = True
                break

        # Check implicit file overlap with open DESIGN/REFACTOR items
        if not is_blocked and design_refactor_files:
            item_files: set[str] = set()
            for sf in subfield_lines:
                if isinstance(sf, str):
                    files_match = re.match(r"^\s+-\s+Files:\s+(.+)", sf)
                    if files_match:
                        for f in re.findall(r"`([^`]+)`", files_match.group(1)):
                            item_files.add(f)
            if item_files & design_refactor_files:
                is_blocked = True

        if is_blocked:
            logger.info("  SKIP %s: blocked by open DESIGN/REFACTOR item", bl_id)
            continue

        item["fields"] = fields
        item["parent_cp"] = parent_cp
        item["parent_section"] = parent_section
        eligible.append(item)

    return eligible


# ---------------------------------------------------------------------------
# Title algorithm
# ---------------------------------------------------------------------------


def generate_title(prompt: str, fields: dict[str, str]) -> str:
    """Generate checkpoint title from routing prompt.

    1. Check for parenthetical: Remediation checkpoint for CP-NN (TEXT)
    2. If TEXT contains 'batch N of M:', strip prefix
    3. If no parenthetical: {Component} -- {first 60 chars of Scope}
    """
    paren_match = re.search(
        r"Remediation checkpoint for CP-\d+(?:R\d+)?\s*\(([^)]+)\)", prompt
    )
    if paren_match:
        text = paren_match.group(1).strip()
        # Strip "batch N of M:" prefix
        batch_match = re.match(r"batch \d+ of \d+:\s*", text)
        if batch_match:
            text = text[batch_match.end():]
        return text

    # Fallback: first 60 chars of scope (component name is prepended by the
    # checkpoint template in generate_checkpoint_markdown, so omit it here
    # to avoid duplication like "Component -- Component -- scope").
    scope = fields.get("Scope", "")
    scope_truncated = scope[:60]
    if len(scope) > 60:
        # Truncate at word boundary
        last_space = scope_truncated.rfind(" ")
        if last_space > 30:
            scope_truncated = scope_truncated[:last_space]

    return scope_truncated


# ---------------------------------------------------------------------------
# Remediation chain walker
# ---------------------------------------------------------------------------


def resolve_feature(plan_text: str, cp_id: str) -> str | None:
    """Walk Remediates chain to root roadmap CP for Feature field."""
    visited: set[str] = set()
    current = cp_id
    while current and current not in visited:
        visited.add(current)
        section = extract_cp_section(plan_text, current)
        if not section:
            return None
        feature = extract_field(section, "Feature")
        remediates = extract_field(section, "Remediates")
        if not remediates:
            # This is the root CP
            return feature
        # Walk up to parent
        parent_match = re.match(r"(CP-\d+)", remediates)
        if parent_match:
            current = parent_match.group(1)
        else:
            return feature
    return None


def resolve_gate(
    fields: dict[str, str], parent_section: str, plan_text: str
) -> str | None:
    """Resolve gate command. If 'inherited from CP-NN', use parent's gate."""
    gate = fields.get("Gate", "")
    inherit_match = re.match(r"inherited from (CP-\d+(?:R\d+)?)", gate)
    if inherit_match:
        source_cp = inherit_match.group(1)
        source_section = extract_cp_section(plan_text, source_cp)
        if source_section:
            return extract_field(source_section, "Gate command")
        # Fall back to parent section
        return extract_field(parent_section, "Gate command")
    if gate:
        return gate
    return extract_field(parent_section, "Gate command")


# ---------------------------------------------------------------------------
# Checkpoint generation
# ---------------------------------------------------------------------------


def generate_checkpoint_markdown(
    cp_id: str,
    title: str,
    feature: str,
    scope: str,
    parent_cp: str,
    source_bl: str,
    severity: str,
    component_name: str,
    protocol_file: str,
    write_targets: list[str],
    context_files: list[str],
    gate_command: str,
    today: str,
) -> str:
    """Generate a single remediation checkpoint markdown block."""
    write_targets_md = "\n".join(f"- `{t}`" for t in write_targets)
    context_files_md = "\n".join(f"- `{c}`" for c in context_files)

    return f"""### {cp_id}: {component_name} -- {title}

**Feature:** {feature}
**Description:** {scope}
**Remediates:** {parent_cp}
**Source:** plans/backlog.md (From {parent_cp} -- {today})
**Source BL:** {source_bl}
**Severity:** {severity}
**Status:** [ ] pending

**Scope:**

- Component: {component_name} (`{write_targets[0] if write_targets else "unknown"}`)
- Protocol: `{protocol_file}`

**Write targets:**

{write_targets_md}

**Context files (read-only):**

{context_files_md}

**Gate command:** `{gate_command}`

**Depends on:** {parent_cp}

---
"""


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
    files.append(f"plans/backlog.md (From {parent_cp} section)")
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
    backlog_path = repo / "plans/backlog.md"
    plan_path = repo / "plans/plan.md"

    if not backlog_path.is_file():
        logger.error("ERROR: %s not found.", backlog_path)
        return 1
    if not plan_path.is_file():
        logger.error("ERROR: %s not found.", plan_path)
        return 1

    backlog_lines = read_lines(str(backlog_path))
    plan_text = plan_path.read_text(encoding="utf-8")

    bl_index = build_bl_index(backlog_lines)
    today = date.today().isoformat()

    logger.info("Auto-checkpoint scan: %d BL items indexed", len(bl_index))

    # Step 1: Extract open items with routing prompts
    items = extract_open_items_with_prompts(backlog_lines, bl_index)
    logger.info("Items with routing prompts: %d", len(items))

    # Step 2: Apply 7-criterion filter
    eligible = apply_eligibility_filter(items, plan_text, backlog_lines, bl_index)
    logger.info("Eligible items after filter: %d", len(eligible))

    if not eligible:
        logger.info("No eligible items found. Nothing to do.")
        return 0

    # Step 3: Deduplicate by CP ID (group items sharing same Routed: CP-XXXRN)
    cp_groups: dict[str, list[dict[str, Any]]] = {}
    for item in eligible:
        cp = str(item["routed_cp"])
        if cp not in cp_groups:
            cp_groups[cp] = []
        cp_groups[cp].append(item)

    logger.info("Unique CPs to generate: %d", len(cp_groups))

    # Step 4: Generate checkpoint markdown for each unique CP
    checkpoints: list[str] = []
    summary_rows: list[tuple[str, str, str, str]] = []
    routed_pairs: list[tuple[str, str]] = []  # (bl_id, cp_id) for backlog routing

    for cp_id, group in sorted(cp_groups.items()):
        # Use first item's prompt as the primary
        primary = group[0]
        fields = primary.get("fields", {})
        if not isinstance(fields, dict):
            continue

        parent_cp = str(primary["parent_cp"])
        parent_section = str(primary["parent_section"])
        prompt = str(primary["prompt"])

        # Collect all source BL IDs from the group
        source_bl_ids: list[str] = []
        for item in group:
            source_bl_ids.append(str(item["bl_id"]))
        # Also include any BL IDs mentioned in the Source BL field
        source_bl_field = str(fields.get("Source BL", ""))
        for bl in extract_bl_ids_from_text(source_bl_field):
            if bl not in source_bl_ids:
                source_bl_ids.append(bl)

        source_bl = ", ".join(source_bl_ids)

        # Resolve feature via remediation chain
        feature = resolve_feature(plan_text, parent_cp)
        if not feature:
            logger.error("  ERROR: Could not resolve Feature for %s (parent %s)", cp_id, parent_cp)
            continue

        # Resolve gate
        gate_command = resolve_gate(fields, parent_section, plan_text)
        if not gate_command:
            logger.error("  ERROR: Could not resolve gate for %s", cp_id)
            continue

        # Parse write targets
        write_targets = extract_write_target_list(str(fields.get("Write targets", "")))
        if not write_targets:
            logger.error("  ERROR: No write targets for %s", cp_id)
            continue

        # Determine component name and protocol
        component_name = extract_component_name(str(fields.get("Write targets", "")))
        # Get protocol from parent section
        protocol_file = ""
        parent_protocol = extract_field(parent_section, "Scope")
        if parent_protocol:
            proto_match = re.search(r"`(interfaces/\w+\.pyi)`", parent_protocol)
            if proto_match:
                protocol_file = proto_match.group(1)

        # Generate title
        title = generate_title(prompt, fields)

        # Determine severity (highest in group)
        severity_order = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
        max_sev = "MEDIUM"
        for item in group:
            sev = str(item.get("severity", "MEDIUM"))
            if severity_order.get(sev, 0) > severity_order.get(max_sev, 0):
                max_sev = sev

        # Build context files
        context_files = build_context_files(protocol_file, component_name, parent_cp)

        cp_md = generate_checkpoint_markdown(
            cp_id=cp_id,
            title=title,
            feature=feature,
            scope=str(fields.get("Scope", "")),
            parent_cp=parent_cp,
            source_bl=source_bl,
            severity=max_sev,
            component_name=component_name,
            protocol_file=protocol_file,
            write_targets=write_targets,
            context_files=context_files,
            gate_command=gate_command,
            today=today,
        )
        checkpoints.append(cp_md)
        summary_rows.append((cp_id, source_bl, title, max_sev))
        for bl_id in source_bl_ids:
            routed_pairs.append((bl_id, cp_id))

    if not checkpoints:
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
        logger.info("[DRY RUN] Would write %d checkpoint(s) to plan.md:", len(checkpoints))
        logger.info("")
        for cp_md in checkpoints:
            logger.info(cp_md)
        logger.info("[DRY RUN] Would route %d backlog item(s):", len(routed_pairs))
        for bl_id, cp_id in routed_pairs:
            logger.info("  %s -> %s", bl_id, cp_id)
        return 0

    # Step 6: Atomic write -- insert before ## Connectivity Tests
    insert_marker = "\n## Connectivity Tests"
    if insert_marker not in plan_text:
        logger.error("ERROR: '## Connectivity Tests' section not found in plan.md")
        return 1

    new_content = "\n" + "\n".join(checkpoints)
    updated_plan = plan_text.replace(insert_marker, new_content + insert_marker, 1)

    plan_path.write_text(updated_plan, encoding="utf-8")

    logger.info("AUTO-CHECKPOINT: %d checkpoint(s) written to plan.md.", len(checkpoints))

    # Step 7: Route consumed backlog items via route-backlog-item.sh
    route_script = repo / ".claude/scripts/route-backlog-item.sh"
    if not route_script.is_file():
        logger.error("WARNING: %s not found -- skipping backlog routing.", route_script)
    else:
        route_failures = 0
        for bl_id, cp_id in routed_pairs:
            result = subprocess.run(
                ["bash", str(route_script), bl_id, cp_id],
                capture_output=True, text=True, check=False,
                cwd=str(repo),
            )
            if result.returncode == 0:
                logger.info("  %s", result.stdout.strip())
            else:
                # Non-fatal: CP was written, routing annotation failed
                logger.error("  WARNING: Failed to route %s -> %s: %s",
                             bl_id, cp_id, result.stderr.strip())
                route_failures += 1
        if route_failures:
            logger.error("WARNING: %d backlog routing(s) failed -- items may need manual Routed: annotation.", route_failures)

    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env bash
# .claude/scripts/group_findings.sh
#
# Deterministic grouping script: parse assessment-manifest.yaml, group findings
# by target_path, separate into waves by depends_on, write dispatch-wave-N.yaml.
#
# Inputs:
#   plans/assessment-manifest.yaml  (produced by HARNESS_classify_candidates.py)
#
# Outputs:
#   plans/evo-findings/dispatch-wave-1.yaml
#   plans/evo-findings/dispatch-wave-2.yaml  (if deferred findings exist)
#   ...
#
# Usage:
#   bash .claude/scripts/group_findings.sh

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null)}"
if [ -z "$REPO_ROOT" ]; then
    echo "group_findings: ERROR: could not determine repo root." >&2
    exit 1
fi

MANIFEST="$REPO_ROOT/plans/assessment-manifest.yaml"

if [ ! -f "$MANIFEST" ]; then
    echo "group_findings: ERROR: assessment-manifest.yaml not found at $MANIFEST" >&2
    echo "Run HARNESS_classify_candidates.py first." >&2
    exit 1
fi

mkdir -p "$REPO_ROOT/plans/evo-findings"

echo "group_findings: grouping findings from $MANIFEST" >&2

uv run python - "$REPO_ROOT" "$MANIFEST" <<'PYEOF'
import sys
import yaml
from pathlib import Path
from collections import defaultdict

repo_root = Path(sys.argv[1])
manifest_path = Path(sys.argv[2])
out_dir = repo_root / "plans" / "evo-findings"

data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
findings = data.get("findings", [])

if not findings:
    print("group_findings: no findings to dispatch.", file=sys.stderr)
    sys.exit(0)

# Group findings sharing the same target_path into one dispatch unit.
# group_id is derived from the first finding ID in the group.
groups_by_target: dict[str, dict] = {}
group_counter = 1

for finding in findings:
    target = finding.get("target_path") or f"__unknown_{finding['id']}"
    if target not in groups_by_target:
        groups_by_target[target] = {
            "group_id": f"g{group_counter}",
            "finding_ids": [],
            "target_path": target,
            "depends_on": set(),
        }
        group_counter += 1
    g = groups_by_target[target]
    g["finding_ids"].append(finding["id"])
    for dep in finding.get("depends_on", []):
        g["depends_on"].add(dep)

# Convert set to sorted list for YAML output.
all_groups = []
for g in groups_by_target.values():
    g["depends_on"] = sorted(g["depends_on"])
    all_groups.append(g)

# Separate into waves: Wave 1 = groups with no depends_on;
# Wave 2+ = groups whose depends_on resolved in prior waves.
resolved_ids: set[int] = set()
wave_num = 1
remaining = list(all_groups)

while remaining:
    wave_groups = []
    still_waiting = []
    for g in remaining:
        if all(dep in resolved_ids for dep in g["depends_on"]):
            wave_groups.append(g)
        else:
            still_waiting.append(g)

    if not wave_groups:
        # Dependency cycle or unresolvable -- dump all remaining into current wave.
        print(
            f"group_findings: WARNING: dependency cycle detected; dumping {len(remaining)} groups into wave {wave_num}.",
            file=sys.stderr,
        )
        wave_groups = remaining
        still_waiting = []

    wave_doc = {
        "wave": wave_num,
        "groups": [
            {
                "group_id": g["group_id"],
                "finding_ids": g["finding_ids"],
                "target_path": g["target_path"],
            }
            for g in wave_groups
        ],
    }
    wave_path = out_dir / f"dispatch-wave-{wave_num}.yaml"
    wave_path.write_text(
        yaml.dump(wave_doc, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    print(f"group_findings: wave {wave_num} -> {wave_path} ({len(wave_groups)} groups)", file=sys.stderr)

    # Mark all finding IDs in this wave as resolved.
    for g in wave_groups:
        for fid in g["finding_ids"]:
            resolved_ids.add(fid)

    remaining = still_waiting
    wave_num += 1

print(f"WAVES={wave_num - 1}", flush=True)
PYEOF

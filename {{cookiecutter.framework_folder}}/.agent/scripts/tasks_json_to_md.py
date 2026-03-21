#!/usr/bin/env python3
"""
tasks_json_to_md.py — Iocane v1 → v2 migration utility

Converts a legacy plans/tasks.json file into per-checkpoint tasks/[CP-ID].md files
in the Session 3 format expected by /io-orchestrate and /io-execute.

Usage:
    uv run python .agent/scripts/tasks_json_to_md.py

    # Dry run (preview output without writing):
    uv run python .agent/scripts/tasks_json_to_md.py --dry-run

    # Custom input/output paths:
    uv run python .agent/scripts/tasks_json_to_md.py --input plans/tasks.json --output-dir tasks/

Notes:
    - The converter produces best-effort task files. Gate commands and context files
      should be reviewed and completed manually after conversion.
    - Fields not present in tasks.json (e.g., connectivity tests, protocol file) are
      marked with [REQUIRED: fill in] placeholders.
    - Original tasks.json is not modified or deleted.
"""

import argparse
import json
import sys
from pathlib import Path


PLACEHOLDER = "[REQUIRED: fill in]"


def load_tasks_json(path: Path) -> list[dict]:
    """Load and normalize tasks.json — handles both list and {tasks: [...]} formats."""
    with open(path) as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "tasks" in data:
        return data["tasks"]
    raise ValueError(f"Unrecognized tasks.json format in {path}. Expected list or {{tasks: [...]}}.")


def infer_checkpoint_id(task: dict, index: int) -> str:
    """Derive a checkpoint ID from the task's id field or fall back to index."""
    task_id = task.get("id") or task.get("task_id") or ""
    # e.g. CP_1.1 -> CP-01, CP_2 -> CP-02, task-001 -> CP-01
    if task_id.startswith("CP_"):
        parts = task_id.replace("CP_", "").split(".")
        return f"CP-{int(parts[0]):02d}"
    return f"CP-{index + 1:02d}"


def group_by_checkpoint(tasks: list[dict]) -> dict[str, list[dict]]:
    """Group tasks by their checkpoint ID."""
    groups: dict[str, list[dict]] = {}
    for i, task in enumerate(tasks):
        cp_id = infer_checkpoint_id(task, i)
        groups.setdefault(cp_id, []).append(task)
    return groups


def format_task_file(cp_id: str, tasks: list[dict]) -> str:
    """Render a tasks/[CP-ID].md file from a group of legacy tasks."""

    # Collect write_targets and context_files across all tasks in the checkpoint
    write_targets = []
    context_files = []
    for task in tasks:
        for wt in task.get("write_targets", []):
            if wt not in write_targets:
                write_targets.append(wt)
        for cf in task.get("context_files", []):
            if cf not in context_files:
                context_files.append(cf)

    # Derive checkpoint name from first task description
    first_desc = tasks[0].get("description") or tasks[0].get("name") or cp_id

    # Infer a gate command from write_targets if not present
    test_targets = [wt for wt in write_targets if "test" in wt.lower()]
    if test_targets:
        gate_command = f"pytest {test_targets[0]}"
    else:
        gate_command = PLACEHOLDER

    lines = [
        f"# Task: {cp_id} — {first_desc}",
        "",
        "## Objective",
        f"{first_desc}",
        "",
        "## Contract",
        f"Protocol: {PLACEHOLDER}",
        "Read the protocol before writing any code. Build against it exactly.",
        "",
        "## Write Targets",
    ]

    if write_targets:
        for wt in write_targets:
            lines.append(f"- `{wt}`")
    else:
        lines.append(f"- {PLACEHOLDER}")

    lines += [
        "",
        "## Context Files (read-only)",
    ]

    if context_files:
        for cf in context_files:
            lines.append(f"- `{cf}`")
    else:
        lines.append(f"- {PLACEHOLDER}")

    lines += [
        "",
        "## Connectivity Tests to Keep Green",
        f"- {PLACEHOLDER}",
        "",
        "## Execution Protocol",
        "",
        "Follow Red-Green-Refactor strictly:",
        "",
    ]

    # Render individual tasks as numbered steps
    for i, task in enumerate(tasks, 1):
        task_type = task.get("type", "unknown")
        task_desc = task.get("description") or task.get("name") or f"Step {i}"
        task_gate = task.get("gate_command") or ""

        lines.append(f"### Step {i}: [{task_type.upper()}] {task_desc}")
        if task_gate:
            lines.append(f"Gate: `{task_gate}`")
        lines.append("")

    lines += [
        "## Gate Command",
        f"`{gate_command}`",
        "",
        "## Completion",
        "",
        "When all steps pass, write a single line to `../../tasks/{cp_id}.status`:".replace("{cp_id}", cp_id),
        "```",
        "PASS",
        "```",
        "",
        "If any step fails after 3 attempts, write:",
        "```",
        "FAIL: [one line describing what failed]",
        "```",
        "Then terminate.",
        "",
        "## Constraints",
        "- You have NO access to plan.md, roadmap.md, project-spec.md (beyond the CRC card noted above), or other task files",
        "- You may NOT write to any file not listed in Write Targets",
        "- You may NOT install dependencies — if a dependency is missing, write FAIL and terminate",
        "- You may NOT use `# noqa: DI` without a matching backlog entry — if you need it, write FAIL and terminate",
    ]

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert plans/tasks.json to tasks/[CP-ID].md files.")
    parser.add_argument("--input", default="plans/tasks.json", help="Path to tasks.json")
    parser.add_argument("--output-dir", default="tasks", help="Directory to write task files into")
    parser.add_argument("--dry-run", action="store_true", help="Preview output without writing files")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)

    if not input_path.exists():
        print(f"ERROR: {input_path} not found.", file=sys.stderr)
        sys.exit(1)

    print(f"Loading {input_path}...")
    tasks = load_tasks_json(input_path)
    print(f"  {len(tasks)} tasks found.")

    groups = group_by_checkpoint(tasks)
    print(f"  {len(groups)} checkpoint groups identified: {', '.join(groups.keys())}")

    if not args.dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

    for cp_id, cp_tasks in groups.items():
        content = format_task_file(cp_id, cp_tasks)
        out_path = output_dir / f"{cp_id}.md"

        if args.dry_run:
            print(f"\n{'='*60}")
            print(f"DRY RUN: {out_path}")
            print('='*60)
            print(content)
        else:
            out_path.write_text(content, encoding="utf-8")
            print(f"  Written: {out_path}")

    if args.dry_run:
        print("\nDry run complete. No files written.")
    else:
        print(f"\nConversion complete. {len(groups)} task file(s) written to {output_dir}/")
        print("\nNext steps:")
        print("  1. Review each tasks/[CP-ID].md and fill in all [REQUIRED: fill in] placeholders")
        print("  2. Verify gate commands are correct pytest invocations")
        print("  3. Add protocol contract paths under '## Contract'")
        print("  4. Add connectivity test signatures under '## Connectivity Tests to Keep Green'")
        print("  5. Run /io-orchestrate to score the confidence rubric before dispatching")


if __name__ == "__main__":
    main()

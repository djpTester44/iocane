#!/usr/bin/env python3
"""Sync artifacts from .github/ to .agent/ with format-specific conversions.

Direction: .github/ -> .agent/ (one-way, additive only -- never deletes targets)

Mapping:
  .github/instructions/*.instructions.md -> .agent/rules/*.md
  .github/prompts/*.prompt.md            -> .agent/workflows/*.md
  .github/skills/*/                      -> .agent/skills/*/
  .github/scripts/*                      -> .agent/scripts/*
  .github/templates/*                    -> .agent/templates/*
  .github/<loose files>                  -> .agent/<loose files>
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Exclusions
# ---------------------------------------------------------------------------
EXCLUDED_PROMPTS = {"sync-agent.prompt.md"}

EXCLUDED_INSTRUCTIONS: set[str] = set()
AGENT_RULES_SKIP: set[str] = set()

# Sync scripts are maintained independently per directory -- never overwrite
EXCLUDED_SCRIPTS = {"github_to_agent_sync.py", "agent_to_github_sync.py"}

EXCLUDED_SKILL_DIRS = {"_templates"}

# GitHub-reserved filenames that should prompt the user before copying
GITHUB_RESERVED = {"FUNDING.yml", "CODEOWNERS", "dependabot.yml", "SECURITY.md"}

KNOWN_SUBDIRS = {"instructions", "prompts", "skills", "scripts", "templates"}


def _matches_filter(name: str, targets: set[str] | None) -> bool:
    """Return True if name (or its stem) matches the target filter.

    Strips known suffixes (.instructions, .prompt) before matching.
    If targets is None, everything matches (no filter).
    """
    if targets is None:
        return True
    stem = name
    for suffix in (".instructions.md", ".prompt.md", ".md"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    return stem in targets or name in targets


@dataclass
class SyncStats:
    """Track sync results for a single artifact type."""

    checked: int = 0
    already_synced: int = 0
    created: int = 0
    updated: int = 0
    errors: int = 0
    created_files: list[str] = field(default_factory=lambda: [])
    updated_files: list[str] = field(default_factory=lambda: [])
    error_messages: list[str] = field(default_factory=lambda: [])


# ---------------------------------------------------------------------------
# Frontmatter helpers
# ---------------------------------------------------------------------------
_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Return (frontmatter_dict, body) from a markdown file's text."""
    m = _FM_RE.match(text)
    if not m:
        return {}, text
    raw = m.group(1)
    body = text[m.end() :]
    fm: dict[str, str] = {}
    for line in raw.splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            fm[key.strip()] = val.strip()
    return fm, body


def build_frontmatter(fields: dict[str, str]) -> str:
    """Render a YAML frontmatter block from key-value pairs."""
    lines = ["---"]
    for k, v in fields.items():
        lines.append(f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Conversion: Instructions -> Rules
# ---------------------------------------------------------------------------


def convert_instruction_to_rule(text: str) -> str:
    """Convert .github/instructions format to .agent/rules format.

    Frontmatter changes:
      - applyTo: '{pattern}' -> trigger: glob + globs: {pattern}
      - applyTo: '**' (catch-all) -> trigger: always_on + globs: **
      - No applyTo -> trigger: always_on (no globs)
      - description: kept as-is
      - Remove any other github-specific fields

    Body changes:
      - Remove '> Inherits: ...' lines
    """
    fm, body = parse_frontmatter(text)

    new_fm: dict[str, str] = {}

    apply_to = fm.get("applyTo", "").strip("'\"")

    if apply_to:
        if apply_to == "**":
            new_fm["trigger"] = "always_on"
        else:
            new_fm["trigger"] = "glob"
    else:
        new_fm["trigger"] = "always_on"

    # Description always comes after trigger
    if "description" in fm:
        new_fm["description"] = fm["description"]

    # Globs come last (only if a pattern exists)
    if apply_to:
        new_fm["globs"] = apply_to

    # Remove Inherits lines from body
    body = re.sub(r"^> Inherits:.*\n?", "", body, flags=re.MULTILINE)
    # Clean up any resulting double blank lines
    body = re.sub(r"\n{3,}", "\n\n", body)

    result = build_frontmatter(new_fm) + body
    if not result.endswith("\n"):
        result += "\n"
    return result


# ---------------------------------------------------------------------------
# Conversion: Prompts -> Workflows
# ---------------------------------------------------------------------------


def convert_prompt_to_workflow(text: str) -> str:
    """Convert .github/prompts format to .agent/workflows format.

    Frontmatter changes:
      - Remove 'name:' field
      - Keep 'description:' as-is

    Body changes: None.
    """
    fm, body = parse_frontmatter(text)

    new_fm: dict[str, str] = {}
    if "description" in fm:
        new_fm["description"] = fm["description"]

    result = build_frontmatter(new_fm) + body
    if not result.endswith("\n"):
        result += "\n"
    return result


# ---------------------------------------------------------------------------
# Sync logic
# ---------------------------------------------------------------------------


def sync_rules(
    github_dir: Path,
    agent_dir: Path,
    *,
    dry_run: bool = False,
    targets: set[str] | None = None,
) -> SyncStats:
    """Sync .github/instructions/ -> .agent/rules/."""
    stats = SyncStats()
    src = github_dir / "instructions"
    dst = agent_dir / "rules"

    if not src.is_dir():
        return stats

    dst.mkdir(parents=True, exist_ok=True)

    for src_file in sorted(src.glob("*.instructions.md")):
        if not _matches_filter(src_file.name, targets):
            continue
        stats.checked += 1
        # Compute target name: strip .instructions suffix
        stem = src_file.name
        if stem.endswith(".instructions.md"):
            target_name = stem.replace(".instructions.md", ".md")
        else:
            target_name = stem

        if target_name in AGENT_RULES_SKIP:
            stats.already_synced += 1
            continue

        dst_file = dst / target_name

        try:
            content = src_file.read_text(encoding="utf-8")
            converted = convert_instruction_to_rule(content)

            if dst_file.exists():
                existing = dst_file.read_text(encoding="utf-8")
                if existing == converted:
                    stats.already_synced += 1
                    continue
                if not dry_run:
                    dst_file.write_text(converted, encoding="utf-8")
                stats.updated += 1
                stats.updated_files.append(
                    dst_file.relative_to(agent_dir.parent).as_posix()
                )
            else:
                if not dry_run:
                    dst_file.write_text(converted, encoding="utf-8")
                stats.created += 1
                stats.created_files.append(
                    dst_file.relative_to(agent_dir.parent).as_posix()
                )
        except Exception as e:
            stats.errors += 1
            stats.error_messages.append(f"{src_file.name}: {e}")

    return stats


def sync_workflows(
    github_dir: Path,
    agent_dir: Path,
    *,
    dry_run: bool = False,
    targets: set[str] | None = None,
) -> SyncStats:
    """Sync .github/prompts/ -> .agent/workflows/."""
    stats = SyncStats()
    src = github_dir / "prompts"
    dst = agent_dir / "workflows"

    if not src.is_dir():
        return stats

    dst.mkdir(parents=True, exist_ok=True)

    for src_file in sorted(src.glob("*.prompt.md")):
        if src_file.name in EXCLUDED_PROMPTS:
            continue
        if not _matches_filter(src_file.name, targets):
            continue

        stats.checked += 1
        target_name = src_file.name.replace(".prompt.md", ".md")

        dst_file = dst / target_name

        try:
            content = src_file.read_text(encoding="utf-8")
            converted = convert_prompt_to_workflow(content)

            if dst_file.exists():
                existing = dst_file.read_text(encoding="utf-8")
                if existing == converted:
                    stats.already_synced += 1
                    continue
                if not dry_run:
                    dst_file.write_text(converted, encoding="utf-8")
                stats.updated += 1
                stats.updated_files.append(
                    dst_file.relative_to(agent_dir.parent).as_posix()
                )
            else:
                if not dry_run:
                    dst_file.write_text(converted, encoding="utf-8")
                stats.created += 1
                stats.created_files.append(
                    dst_file.relative_to(agent_dir.parent).as_posix()
                )
        except Exception as e:
            stats.errors += 1
            stats.error_messages.append(f"{src_file.name}: {e}")

    return stats


def sync_skills(
    github_dir: Path,
    agent_dir: Path,
    *,
    dry_run: bool = False,
    targets: set[str] | None = None,
) -> SyncStats:
    """Sync .github/skills/ -> .agent/skills/ (as-is copy)."""
    stats = SyncStats()
    src = github_dir / "skills"
    dst = agent_dir / "skills"

    if not src.is_dir():
        return stats

    dst.mkdir(parents=True, exist_ok=True)

    for skill_dir in sorted(src.iterdir()):
        if not skill_dir.is_dir():
            continue
        if skill_dir.name in EXCLUDED_SKILL_DIRS:
            continue
        if not _matches_filter(skill_dir.name, targets):
            continue

        stats.checked += 1
        dst_skill = dst / skill_dir.name

        if not dst_skill.exists():
            try:
                if not dry_run:
                    shutil.copytree(skill_dir, dst_skill)
                stats.created += 1
                stats.created_files.append(
                    dst_skill.relative_to(agent_dir.parent).as_posix() + "/"
                )
            except Exception as e:
                stats.errors += 1
                stats.error_messages.append(f"{skill_dir.name}: {e}")
            continue

        # Directory exists -- walk individual files for content comparison
        any_diff = False
        try:
            for src_file in sorted(skill_dir.rglob("*")):
                if src_file.is_dir():
                    continue
                rel = src_file.relative_to(skill_dir)
                dst_file = dst_skill / rel
                if dst_file.exists() and dst_file.read_bytes() == src_file.read_bytes():
                    continue
                any_diff = True
                if not dry_run:
                    dst_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_file, dst_file)
            if any_diff:
                stats.updated += 1
                stats.updated_files.append(
                    dst_skill.relative_to(agent_dir.parent).as_posix() + "/"
                )
            else:
                stats.already_synced += 1
        except Exception as e:
            stats.errors += 1
            stats.error_messages.append(f"{skill_dir.name}: {e}")

    return stats


def sync_direct_copy(
    github_dir: Path,
    agent_dir: Path,
    subdir: str,
    *,
    dry_run: bool = False,
    targets: set[str] | None = None,
    excluded: set[str] | None = None,
) -> SyncStats:
    """Sync a subdirectory via direct copy (scripts, templates)."""
    stats = SyncStats()
    src = github_dir / subdir
    dst = agent_dir / subdir

    if not src.is_dir():
        return stats

    dst.mkdir(parents=True, exist_ok=True)

    for src_file in sorted(src.iterdir()):
        if src_file.is_dir():
            continue
        if src_file.suffix == ".zip":
            continue
        if excluded and src_file.name in excluded:
            continue
        if not _matches_filter(src_file.name, targets):
            continue

        stats.checked += 1
        dst_file = dst / src_file.name

        try:
            if dst_file.exists():
                if dst_file.read_bytes() == src_file.read_bytes():
                    stats.already_synced += 1
                    continue
                if not dry_run:
                    shutil.copy2(src_file, dst_file)
                stats.updated += 1
                stats.updated_files.append(
                    dst_file.relative_to(agent_dir.parent).as_posix()
                )
            else:
                if not dry_run:
                    shutil.copy2(src_file, dst_file)
                stats.created += 1
                stats.created_files.append(
                    dst_file.relative_to(agent_dir.parent).as_posix()
                )
        except Exception as e:
            stats.errors += 1
            stats.error_messages.append(f"{src_file.name}: {e}")

    return stats


def sync_loose_files(
    github_dir: Path,
    agent_dir: Path,
    *,
    dry_run: bool = False,
    targets: set[str] | None = None,
) -> SyncStats:
    """Sync loose files from .github/ root -> .agent/ root."""
    stats = SyncStats()

    for src_file in sorted(github_dir.iterdir()):
        if src_file.is_dir():
            continue
        if src_file.suffix == ".zip":
            continue
        if src_file.name.startswith("archive."):
            continue
        if not _matches_filter(src_file.name, targets):
            continue

        stats.checked += 1
        dst_file = agent_dir / src_file.name

        if src_file.name in GITHUB_RESERVED:
            stats.errors += 1
            stats.error_messages.append(
                f"{src_file.name}: SKIPPED - GitHub-reserved filename (needs user approval)"
            )
            continue

        try:
            if dst_file.exists():
                if dst_file.read_bytes() == src_file.read_bytes():
                    stats.already_synced += 1
                    continue
                if not dry_run:
                    shutil.copy2(src_file, dst_file)
                stats.updated += 1
                stats.updated_files.append(
                    dst_file.relative_to(agent_dir.parent).as_posix()
                )
            else:
                if not dry_run:
                    shutil.copy2(src_file, dst_file)
                stats.created += 1
                stats.created_files.append(
                    dst_file.relative_to(agent_dir.parent).as_posix()
                )
        except Exception as e:
            stats.errors += 1
            stats.error_messages.append(f"{src_file.name}: {e}")

    return stats


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def print_report(results: dict[str, SyncStats]) -> None:
    """Print a markdown-formatted summary table."""
    print("\n## Sync Results (.github -> .agent)\n")
    print("| Type | Checked | Synced | Updated | Created | Errors |")
    print("|------|---------|--------|---------|---------|--------|")
    for label, s in results.items():
        print(
            f"| {label} | {s.checked} | {s.already_synced} "
            f"| {s.updated} | {s.created} | {s.errors} |"
        )

    updated = [f for s in results.values() for f in s.updated_files]
    if updated:
        print("\n### Updated Files")
        for f in updated:
            print(f"- `{f}`")

    created = [f for s in results.values() for f in s.created_files]
    if created:
        print("\n### Created Files")
        for f in created:
            print(f"- `{f}`")

    errors = [msg for s in results.values() for msg in s.error_messages]
    if errors:
        print("\n### Errors")
        for msg in errors:
            print(f"- {msg}")
    else:
        print("\n### Errors\n- (none)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync .github/ -> .agent/ (one-way, additive)"
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Project root containing .github/ and .agent/ directories",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing files",
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="Optional file stems to sync (e.g. 'execution audit code-optimizer'). "
        "Omit to sync everything.",
    )
    args = parser.parse_args()

    github_dir = args.root / ".github"
    agent_dir = args.root / ".agent"

    if not github_dir.is_dir():
        print(f"ERROR: {github_dir} not found", file=sys.stderr)
        sys.exit(1)

    agent_dir.mkdir(exist_ok=True)

    targets: set[str] | None = set(args.files) if args.files else None

    if args.dry_run:
        print("** DRY RUN -- no files will be written **\n")
    if targets:
        print(f"Filtering to: {', '.join(sorted(targets))}\n")

    results: dict[str, SyncStats] = {
        "Rules": sync_rules(
            github_dir, agent_dir, dry_run=args.dry_run, targets=targets
        ),
        "Workflows": sync_workflows(
            github_dir, agent_dir, dry_run=args.dry_run, targets=targets
        ),
        "Skills": sync_skills(
            github_dir, agent_dir, dry_run=args.dry_run, targets=targets
        ),
        "Scripts": sync_direct_copy(
            github_dir,
            agent_dir,
            "scripts",
            dry_run=args.dry_run,
            targets=targets,
            excluded=EXCLUDED_SCRIPTS,
        ),
        "Templates": sync_direct_copy(
            github_dir, agent_dir, "templates", dry_run=args.dry_run, targets=targets
        ),
        "Loose Files": sync_loose_files(
            github_dir, agent_dir, dry_run=args.dry_run, targets=targets
        ),
    }

    print_report(results)


if __name__ == "__main__":
    main()

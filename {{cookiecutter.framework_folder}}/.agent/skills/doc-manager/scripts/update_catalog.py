"""
Catalog Generator - Sweeps .github directory to generate a central CATALOG.md.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

ROOT_DIR = Path(__file__).resolve().parents[4]
GITHUB_DIR = ROOT_DIR / ".github"
CATALOG_FILE = GITHUB_DIR / "CATALOG.md"


def parse_frontmatter(content: str) -> dict[str, Any]:
    """Parse YAML frontmatter from markdown content."""
    match = re.search(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}
    try:
        return yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return {}


def get_skills() -> list[dict]:
    """Collect all skills from the skills directory."""
    skills = []
    skills_dir = GITHUB_DIR / "skills"
    if not skills_dir.exists():
        return []
    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            continue
        data = parse_frontmatter(skill_file.read_text(encoding="utf-8"))
        skills.append(
            {
                "name": data.get("name", skill_dir.name),
                "description": data.get("description", "No description"),
                "path": f"skills/{skill_dir.name}/SKILL.md",
            }
        )
    return skills


def get_prompts() -> list[dict]:
    """Collect all prompts from the prompts directory."""
    prompts = []
    prompts_dir = GITHUB_DIR / "prompts"
    if not prompts_dir.exists():
        return []
    for prompt_file in sorted(prompts_dir.glob("*.md")):
        data = parse_frontmatter(prompt_file.read_text(encoding="utf-8"))
        prompts.append(
            {
                "name": prompt_file.stem,
                "description": data.get("description", "No description"),
                "path": f"prompts/{prompt_file.name}",
            }
        )
    return prompts


def get_instructions() -> list[dict]:
    """Collect all instructions from the instructions directory."""
    instructions = []
    instructions_dir = GITHUB_DIR / "instructions"
    if not instructions_dir.exists():
        return []
    for instruction_file in sorted(instructions_dir.glob("*.md")):
        data = parse_frontmatter(instruction_file.read_text(encoding="utf-8"))
        instructions.append(
            {
                "name": instruction_file.stem,
                "description": data.get("description", "No description"),
                "applyTo": data.get("applyTo", "*"),
                "path": f"instructions/{instruction_file.name}",
            }
        )
    return instructions


def generate_catalog() -> None:
    """Generate the CATALOG.md file."""
    skills = get_skills()
    prompts = get_prompts()
    instructions = get_instructions()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = [
        "# Agent Catalog",
        "",
        f"Last Updated: {timestamp}",
        "",
        "## Skills",
        "",
        "| Name | Description |",
        "|------|-------------|",
    ]
    for s in skills:
        link = f"[{s['name']}]({s['path']})"
        lines.append(f"| {link} | {s['description'][:80]}... |")

    lines.extend(
        ["", "## Prompts", "", "| Name | Description |", "|------|-------------|"]
    )
    for p in prompts:
        link = f"[{p['name']}]({p['path']})"
        lines.append(f"| {link} | {p['description'][:80]}... |")

    lines.extend(
        [
            "",
            "## Instructions",
            "",
            "| Name | ApplyTo | Description |",
            "|------|---------|-------------|",
        ]
    )
    for i in instructions:
        link = f"[{i['name']}]({i['path']})"
        lines.append(f"| {link} | {i['applyTo']} | {i['description'][:60]}... |")

    lines.append("")
    CATALOG_FILE.write_text("\n".join(lines), encoding="utf-8")
    print(f"Catalog updated: {CATALOG_FILE}")


if __name__ == "__main__":
    generate_catalog()

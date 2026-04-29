#!/usr/bin/env python3
"""Compose a run-state snapshot from a host-authored draft plus mechanical enumeration.

Reasoning-tier sections (1, 8, 9) come from the YAML draft the host
agent fills before invocation. Mechanical-enumeration sections (3, 5, 6
universal; 2, 4, 7 io-architect-specific) come from glob/stat over
``.iocane/`` and ``plans/``, plus a subprocess call to
``.claude/scripts/capability.py list-active --json``.

Section ordering is exposed as the module-level constants
``SECTIONS_GENERIC`` and ``SECTIONS_IO_ARCHITECT``.
``/HARNESS-remediation-analyze`` references these constants by name
during dump-absorption to detect schema drift.

Usage::

    uv run python .claude/scripts/compose_run_state.py \\
        --draft .iocane/drafts/run-state-draft.yaml \\
        --output .iocane/findings/<datestamp>_<workflow>-state.md \\
        --workflow {generic|io-architect}
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

# ---------------------------------------------------------------------------
# Draft schema (reasoning-tier sections 1 / 8 / 9)
# ---------------------------------------------------------------------------


class AnomalyEntry(BaseModel):
    """One categorical anomaly observation in section 8."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    label: str
    qualifier: str | None = None
    body: str


class AgentDecision(BaseModel):
    """One deliberated-or-reflexive agent decision in section 10.

    Captures choices the agent made that downstream remediation passes
    would otherwise have to infer from artifact shapes. Per AGENTS.md
    2026-04-27 lesson: the cost of inferring wrong is multi-week
    plan-revision cascade; capturing intent at snapshot time is cheap.
    The ``deliberated`` flag matters most -- a "reflexive default"
    entry is the harness team's signal that the option space wasn't
    actually evaluated.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")
    choice: str
    alternatives_considered: list[str] = Field(default_factory=list)
    reasoning: str
    deliberated: bool = True


class RunStateDraft(BaseModel):
    """Host-authored draft input for ``compose_run_state.py``."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    workflow_label: str
    generated_note: str | None = None
    run_state: list[str] = Field(default_factory=list)
    anomalies: list[AnomalyEntry] = Field(default_factory=list)
    recommended_continuation: list[str] = Field(default_factory=list)
    agent_decisions: list[AgentDecision] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Section type
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Section:
    """A single rendered section of the snapshot."""

    number: int
    title: str
    render: Callable[[RunStateDraft, pathlib.Path], str]


# ---------------------------------------------------------------------------
# Reasoning-tier renderers (universal; data from draft)
# ---------------------------------------------------------------------------


def render_run_state(draft: RunStateDraft, repo_root: pathlib.Path) -> str:
    if not draft.run_state:
        body = "_(no entries)_"
    else:
        body = "\n".join(f"- {line}" for line in draft.run_state)
    return f"## 1. Run state right now\n\n{body}\n"


def render_anomalies(draft: RunStateDraft, repo_root: pathlib.Path) -> str:
    if not draft.anomalies:
        return "## 8. Anomalies observed\n\n_(none)_\n"
    parts: list[str] = []
    for entry in draft.anomalies:
        head = f"**{entry.label}"
        if entry.qualifier:
            head += f" — {entry.qualifier}"
        head += ":**"
        parts.append(f"{head} {entry.body}")
    body = "\n\n".join(parts)
    return f"## 8. Anomalies observed\n\n{body}\n"


def render_continuation(draft: RunStateDraft, repo_root: pathlib.Path) -> str:
    if not draft.recommended_continuation:
        return "## 9. Recommended continuation sequence\n\n_(none)_\n"
    body = "\n".join(
        f"{i}. {item}" for i, item in enumerate(draft.recommended_continuation, 1)
    )
    return f"## 9. Recommended continuation sequence\n\n{body}\n"


def render_agent_decisions(
    draft: RunStateDraft, repo_root: pathlib.Path,
) -> str:
    if not draft.agent_decisions:
        return "## 10. Agent decisions\n\n_(none)_\n"
    parts: list[str] = []
    for entry in draft.agent_decisions:
        flag = "deliberated" if entry.deliberated else "reflexive default"
        head = f"**Choice ({flag}):** {entry.choice}"
        if entry.alternatives_considered:
            alts = ", ".join(f"`{a}`" for a in entry.alternatives_considered)
            head += f"\n\n_Alternatives considered:_ {alts}"
        else:
            head += "\n\n_Alternatives considered:_ none enumerated"
        head += f"\n\n_Reasoning:_ {entry.reasoning}"
        parts.append(head)
    body = "\n\n---\n\n".join(parts)
    return f"## 10. Agent decisions\n\n{body}\n"


# ---------------------------------------------------------------------------
# Mechanical-enumeration renderers (universal)
# ---------------------------------------------------------------------------


def _glob_with_stat(
    root: pathlib.Path, pattern: str,
) -> list[tuple[pathlib.Path, int]]:
    if not root.exists():
        return []
    return [
        (p, p.stat().st_size)
        for p in sorted(root.glob(pattern))
        if p.is_file()
    ]


def render_agent_scripts(draft: RunStateDraft, repo_root: pathlib.Path) -> str:
    iocane = repo_root / ".iocane"
    rows: list[tuple[pathlib.Path, int]] = []
    for sub in ("tmp", "_tmp"):
        rows.extend(_glob_with_stat(iocane / sub, "*.py"))
    if not rows:
        body = "_(none)_"
    else:
        lines = ["| Path | Bytes |", "|---|---|"]
        for path, size in rows:
            lines.append(f"| `{path.relative_to(repo_root)}` | {size} |")
        body = "\n".join(lines)
    return f"## 3. Agent-authored scripts under `.iocane/`\n\n{body}\n"


_DRAFT_SCRATCH_PATTERNS = ("*.json", "*.log", "*.txt", "*.yaml", "*.md")


def render_drafts(draft: RunStateDraft, repo_root: pathlib.Path) -> str:
    iocane = repo_root / ".iocane"
    rows: list[tuple[pathlib.Path, int]] = []
    for sub in ("tmp", "_tmp", "drafts"):
        for pattern in _DRAFT_SCRATCH_PATTERNS:
            rows.extend(_glob_with_stat(iocane / sub, pattern))
    if not rows:
        body = "_(none)_"
    else:
        lines = ["| Path | Bytes |", "|---|---|"]
        for path, size in sorted(set(rows)):
            lines.append(f"| `{path.relative_to(repo_root)}` | {size} |")
        body = "\n".join(lines)
    return f"## 5. Drafts / scratch\n\n{body}\n"


def render_capability(draft: RunStateDraft, repo_root: pathlib.Path) -> str:
    cap_script = repo_root / ".claude" / "scripts" / "capability.py"
    sid_path = repo_root / ".iocane" / "sessions" / ".current-session-id"
    sid = (
        sid_path.read_text(encoding="utf-8").strip()
        if sid_path.exists()
        else "(unknown)"
    )
    if not cap_script.exists():
        return (
            "## 6. Capability + session state\n\n"
            f"Session ID: `{sid}`\n\n"
            "_(capability.py not found at "
            "`.claude/scripts/capability.py` — no grant state to report)_\n"
        )
    try:
        result = subprocess.run(
            [
                sys.executable,
                str(cap_script),
                "list-active",
                "--json",
                "--repo-root",
                str(repo_root),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return (
            "## 6. Capability + session state\n\n"
            f"Session ID: `{sid}`\n\n"
            f"_(capability.py invocation failed: {exc})_\n"
        )
    payload = result.stdout.strip() or "[]"
    fenced = f"```json\n{payload}\n```"
    return (
        "## 6. Capability + session state\n\n"
        f"Session ID: `{sid}`\n\n"
        "Active grants (from "
        "`uv run python .claude/scripts/capability.py list-active --json`):\n\n"
        f"{fenced}\n"
    )


# ---------------------------------------------------------------------------
# Mechanical-enumeration renderers (workflow-specific: io-architect)
# ---------------------------------------------------------------------------

_CANONICAL_YAMLS: tuple[tuple[str, str, str], ...] = (
    ("Component contracts", "plans/component-contracts.yaml", "components"),
    ("Symbols registry", "plans/symbols.yaml", "symbols"),
    ("Seams", "plans/seams.yaml", "components"),
)


def _yaml_count(path: pathlib.Path, key: str) -> str:
    if not path.exists():
        return "(missing)"
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return "(unparseable)"
    container = data.get(key)
    if container is None:
        return "(empty)"
    if isinstance(container, (dict, list)):
        n = len(container)
    else:
        return "(unknown shape)"
    return f"{n} {key}"


def render_canonical_artifacts(
    draft: RunStateDraft, repo_root: pathlib.Path,
) -> str:
    rows = ["| Artifact | Path | Counts |", "|---|---|---|"]
    for label, rel, key in _CANONICAL_YAMLS:
        path = repo_root / rel
        rows.append(f"| {label} | `{rel}` | {_yaml_count(path, key)} |")
    return (
        "## 2. Canonical artifacts (current state)\n\n"
        + "\n".join(rows)
        + "\n"
    )


def render_findings(draft: RunStateDraft, repo_root: pathlib.Path) -> str:
    findings_dir = repo_root / ".iocane" / "findings"
    if not findings_dir.exists():
        return "## 4. Finding emissions through current cycle\n\n_(none)_\n"
    files = sorted(findings_dir.glob("evaluator_*.yaml"))
    if not files:
        return "## 4. Finding emissions through current cycle\n\n_(none)_\n"
    rows = ["| File | Bytes |", "|---|---|"]
    for f in files:
        rows.append(f"| `{f.relative_to(repo_root)}` | {f.stat().st_size} |")
    return (
        "## 4. Finding emissions through current cycle\n\n"
        + "\n".join(rows)
        + "\n"
    )


def render_step_g(draft: RunStateDraft, repo_root: pathlib.Path) -> str:
    tmp = repo_root / ".iocane" / "tmp"
    if not tmp.exists():
        return "## 7. Step G validator outputs\n\n_(none)_\n"
    stdout_files = sorted(tmp.glob("design-eval*.stdout.json"))
    stderr_files = sorted(tmp.glob("design-eval*.stderr.log"))
    if not stdout_files and not stderr_files:
        return "## 7. Step G validator outputs\n\n_(none)_\n"
    rows = ["| Path | Bytes |", "|---|---|"]
    for f in [*stdout_files, *stderr_files]:
        rows.append(f"| `{f.relative_to(repo_root)}` | {f.stat().st_size} |")
    return "## 7. Step G validator outputs\n\n" + "\n".join(rows) + "\n"


# ---------------------------------------------------------------------------
# Section ordering constants (referenced by-name from
# /HARNESS-remediation-analyze dump-absorption step)
# ---------------------------------------------------------------------------


SECTION_RUN_STATE = Section(1, "Run state right now", render_run_state)
SECTION_CANONICAL = Section(
    2, "Canonical artifacts (current state)", render_canonical_artifacts,
)
SECTION_AGENT_SCRIPTS = Section(
    3, "Agent-authored scripts under `.iocane/`", render_agent_scripts,
)
SECTION_FINDINGS = Section(
    4, "Finding emissions through current cycle", render_findings,
)
SECTION_DRAFTS = Section(5, "Drafts / scratch", render_drafts)
SECTION_CAPABILITY = Section(
    6, "Capability + session state", render_capability,
)
SECTION_STEP_G = Section(7, "Step G validator outputs", render_step_g)
SECTION_ANOMALIES = Section(8, "Anomalies observed", render_anomalies)
SECTION_CONTINUATION = Section(
    9, "Recommended continuation sequence", render_continuation,
)
SECTION_AGENT_DECISIONS = Section(
    10, "Agent decisions", render_agent_decisions,
)


SECTIONS_GENERIC: tuple[Section, ...] = (
    SECTION_RUN_STATE,
    SECTION_AGENT_SCRIPTS,
    SECTION_DRAFTS,
    SECTION_CAPABILITY,
    SECTION_ANOMALIES,
    SECTION_CONTINUATION,
    SECTION_AGENT_DECISIONS,
)


SECTIONS_IO_ARCHITECT: tuple[Section, ...] = (
    SECTION_RUN_STATE,
    SECTION_CANONICAL,
    SECTION_AGENT_SCRIPTS,
    SECTION_FINDINGS,
    SECTION_DRAFTS,
    SECTION_CAPABILITY,
    SECTION_STEP_G,
    SECTION_ANOMALIES,
    SECTION_CONTINUATION,
    SECTION_AGENT_DECISIONS,
)


WORKFLOWS: dict[str, tuple[Section, ...]] = {
    "generic": SECTIONS_GENERIC,
    "io-architect": SECTIONS_IO_ARCHITECT,
}


# ---------------------------------------------------------------------------
# Compose driver
# ---------------------------------------------------------------------------


def load_draft(path: pathlib.Path) -> RunStateDraft:
    """Load and validate the draft YAML; raise on failure."""
    if not path.exists():
        raise FileNotFoundError(f"draft path does not exist: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return RunStateDraft.model_validate(raw)


def resolve_repo_root() -> pathlib.Path:
    """Resolve the repo root via git, falling back to cwd."""
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        if out:
            return pathlib.Path(out).resolve()
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return pathlib.Path.cwd().resolve()


def compose(
    draft: RunStateDraft,
    sections: tuple[Section, ...],
    repo_root: pathlib.Path,
) -> str:
    """Render the full snapshot markdown from draft + sections."""
    header = f"# RUN-STATE SNAPSHOT — `{draft.workflow_label}`\n"
    if draft.generated_note:
        header += f"\nGenerated: {draft.generated_note}\n"
    header += "\n---\n\n"
    body = "\n---\n\n".join(s.render(draft, repo_root) for s in sections)
    return header + body


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draft", required=True, type=pathlib.Path)
    parser.add_argument("--output", required=True, type=pathlib.Path)
    parser.add_argument(
        "--workflow",
        default="generic",
        choices=sorted(WORKFLOWS.keys()),
        help="Section variant to render (default: generic).",
    )
    parser.add_argument(
        "--repo-root",
        type=pathlib.Path,
        default=None,
        help="Repo root for mechanical sections (default: git rev-parse).",
    )
    args = parser.parse_args(argv)

    try:
        draft = load_draft(args.draft)
    except FileNotFoundError as exc:
        sys.stderr.write(f"ERROR: {exc}\n")
        return 1
    except ValidationError as exc:
        sys.stderr.write(f"ERROR: draft validation failed:\n{exc}\n")
        return 1
    except yaml.YAMLError as exc:
        sys.stderr.write(f"ERROR: draft YAML parse failed:\n{exc}\n")
        return 1

    repo_root = (
        args.repo_root.resolve() if args.repo_root else resolve_repo_root()
    )
    sections = WORKFLOWS[args.workflow]

    output_text = compose(draft, sections, repo_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(output_text, encoding="utf-8")
    sys.stdout.write(
        f"compose_run_state: wrote {args.output} ({len(sections)} sections)\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

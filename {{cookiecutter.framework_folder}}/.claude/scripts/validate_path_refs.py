"""validate_path_refs.py

Appendix A §A.6 -- file-reference resolvability gate.

Extracts file-path-like strings from spec artifacts via ripgrep and verifies
each resolves to one of:

  (a) an existing file on disk,
  (b) a CP ``write_target`` in ``plans/plan.yaml`` (or any upstream artifact's
      declared outputs), or
  (c) a CP's ``relies_on_existing`` list.

Unresolved paths emit ``WARN:`` lines at OBSERVATION severity on stderr.
The script always exits 0 -- findings are non-blocking and surfaced by
``/io-architect`` Step I-3 and ``/validate-plan`` Step 9D without halting
the workflow.

Extension-anchored patterns keep the match set biased toward false
negatives per A.6a: matching an occasional non-path that happens to end in
``.py``/``.md`` is cheaper than missing a real drift, but flooding on URLs
and dotted attributes is worse than silent under-coverage. The pattern
deliberately excludes URL schemes and bare unversioned extensions without
any path structure.

Exit codes:
  0 -- always (non-blocking).

Usage:
    uv run python .claude/scripts/validate_path_refs.py --stage architect
    uv run python .claude/scripts/validate_path_refs.py --stage validate-plan
"""

import argparse
import logging
import subprocess
import sys
from pathlib import Path

from plan_parser import load_plan

logger = logging.getLogger(__name__)

# A.6a -- extension-anchored pattern. Matches word/dot/slash/dash runs ending
# in a known spec-artifact extension. Tuning is intentionally conservative:
# adding new extensions here (biasing toward more matches) is cheaper than
# broadening the character class (which invites URL and signature noise).
RG_PATTERN = r"[\w./-]+\.(?:py|pyi|yaml|toml|md|json|html|txt|csv)\b"

# Spec artifacts scanned at both stages. Order is stable so warning output
# is deterministic.
BASE_ARTIFACTS: tuple[str, ...] = (
    "plans/PRD.md",
    "plans/roadmap.md",
    "plans/project-spec.md",
    "plans/component-contracts.yaml",
    "plans/seams.yaml",
)

PLAN_ARTIFACT = "plans/plan.yaml"

# URL fragment marker. Any match that contains "://" was extracted mid-URL;
# rg's character class filter can't anticipate every URL form, so we drop
# these post-match.
URL_MARKER = "://"


def _normalize(path: str) -> str:
    """Collapse a raw path string to the canonical form used for matching.

    Converts backslashes to forward slashes (Windows tolerance) and strips
    a single leading ``./`` segment. Does not resolve relative traversal --
    matches that already contain ``..`` are compared verbatim.
    """
    p = path.replace("\\", "/")
    if p.startswith("./"):
        p = p[2:]
    return p


def extract_path_refs(
    artifacts: list[Path],
) -> list[tuple[Path, int, str]]:
    """Run ripgrep over each artifact and return extracted (source, line, match).

    Returns an empty list if ``rg`` is unavailable (FileNotFoundError) so the
    gate stays non-blocking.
    """
    results: list[tuple[Path, int, str]] = []
    for path in artifacts:
        if not path.exists():
            continue
        try:
            proc = subprocess.run(
                [
                    "rg",
                    "--no-heading",
                    "--with-filename",
                    "--line-number",
                    "--only-matching",
                    RG_PATTERN,
                    str(path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            sys.stderr.write(
                "WARN: ripgrep (rg) not available -- path-reference gate "
                "skipped. Install rg to enable Appendix A §A.6 coverage.\n",
            )
            return []
        # rg exits 1 when no matches; both 0 and 1 are expected.
        if proc.returncode not in (0, 1):
            sys.stderr.write(
                f"WARN: rg failed on {path}: {proc.stderr.strip()}\n",
            )
            continue
        for raw_line in proc.stdout.splitlines():
            # Output format: PATH:LINE:MATCH. On Windows, PATH may contain
            # colons from drive letters, so split from the right.
            parts = raw_line.rsplit(":", 2)
            if len(parts) != 3:
                continue
            source_str, line_str, match = parts
            if URL_MARKER in match:
                continue
            try:
                line_no = int(line_str)
            except ValueError:
                continue
            results.append((Path(source_str), line_no, match))
    return results


def build_reference_set(
    plan_path: Path,
) -> tuple[set[str], set[str]]:
    """Return (write_targets, relies_on_existing) sets from ``plan.yaml``.

    Returns empty sets when the plan is missing or fails to load. Callers
    must treat empty sets as "reference context unavailable" rather than
    "no references exist".
    """
    write_targets: set[str] = set()
    relies_on: set[str] = set()
    if not plan_path.exists():
        return write_targets, relies_on
    try:
        plan = load_plan(str(plan_path))
    except Exception as exc:  # noqa: BLE001 -- non-blocking validator
        sys.stderr.write(f"WARN: failed to load {plan_path}: {exc}\n")
        return write_targets, relies_on
    for cp in plan.checkpoints:
        for wt in cp.write_targets:
            write_targets.add(_normalize(wt))
        for rel in cp.relies_on_existing:
            relies_on.add(_normalize(rel))
    return write_targets, relies_on


def resolve(
    match: str,
    source: Path,
    write_targets: set[str],
    relies_on: set[str],
    repo_root: Path,
) -> bool:
    """Return True when the match resolves; False when it is unresolved.

    Resolution order mirrors A.6b:
      (a) exists on disk relative to ``repo_root``
      (b) declared as a CP ``write_target`` in plan.yaml
      (c) declared as a CP ``relies_on_existing`` entry

    Self-references (a spec artifact naming its own path) are always
    resolved -- they cannot be orphaned against themselves.
    """
    norm = _normalize(match)
    if not norm:
        return True
    if (repo_root / norm).exists():
        return True
    if norm in write_targets:
        return True
    if norm in relies_on:
        return True
    return norm == _normalize(str(source)) or norm == source.name


def main(argv: list[str] | None = None) -> int:
    """Entry point for the path-ref resolvability gate."""
    parser = argparse.ArgumentParser(
        description=(
            "Appendix A §A.6 file-reference resolvability gate. "
            "Extension-anchored ripgrep extraction + plan.yaml reference "
            "set. Non-blocking -- always exits 0."
        ),
    )
    parser.add_argument(
        "--stage",
        choices=["architect", "validate-plan"],
        required=True,
        help=(
            "Invocation stage. `architect` scans PRD/roadmap/project-spec/"
            "component-contracts/seams after Step H. `validate-plan` "
            "additionally scans plan.yaml and consults each CP's "
            "write_targets and relies_on_existing as the reference set."
        ),
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        type=Path,
        help="Repository root for filesystem-existence checks.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    repo_root = args.repo_root.resolve()

    artifacts: list[Path] = [repo_root / rel for rel in BASE_ARTIFACTS]
    plan_path = repo_root / PLAN_ARTIFACT
    if args.stage == "validate-plan":
        artifacts.append(plan_path)

    # Both stages consult plan.yaml when available; the architect stage
    # benefits from an incremental run where plan.yaml already exists.
    write_targets, relies_on = build_reference_set(plan_path)

    refs = extract_path_refs(artifacts)

    flagged = 0
    for source, line_no, match in refs:
        if resolve(match, source, write_targets, relies_on, repo_root):
            continue
        sys.stderr.write(
            f"WARN: {source.as_posix()}:{line_no} references unresolved "
            f"path '{match}' -- not on disk, not a plan write_target, "
            f"not in any relies_on_existing\n",
        )
        flagged += 1

    if flagged:
        sys.stderr.write(
            f"{flagged} unresolved path reference(s) flagged. "
            "Non-blocking -- OBSERVATION severity (A.6).\n",
        )
    else:
        sys.stdout.write(
            "PASS: all extracted path references resolve to filesystem, "
            "write_targets, or relies_on_existing.\n",
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())

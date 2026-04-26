"""Shared write-path for Finding emission to .iocane/findings/.

Centralizes the on-disk filename pattern, sequence disambiguation, and
Pydantic-validated YAML serialization so every Finding emitter (design
evaluator today; CDT/CT semantic evaluators in A5/A6) hits one canonical
write path.

Filename pattern: ``<role>-<UTC YYYYMMDDTHHMMSS>-<NNN>.yaml``. Sequence
NNN is derived from the directory listing at write time -- next integer
above the highest matching <role>-<timestamp>-<NNN>.yaml in the
directory. Singleton-correct in the architect-subprocess context (one
spawn at a time per io-architect Step H 5-cycle bound).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

import yaml
from schemas import Finding, FindingFile

_FINDINGS_SUBDIR = ".iocane/findings"
_SEQUENCE_RE = re.compile(r"^(?P<role>[a-z_]+)-\d{8}T\d{6}-(?P<seq>\d{3})\.yaml$")


def _next_sequence(directory: Path, role_value: str) -> int:
    """Return the next sequence integer for ``role_value`` in ``directory``.

    Scans existing ``<role>-<timestamp>-<NNN>.yaml`` filenames; returns
    the maximum NNN + 1, or 1 if no matching files exist.
    """
    if not directory.exists():
        return 1
    max_seq = 0
    for entry in directory.iterdir():
        if not entry.is_file():
            continue
        match = _SEQUENCE_RE.match(entry.name)
        if match is None:
            continue
        if match.group("role") != role_value:
            continue
        seq = int(match.group("seq"))
        max_seq = max(max_seq, seq)
    return max_seq + 1


def emit_finding(finding: Finding, repo_root: Path | None = None) -> Path:
    """Serialize ``finding`` to a fresh file under ``.iocane/findings/``.

    The function constructs a single-finding ``FindingFile`` container,
    round-trips it through Pydantic to enforce the schema invariants,
    and writes the validated YAML to a unique path. The directory is
    created lazily.

    Args:
        finding: The Finding instance to persist. Already validated by
            its own model construction; the FindingFile wrapper adds
            the container-level non-empty check.
        repo_root: Optional explicit repository root. Defaults to the
            current working directory (callers running under
            ``IOCANE_REPO_ROOT`` should resolve and pass that path
            explicitly to keep emission worktree-correct).

    Returns:
        The absolute path of the file written.
    """
    root = (repo_root or Path.cwd()).resolve()
    directory = root / _FINDINGS_SUBDIR
    directory.mkdir(parents=True, exist_ok=True)
    role_value = finding.role.value
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    seq = _next_sequence(directory, role_value)
    filename = f"{role_value}-{timestamp}-{seq:03d}.yaml"
    path = directory / filename
    container = FindingFile(findings=[finding])
    payload = yaml.safe_dump(
        container.model_dump(mode="json"),
        sort_keys=False,
        allow_unicode=True,
    )
    path.write_text(payload, encoding="utf-8")
    return path

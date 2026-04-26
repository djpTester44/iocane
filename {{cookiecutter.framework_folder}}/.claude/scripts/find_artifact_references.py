"""Deterministic reference finder for harness artifact names.

Walks a file tree and emits every occurrence of a given anchor name (module,
class, skill, hook basename, enum value) classified by the structural region
it appears in. Each file type routes through a typed scanner so that hits
are grounded in parsed structure, not bare substring scanning:

* ``.py``  -- ``ast.walk`` for imports, names, attributes, and string
  constants; ``tokenize`` pass for comments.
* ``.md``  -- ``markdown_reference_parser`` classifies frontmatter,
  fenced code blocks, and body prose.
* ``.json`` -- ``json.loads`` validates structure; line-scan returns
  region as ``json_value`` (settings.json, hook command strings).
* ``.yaml`` / ``.yml`` -- ``yaml.safe_load`` validates structure;
  line-scan returns region as ``yaml_value``.
* ``.sh`` -- structured regex set for known reference forms (bash/python
  invocation paths, env-var role assignments, capability template names);
  fallback ``shell_mention`` when the token matches but no form does.

Word-boundary semantics: the search uses ``\\b<token>\\b`` with ``re.escape``
applied to the token, so ``seam_parser`` does NOT match inside
``seam_parser_extended`` and ``capability`` DOES match inside
``capability-covers`` (hyphen is a non-word character, so the boundary fires).
Dotted anchors (``RootCauseLayer.YAML_CONTRACT``) are supported via
``re.escape``.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
import tokenize
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml

# Resolve sibling imports both when run as __main__ and when imported.
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from markdown_reference_parser import parse_markdown  # noqa: E402

_DEFAULT_ROOTS: tuple[str, ...] = ("harness", "tests")
_SKIP_DIR_NAMES: frozenset[str] = frozenset(
    {".git", "__pycache__", ".iocane", ".venv", "node_modules", ".mypy_cache",
     ".pytest_cache", ".ruff_cache"},
)
# Self-skip: the finder and its own parser/tests describe the search, so any
# match in them is by construction not an artifact reference.
_SKIP_POSIX_SUFFIXES: tuple[str, ...] = (
    "harness/scripts/find_artifact_references.py",
    "harness/scripts/markdown_reference_parser.py",
    "tests/test_find_artifact_references.py",
    "tests/test_markdown_reference_parser.py",
)
# plans/ is the scrub plan + worktree audits -- it describes the artifacts
# being scrubbed and would drown the signal. Match anywhere in path parts.
_SKIP_DIR_PARTS: frozenset[str] = frozenset({"plans"})

_SHELL_FORM_PATTERNS: dict[str, re.Pattern[str]] = {
    "shell_bash_invocation": re.compile(
        r"bash\s+\S*\.claude/(?:hooks|scripts)/\S+",
    ),
    "shell_python_invocation": re.compile(
        r"uv\s+run\s+python\s+\S*\.claude/scripts/\S+",
    ),
    "shell_python_import": re.compile(
        r"(?:^|\s)(?:from\s+[\w.]+\s+import\s+[\w,\s*]+|import\s+[\w.]+)",
    ),
    "shell_env_role": re.compile(r"IOCANE_ROLE\s*[=:]\s*\S+"),
    "shell_template_name": re.compile(r"--template\s+\S+"),
}


@dataclass(frozen=True)
class ReferenceHit:
    """One occurrence of an artifact token within a file."""

    file_path: str
    line_number: int
    reference_kind: str
    line_text: str


def find_references(
    artifact: str, roots: list[Path],
) -> list[ReferenceHit]:
    """Scan ``roots`` for word-boundary occurrences of ``artifact``."""
    if not artifact:
        return []
    pattern = re.compile(r"\b" + re.escape(artifact) + r"\b")
    hits: list[ReferenceHit] = []
    for root in roots:
        for file in _iter_files(root):
            if _should_skip(file):
                continue
            hits.extend(_scan_file(file, pattern))
    hits.sort(key=lambda h: (h.file_path, h.line_number, h.reference_kind))
    return hits


def _iter_files(root: Path) -> list[Path]:
    """Yield files under ``root`` in stable order, skipping build dirs."""
    if root.is_file():
        return [root]
    if not root.is_dir():
        return []
    out: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in _SKIP_DIR_NAMES for part in path.parts):
            continue
        out.append(path)
    return out


def _should_skip(file: Path) -> bool:
    """Skip self, sibling parser, own tests, and anything under plans/."""
    posix = file.as_posix()
    if any(posix.endswith(sfx) for sfx in _SKIP_POSIX_SUFFIXES):
        return True
    return any(part in _SKIP_DIR_PARTS for part in file.parts)


def _scan_file(
    file: Path, pattern: re.Pattern[str],
) -> list[ReferenceHit]:
    """Dispatch to the appropriate per-extension scanner."""
    suffix = file.suffix.lower()
    if suffix == ".py":
        return _scan_python(file, pattern)
    if suffix == ".md":
        return _scan_markdown(file, pattern)
    if suffix == ".json":
        return _scan_json(file, pattern)
    if suffix in (".yaml", ".yml"):
        return _scan_yaml(file, pattern)
    if suffix == ".sh":
        return _scan_shell(file, pattern)
    return []


def _scan_python(
    file: Path, pattern: re.Pattern[str],
) -> list[ReferenceHit]:
    """AST walk + tokenize pass for comments."""
    try:
        source = file.read_text(encoding="utf-8")
    except OSError:
        return []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    rel = file.as_posix()
    lines = source.splitlines()
    hits: list[ReferenceHit] = []
    seen: set[tuple[int, str]] = set()

    for node in ast.walk(tree):
        for hit in _classify_python_node(node, pattern, rel, lines):
            key = (hit.line_number, hit.reference_kind)
            if key in seen:
                continue
            seen.add(key)
            hits.append(hit)

    for tok in _iter_py_comments(file):
        if not pattern.search(tok.string):
            continue
        ln = tok.start[0]
        line_text = lines[ln - 1] if 0 < ln <= len(lines) else tok.string
        key = (ln, "python_comment")
        if key in seen:
            continue
        seen.add(key)
        hits.append(
            ReferenceHit(
                file_path=rel,
                line_number=ln,
                reference_kind="python_comment",
                line_text=line_text.rstrip(),
            ),
        )
    return hits


def _iter_py_comments(file: Path) -> list[tokenize.TokenInfo]:
    try:
        with open(file, "rb") as fh:
            return [t for t in tokenize.tokenize(fh.readline)
                    if t.type == tokenize.COMMENT]
    except (tokenize.TokenError, SyntaxError, OSError):
        return []


def _classify_python_node(
    node: ast.AST, pattern: re.Pattern[str], rel: str, lines: list[str],
) -> list[ReferenceHit]:
    line_no = getattr(node, "lineno", None)
    if line_no is None:
        return []

    if isinstance(node, ast.Import):
        for alias in node.names:
            if pattern.search(alias.name) or (
                alias.asname and pattern.search(alias.asname)
            ):
                return [_build_hit(rel, line_no, "python_import", lines)]
        return []

    if isinstance(node, ast.ImportFrom):
        module = node.module or ""
        if pattern.search(module):
            return [_build_hit(rel, line_no, "python_import", lines)]
        for alias in node.names:
            if pattern.search(alias.name) or (
                alias.asname and pattern.search(alias.asname)
            ):
                return [_build_hit(rel, line_no, "python_import", lines)]
        return []

    if isinstance(node, ast.Name):
        if pattern.search(node.id):
            return [_build_hit(rel, line_no, "python_identifier", lines)]
        return []

    if isinstance(node, ast.Attribute):
        try:
            rendered = ast.unparse(node)
        except (AttributeError, ValueError):
            rendered = node.attr
        if pattern.search(rendered):
            return [_build_hit(rel, line_no, "python_identifier", lines)]
        return []

    if (
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and pattern.search(node.value)
    ):
        return [_build_hit(rel, line_no, "python_string_literal", lines)]

    return []


def _build_hit(
    rel: str, line: int, kind: str, lines: list[str],
) -> ReferenceHit:
    line_text = lines[line - 1] if 0 < line <= len(lines) else ""
    return ReferenceHit(
        file_path=rel,
        line_number=line,
        reference_kind=kind,
        line_text=line_text.rstrip(),
    )


def _scan_markdown(
    file: Path, pattern: re.Pattern[str],
) -> list[ReferenceHit]:
    try:
        parsed = parse_markdown(file)
    except (OSError, UnicodeDecodeError):
        return []
    hits: list[ReferenceHit] = []
    fm = parsed.frontmatter_range
    fences = parsed.code_fences
    for i, line in enumerate(parsed.lines, start=1):
        if not pattern.search(line):
            continue
        if fm and fm.start_line <= i <= fm.end_line:
            kind = "markdown_frontmatter"
        elif any(f.start_line < i < f.end_line for f in fences):
            kind = "markdown_code_fence"
        else:
            kind = "markdown_body"
        hits.append(
            ReferenceHit(
                file_path=parsed.file_path,
                line_number=i,
                reference_kind=kind,
                line_text=line.rstrip(),
            ),
        )
    return hits


def _scan_json(file: Path, pattern: re.Pattern[str]) -> list[ReferenceHit]:
    try:
        text = file.read_text(encoding="utf-8")
    except OSError:
        return []
    try:
        json.loads(text)
    except json.JSONDecodeError:
        return []
    rel = file.as_posix()
    return [
        ReferenceHit(
            file_path=rel,
            line_number=i,
            reference_kind="json_value",
            line_text=line.rstrip(),
        )
        for i, line in enumerate(text.splitlines(), start=1)
        if pattern.search(line)
    ]


def _scan_yaml(file: Path, pattern: re.Pattern[str]) -> list[ReferenceHit]:
    try:
        text = file.read_text(encoding="utf-8")
    except OSError:
        return []
    try:
        yaml.safe_load(text)
    except yaml.YAMLError:
        return []
    rel = file.as_posix()
    return [
        ReferenceHit(
            file_path=rel,
            line_number=i,
            reference_kind="yaml_value",
            line_text=line.rstrip(),
        )
        for i, line in enumerate(text.splitlines(), start=1)
        if pattern.search(line)
    ]


def _scan_shell(file: Path, pattern: re.Pattern[str]) -> list[ReferenceHit]:
    try:
        text = file.read_text(encoding="utf-8")
    except OSError:
        return []
    rel = file.as_posix()
    hits: list[ReferenceHit] = []
    for i, line in enumerate(text.splitlines(), start=1):
        if not pattern.search(line):
            continue
        kind = "shell_mention"
        for form_kind, form_pat in _SHELL_FORM_PATTERNS.items():
            m = form_pat.search(line)
            if m and pattern.search(m.group(0)):
                kind = form_kind
                break
        hits.append(
            ReferenceHit(
                file_path=rel,
                line_number=i,
                reference_kind=kind,
                line_text=line.rstrip(),
            ),
        )
    return hits


def emit_manifest(
    artifact: str, hits: list[ReferenceHit], fmt: str,
) -> str:
    """Serialize the manifest as YAML (default) or JSON."""
    payload = {
        "artifact": artifact,
        "hits": [asdict(h) for h in hits],
    }
    if fmt == "json":
        return json.dumps(payload, indent=2) + "\n"
    return yaml.dump(
        payload, default_flow_style=False, sort_keys=False, allow_unicode=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Find structural references to a harness artifact name across "
            "Python / markdown / JSON / YAML / shell files."
        ),
    )
    parser.add_argument(
        "--artifact", required=True,
        help="Anchor name to search for (word-boundary match).",
    )
    parser.add_argument(
        "--root", action="append", default=[],
        help=(
            "File or directory to scan (repeatable). "
            f"Defaults to: {', '.join(_DEFAULT_ROOTS)}."
        ),
    )
    parser.add_argument(
        "--format", choices=("yaml", "json"), default="yaml",
        help="Output format (default: yaml).",
    )
    args = parser.parse_args(argv)
    roots = [Path(r) for r in (args.root or list(_DEFAULT_ROOTS))]
    hits = find_references(args.artifact, roots)
    sys.stdout.write(emit_manifest(args.artifact, hits, args.format))
    return 0


if __name__ == "__main__":
    sys.exit(main())

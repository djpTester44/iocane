"""Markdown reference parsing utilities.

Typed parser for harness markdown files (commands, rules, docs, references,
SKILL.md). Extracts YAML frontmatter, fenced code blocks, inline links, and
classifies arbitrary token occurrences by structural region. Used by
``find_artifact_references.py`` so that markdown reference detection does not
resort to bare grep -- a region-classified hit lets the caller distinguish a
prose mention from a path reference inside a code fence from a frontmatter
glob.

Public surface:

* ``parse_markdown(path) -> ParsedMarkdown``
* ``find_token(parsed, token) -> list[TokenHit]``
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

RegionKind = Literal["frontmatter", "code_fence", "body"]

_FRONTMATTER_DELIM = "---"
_FENCE_RE = re.compile(r"^\s{0,3}(```+|~~~+)\s*(\S*)\s*$")
_INLINE_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")


@dataclass(frozen=True)
class FrontmatterRange:
    """Inclusive 1-based line span of the YAML frontmatter block."""

    start_line: int
    end_line: int


@dataclass(frozen=True)
class CodeFenceRange:
    """Inclusive 1-based line span of one fenced code block.

    ``language`` is the info string after the opening fence (``python`` in
    `````python``); ``None`` if absent.
    """

    start_line: int
    end_line: int
    language: str | None


@dataclass(frozen=True)
class InlineLink:
    """One ``[text](target)`` occurrence outside frontmatter."""

    line_number: int
    text: str
    target: str


@dataclass(frozen=True)
class TokenHit:
    """A single occurrence of a search token, with structural classification."""

    file_path: str
    line_number: int
    region_kind: RegionKind
    line_text: str
    code_fence_language: str | None = None


@dataclass(frozen=True)
class ParsedMarkdown:
    """Structured parse of a markdown file."""

    file_path: str
    frontmatter: dict | None
    frontmatter_range: FrontmatterRange | None
    code_fences: tuple[CodeFenceRange, ...]
    inline_links: tuple[InlineLink, ...]
    lines: tuple[str, ...]


def parse_markdown(path: Path | str) -> ParsedMarkdown:
    """Load and structurally parse a markdown file."""
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    lines = text.splitlines()

    fm_data, fm_range = _extract_frontmatter(lines)
    code_fences = _find_code_fences(lines, fm_range)
    inline_links = _find_inline_links(lines, fm_range)

    return ParsedMarkdown(
        file_path=p.as_posix(),
        frontmatter=fm_data,
        frontmatter_range=fm_range,
        code_fences=tuple(code_fences),
        inline_links=tuple(inline_links),
        lines=tuple(lines),
    )


def find_token(parsed: ParsedMarkdown, token: str) -> list[TokenHit]:
    """Locate every line on which ``token`` appears, classified by region."""
    if not token:
        return []
    hits: list[TokenHit] = []
    fm = parsed.frontmatter_range
    fences = parsed.code_fences
    for i, line in enumerate(parsed.lines, start=1):
        if token not in line:
            continue
        region, fence_lang = _classify_line(i, fm, fences)
        hits.append(
            TokenHit(
                file_path=parsed.file_path,
                line_number=i,
                region_kind=region,
                line_text=line.rstrip(),
                code_fence_language=fence_lang,
            ),
        )
    return hits


def _extract_frontmatter(
    lines: list[str],
) -> tuple[dict | None, FrontmatterRange | None]:
    """Parse leading ``---`` delimited YAML frontmatter, if present."""
    if not lines or lines[0].strip() != _FRONTMATTER_DELIM:
        return None, None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == _FRONTMATTER_DELIM:
            block = "\n".join(lines[1:i])
            try:
                data = yaml.safe_load(block) or {}
            except yaml.YAMLError:
                data = None
            if not isinstance(data, dict):
                data = None
            return data, FrontmatterRange(start_line=1, end_line=i + 1)
    return None, None


def _find_code_fences(
    lines: list[str], fm_range: FrontmatterRange | None,
) -> list[CodeFenceRange]:
    """Locate balanced triple-backtick / triple-tilde fenced blocks."""
    fences: list[CodeFenceRange] = []
    open_marker: str | None = None
    open_line = 0
    open_lang: str | None = None
    for i, line in enumerate(lines, start=1):
        if fm_range and fm_range.start_line <= i <= fm_range.end_line:
            continue
        m = _FENCE_RE.match(line)
        if not m:
            continue
        marker, lang = m.group(1), (m.group(2) or None)
        marker_kind = marker[0]
        if open_marker is None:
            open_marker = marker_kind
            open_line = i
            open_lang = lang
        elif marker_kind == open_marker:
            fences.append(
                CodeFenceRange(
                    start_line=open_line, end_line=i, language=open_lang,
                ),
            )
            open_marker = None
            open_lang = None
            open_line = 0
    return fences


def _find_inline_links(
    lines: list[str], fm_range: FrontmatterRange | None,
) -> list[InlineLink]:
    """Find ``[text](target)`` occurrences outside frontmatter."""
    links: list[InlineLink] = []
    for i, line in enumerate(lines, start=1):
        if fm_range and fm_range.start_line <= i <= fm_range.end_line:
            continue
        for m in _INLINE_LINK_RE.finditer(line):
            links.append(
                InlineLink(
                    line_number=i, text=m.group(1), target=m.group(2),
                ),
            )
    return links


def _classify_line(
    line_number: int,
    fm: FrontmatterRange | None,
    fences: tuple[CodeFenceRange, ...],
) -> tuple[RegionKind, str | None]:
    """Return the structural region for a 1-based line number."""
    if fm and fm.start_line <= line_number <= fm.end_line:
        return "frontmatter", None
    for fence in fences:
        if fence.start_line < line_number < fence.end_line:
            return "code_fence", fence.language
    return "body", None

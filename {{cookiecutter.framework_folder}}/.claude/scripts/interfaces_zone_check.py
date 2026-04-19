"""interfaces_zone_check.py

Core logic for the interfaces-zone guard hooks:
  * ``interfaces-pyi-only.sh`` -- Edit|Write matcher; non-.pyi writes rejected.
  * ``interfaces-codegen-only.sh`` -- Edit|Write matcher; writes require
    ``IOCANE_ROLE=gen_protocols``.
  * ``interfaces-bash-write.sh`` -- Bash matcher; shell-redirection and
    file-manipulator writes must honor the same extension + role gates.
  * ``interfaces-powershell-write.sh`` -- PowerShell matcher; Windows
    parity for the Bash-write class.

## Trust model

These hooks gate AGENT DRIFT UNDER CONTEXT PRESSURE, not deliberate
adversarial bypass. ``IOCANE_ROLE`` is a caller-controlled string; an
attacker who reads this script can inline-set the role to bypass. The
shell-verb regex sets are blocklists, not allowlists, and are
non-exhaustive by design. Acceptable under v3's threat model (honest
agent following workflow); cryptographic admission engineering
(per-invocation tokens, parent-process verification, capability
binding) is deferred as out-of-scope.

## Zone detection

Anchored to the top-level ``interfaces/`` directory at the repo root
(relative paths whose first segment, after stripping ``./``, is
``interfaces``). Nested occurrences (``docs/interfaces/``,
``third_party/*/interfaces/``) do NOT trigger the guards. Comparison
is case-insensitive. Symlinks are resolved before the zone check so
indirect paths (``src/link_to_interfaces/foo.py``) also trip the guards.
"""

import json
import os
import re
import sys

_PYI_ONLY_MSG = (
    "BLOCKED: interfaces/ is type-only; non-.pyi writes rejected "
    "({file_path}). See harness/rules/interfaces-zone.md."
)

_CODEGEN_ONLY_MSG = (
    "BLOCKED: interfaces/ is codegen-only; hand-authored writes rejected "
    "({file_path}). Run /io-gen-protocols to regenerate from YAML, or "
    "edit plans/*.yaml then re-run codegen. See "
    "harness/rules/interfaces-zone.md."
)

_BASH_WRITE_MSG_BASE = (
    "BLOCKED: command writes into interfaces/ outside the codegen "
    "scope. interfaces/ is codegen-only; shell redirection / file "
    "manipulators cannot route around /io-gen-protocols. Offending "
    "command: {command!r}. See harness/rules/interfaces-zone.md."
)

_BASH_PYI_ONLY_MSG = (
    "BLOCKED: command writes a non-.pyi file into interfaces/. "
    "interfaces/ is type-only; even under IOCANE_ROLE=gen_protocols "
    "only .pyi files may be written. Offending command: {command!r}. "
    "See harness/rules/interfaces-zone.md."
)

# Bash write-verb patterns targeting top-level interfaces/ only. Each
# regex anchors the interfaces/ reference to optional ``./`` or quote
# after the write verb -- absolute paths and nested ``docs/interfaces/``
# are intentionally not matched (same scope as the file_path guards).
#
# NON-EXHAUSTIVE BY DESIGN. The honest-agent threat model does not
# require catching every shell primitive ever invented. Adding verbs
# here raises the drift bar incrementally; it does not close the
# structurally-undefended role admission path.
_BASH_WRITE_PATTERNS = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        # Shell redirect: > interfaces/ or >> interfaces/
        r">>?\s*['\"]?\.?/?interfaces/",
        # tee [flags] interfaces/
        r"\btee\b(?:\s+-\S+)*\s+['\"]?\.?/?interfaces/",
        # cp / mv SRC interfaces/
        r"\b(?:cp|mv)\b(?:\s+-\S+)*\s+\S+\s+['\"]?\.?/?interfaces/",
        # install [flags] ... interfaces/ (non-greedy to tolerate
        # flag-with-value pairs like `install -m 644 src/x.py ...`)
        r"\binstall\b[^|&;]*?\s['\"]?\.?/?interfaces/",
        # touch interfaces/
        r"\btouch\b(?:\s+-\S+)*\s+['\"]?\.?/?interfaces/",
        # sed -i ... interfaces/
        r"\bsed\b[^|&;]*?\s+-i\b[^|&;]*?['\"]?\.?/?interfaces/",
        # python open(...) (single/double quote, incl. shell-escaped \")
        r"\bopen\s*\(\s*\\?['\"]\.?/?interfaces/",
        # dd of=interfaces/
        r"\bdd\b[^|&;]*?\bof=['\"]?\.?/?interfaces/",
        # python -c / python3 -c / py -c with interfaces/ anywhere in the
        # quoted script body. Covers open(f'...'), pathlib.write_text,
        # shutil.copy, os.rename, and any other stdlib write idiom whose
        # target string contains the zone path literal. Non-greedy .*?
        # tolerates nested quote layers (outer double, inner single).
        r"\b(?:python3?|py)\b\s+-c\s+['\"].*?interfaces/",
    )
)

# PowerShell equivalents. Windows parity under the same trust model.
# Each pattern requires whitespace or ``=`` (for ``-FilePath=...`` syntax)
# immediately before the optional ``./``/quote prefix, which anchors the
# interfaces/ reference to top-level and avoids matching
# ``docs/interfaces/...`` when a verb precedes it earlier in the line.
_POWERSHELL_WRITE_PATTERNS = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        # PowerShell redirect: > / >>
        r">>?\s*['\"]?\.?/?interfaces/",
        # Set-Content / Add-Content / Out-File / Export-*
        r"\b(?:Set-Content|Add-Content|Out-File|Export-Csv|Export-Clixml)"
        r"\b[^|&;]*?[\s=]['\"]?\.?/?interfaces/",
        # New-Item interfaces/... -ItemType File
        r"\bNew-Item\b[^|&;]*?[\s=]['\"]?\.?/?interfaces/",
        # Copy-Item / Move-Item SRC interfaces/
        r"\b(?:Copy-Item|Move-Item)\b[^|&;]*?[\s=]['\"]?\.?/?interfaces/",
        # Tee-Object -FilePath interfaces/
        r"\bTee-Object\b[^|&;]*?[\s=]['\"]?\.?/?interfaces/",
    )
)

# Path token referring to a non-.pyi file inside top-level interfaces/,
# used to enforce the .pyi-only invariant on Bash / PowerShell commands
# even when the role admits the write. The negative lookbehind excludes
# word-chars and slashes so nested paths like ``docs/interfaces/...`` are
# NOT treated as top-level matches.
_NON_PYI_INTERFACES_TOKEN = re.compile(
    r"(?<![A-Za-z0-9_/])['\"]?\.?/?interfaces/"
    r"[^\s'\"<>|&;`$]*\.(?!pyi\b)[A-Za-z0-9_]+",
    re.IGNORECASE,
)


def _normalized(file_path: str) -> str:
    """Lowercase + POSIX-separator + leading-``./`` stripped."""
    normalized = file_path.replace("\\", "/").lower()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _literal_in_interfaces_zone(file_path: str) -> bool:
    """Match ``interfaces`` as the first repo-relative segment (literal)."""
    normalized = _normalized(file_path)
    if not normalized:
        return False
    return normalized.split("/", 1)[0] == "interfaces"


def _resolved_in_interfaces_zone(file_path: str) -> bool:
    """Resolve symlinks and check if the target lands under
    ``<cwd>/interfaces``.

    Catches the indirection case where an author-looking path
    (``src/link/foo.py`` where ``src/link`` is a symlink to
    ``interfaces``) smuggles a write INTO the zone. Returns False on
    resolution error so other hooks remain authoritative.
    """
    try:
        target = os.path.realpath(file_path)
        zone = os.path.realpath("interfaces")
    except (OSError, ValueError):
        return False
    target_norm = target.replace("\\", "/").lower()
    zone_norm = zone.replace("\\", "/").lower()
    if target_norm == zone_norm:
        return True
    return target_norm.startswith(zone_norm + "/")


def _in_interfaces_zone(file_path: str) -> bool:
    """Return True when either the literal or the resolved path is
    under top-level interfaces/."""
    if not file_path:
        return False
    return _literal_in_interfaces_zone(
        file_path
    ) or _resolved_in_interfaces_zone(file_path)


def is_violation_pyi_only(file_path: str) -> str | None:
    """Return an error message if a non-.pyi write targets interfaces/."""
    if not file_path:
        return None
    if not _in_interfaces_zone(file_path):
        return None
    normalized = _normalized(file_path)
    segments = normalized.split("/")
    if len(segments) < 2:
        return None
    if segments[-1].endswith(".pyi"):
        return None
    return _PYI_ONLY_MSG.format(file_path=file_path)


def is_violation_codegen_only(
    file_path: str, role: str | None
) -> str | None:
    """Return an error message if a write under interfaces/ lacks the role."""
    if not file_path:
        return None
    if not _in_interfaces_zone(file_path):
        return None
    if role == "gen_protocols":
        return None
    return _CODEGEN_ONLY_MSG.format(file_path=file_path)


def _bash_or_shell_violation(
    command: str,
    role: str | None,
    write_patterns: tuple[re.Pattern[str], ...],
) -> str | None:
    """Shared core for Bash + PowerShell write-pattern checks.

    Two gates:
      1. If the command writes a non-.pyi target into interfaces/,
         reject regardless of role (parity with is_violation_pyi_only
         on the Edit|Write matcher).
      2. If the command writes a .pyi target into interfaces/, require
         role=gen_protocols (parity with is_violation_codegen_only).
    """
    if not command:
        return None
    has_write = any(p.search(command) for p in write_patterns)
    if not has_write:
        return None
    if _NON_PYI_INTERFACES_TOKEN.search(command):
        return _BASH_PYI_ONLY_MSG.format(command=command[:300])
    if role == "gen_protocols":
        return None
    return _BASH_WRITE_MSG_BASE.format(command=command[:300])


def is_violation_bash_write(
    command: str, role: str | None
) -> str | None:
    """Return an error message if a Bash command writes into interfaces/.

    Closes the common drift vectors for shell redirection and file
    manipulators. The pattern set is a blocklist (non-exhaustive by
    design per the trust model); tightening it beyond honest-agent
    drift cases is explicitly out-of-scope.
    """
    return _bash_or_shell_violation(command, role, _BASH_WRITE_PATTERNS)


def is_violation_powershell_write(
    command: str, role: str | None
) -> str | None:
    """Return an error message if a PowerShell command writes into interfaces/.

    Windows parity for the Bash-write class. Covers Out-File,
    Set-Content, Add-Content, New-Item, Copy/Move-Item, Tee-Object,
    and shell redirection. Same non-exhaustive-blocklist caveat.
    """
    return _bash_or_shell_violation(command, role, _POWERSHELL_WRITE_PATTERNS)


def _file_path_from_stdin_json() -> str:
    """Extract ``tool_input.file_path`` from PreToolUse JSON on stdin."""
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return ""
        d = json.loads(raw)
        return (d.get("tool_input") or {}).get("file_path", "") or ""
    except (json.JSONDecodeError, AttributeError, TypeError):
        return ""


def _command_from_stdin_json() -> str:
    """Extract ``tool_input.command`` from PreToolUse JSON on stdin."""
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return ""
        d = json.loads(raw)
        return (d.get("tool_input") or {}).get("command", "") or ""
    except (json.JSONDecodeError, AttributeError, TypeError):
        return ""


def main(argv: list[str]) -> int:
    """CLI entry dispatched by the bash/powershell hook wrappers."""
    if len(argv) < 2:
        return 0
    mode = argv[1]
    if mode == "pyi-only":
        file_path = _file_path_from_stdin_json()
        msg = is_violation_pyi_only(file_path)
    elif mode == "codegen-only":
        file_path = _file_path_from_stdin_json()
        role = argv[2] if len(argv) > 2 else ""
        msg = is_violation_codegen_only(file_path, role or None)
    elif mode == "bash-write":
        command = _command_from_stdin_json()
        role = argv[2] if len(argv) > 2 else ""
        msg = is_violation_bash_write(command, role or None)
    elif mode == "powershell-write":
        command = _command_from_stdin_json()
        role = argv[2] if len(argv) > 2 else ""
        msg = is_violation_powershell_write(command, role or None)
    else:
        return 0
    if msg:
        sys.stderr.write(msg + "\n")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

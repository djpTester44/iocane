"""validate_trust_edge_chain.py

Cross-artifact trust-edge chain validator for /io-architect Step G's
deterministic batch. Enforces three mechanical checks across the PRD,
roadmap, component-contracts.yaml, and symbols.yaml:

  Check 1 (presence): If the PRD body contains external-input boundary
    keywords (untrusted, webhook, payload, etc.) but the roadmap has no
    Trust Edges section, emit exit code 1. The PRD is the authoring
    surface where operators describe boundaries; /io-specify Step B.5
    is responsible for synthesizing the Trust Edges section into the
    roadmap. This check catches the synthesis gap.

  Check 2 (chain): For each Trust Edge declared in the roadmap, locate
    the named component in component-contracts.yaml and verify its
    ``raises`` list contains at least one entry whose name matches an
    adversarial-rejection keyword (invalid, malformed, oversize, etc.).
    Exit code 2 on miss.

  Check 3 (parameterization): For each component flagged in Check 2,
    scan its responsibilities and raises entries for bare literal numbers
    adjacent to measurement units (e.g. "30 seconds", "1024 bytes").
    Any hit without an adjacent ``Settings.<symbol>`` reference emits
    exit code 3.

Exit codes:
  0  -- all checks pass
  1  -- Check 1 fail (presence)
  2  -- Check 2 fail (chain)
  3  -- Check 3 fail (parameterization)
  Multi-fail uses left-to-right priority: if both Check 1 and Check 2
  fail, exit 1.

Usage:
    uv run python .claude/scripts/validate_trust_edge_chain.py \\
        --prd plans/PRD.md \\
        --roadmap plans/roadmap.md \\
        --contracts plans/component-contracts.yaml \\
        --symbols plans/symbols.yaml
"""

import argparse
import logging
import re
import sys
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex constants
# ---------------------------------------------------------------------------

# Check 1 -- keywords that indicate external-input / trust boundaries.
# ``deserializ`` is a stem (matches deserialize, deserialization, etc.) so
# no trailing word-boundary is applied; the others use whole-word matching.
_BOUNDARY_KEYWORDS_RE = re.compile(
    r"\b(untrusted|webhook|payload|deserializ\w*|external\s+api"
    r"|path\s+resolution|secret\s+material)\b",
    re.IGNORECASE,
)

# Check 1 -- heading that marks the Trust Edges section in the roadmap.
_TRUST_EDGES_SECTION_RE = re.compile(
    r"^##\s+Trust\s+Edges",
    re.IGNORECASE | re.MULTILINE,
)

# Check 2 -- match a Trust Edge entry's "component:" field.
# Handles both YAML list-block format (- component: ...) and
# markdown bold format (- **component:** ...).
# The markdown form places the closing ** AFTER the colon: **component:**
# so we must allow for trailing * chars after the colon too.
_TE_COMPONENT_RE = re.compile(
    r"(?:^|\n)\s*-\s+\*{0,2}component\*{0,2}:\*{0,2}\s*(.+)",
    re.IGNORECASE,
)

# Check 2 -- adversarial-rejection keywords in exception names / raise triggers.
# No trailing word boundary -- exception names use CamelCase so the keyword
# stem is embedded (e.g., InvalidPayloadError, MalformedInputError).
# Leading \b ensures we don't match mid-stem (e.g., "oversize" not "Coversize").
_ADVERSARIAL_TRIGGER_RE = re.compile(
    r"\b(invalid|malformed|oversize|traversal|forbidden|unauthorized"
    r"|tamper|replay)",
    re.IGNORECASE,
)

# Check 3 -- bare literal numbers adjacent to measurement units.
_LITERAL_NUMBER_RE = re.compile(
    r"\b\d+(\.\d+)?\s*(seconds?|attempts?|times?|bytes?|requests?"
    r"|chars?|kb|mb)\b",
    re.IGNORECASE,
)

# Check 3 -- Settings.<symbol> reference in the vicinity of a literal.
_SETTINGS_REF_RE = re.compile(r"\bSettings\.[A-Za-z_][A-Za-z0-9_.]*\b")


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _extract_trust_edge_components(roadmap_text: str) -> list[str]:
    """Extract component names from Trust Edges section of roadmap.md.

    Args:
        roadmap_text: Full text of the roadmap / PRD markdown file.

    Returns:
        List of component name strings declared under Trust Edges entries.
        Empty list if section is absent or declares "no trust edges".
    """
    section_match = _TRUST_EDGES_SECTION_RE.search(roadmap_text)
    if not section_match:
        return []

    # Slice from the section heading to the next ## heading (or end of file).
    section_start = section_match.start()
    next_h2 = re.search(r"\n##\s", roadmap_text[section_start + 1 :])
    if next_h2:
        section_text = roadmap_text[
            section_start : section_start + 1 + next_h2.start()
        ]
    else:
        section_text = roadmap_text[section_start:]

    # Skip explicit "no trust edges" declarations.
    if re.search(r"no\s+trust\s+edges", section_text, re.IGNORECASE):
        return []

    components: list[str] = []
    for m in _TE_COMPONENT_RE.finditer(section_text):
        raw = m.group(1).strip()
        # Strip trailing markdown / YAML noise (e.g. square-bracket wrappers).
        raw = raw.strip("[]").strip()
        if raw:
            components.append(raw)
    return components


def _load_contracts_raw(contracts_path: Path) -> dict[str, dict[str, object]]:
    """Load component-contracts.yaml as a raw dict without schema validation.

    Using raw YAML avoids importing the full schemas module and keeps the
    validator self-contained for cross-artifact use.

    Args:
        contracts_path: Path to component-contracts.yaml.

    Returns:
        Dict mapping component name to its raw YAML fields.

    Raises:
        FileNotFoundError: If the file does not exist.
        yaml.YAMLError: If the file fails to parse.
    """
    text = contracts_path.read_text(encoding="utf-8")
    raw = yaml.safe_load(text)
    if not isinstance(raw, dict):
        return {}
    components = raw.get("components", {})
    if not isinstance(components, dict):
        return {}
    return {k: v if isinstance(v, dict) else {} for k, v in components.items()}


def _load_symbols_raw(symbols_path: Path) -> dict[str, dict[str, object]]:
    """Load symbols.yaml as a raw dict.

    Args:
        symbols_path: Path to symbols.yaml.

    Returns:
        Dict mapping symbol name to its raw YAML fields.
    """
    if not symbols_path.exists():
        return {}
    text = symbols_path.read_text(encoding="utf-8")
    raw = yaml.safe_load(text)
    if not isinstance(raw, dict):
        return {}
    symbols = raw.get("symbols", {})
    if not isinstance(symbols, dict):
        return {}
    return {k: v if isinstance(v, dict) else {} for k, v in symbols.items()}


def _resolve_component_name(
    name: str,
    contracts: dict[str, dict[str, object]],
) -> str | None:
    """Resolve a Trust Edge component reference to a contracts key.

    Trust Edge ``component`` fields may name a roadmap feature identifier
    (e.g. "F-03") or a component name that maps to a contracts entry.
    This function does exact-match first, then prefix/substring match as
    a fallback for cases where the TE entry includes descriptive text
    alongside the component name.

    Args:
        name: Raw component string from the Trust Edge entry.
        contracts: Component contracts dict keyed by component name.

    Returns:
        The matching contract key, or None if no match found.
    """
    if name in contracts:
        return name
    # Prefix/word-boundary match -- handles "F-03 — PipelineValidator" etc.
    for key in contracts:
        if key in name or name in key:
            return key
    return None


# ---------------------------------------------------------------------------
# Check functions
# ---------------------------------------------------------------------------


def check_presence(prd_text: str, roadmap_text: str) -> list[str]:
    """Check 1: presence.

    If PRD body contains boundary keywords but the roadmap has no Trust
    Edges section, return a list with one violation message. The PRD is
    the authoring surface (operators describe boundaries there); the
    roadmap is where /io-specify Step B.5 synthesizes Trust Edges. This
    check catches the synthesis gap between the two surfaces.

    Args:
        prd_text: Full text of plans/PRD.md.
        roadmap_text: Full text of plans/roadmap.md.

    Returns:
        List of violation strings (empty = pass).
    """
    has_keywords = bool(_BOUNDARY_KEYWORDS_RE.search(prd_text))
    if not has_keywords:
        return []

    has_section = bool(_TRUST_EDGES_SECTION_RE.search(roadmap_text))
    if has_section:
        return []

    return [
        "Check 1 (presence): PRD describes external-input boundaries "
        f"(matched keywords: {_BOUNDARY_KEYWORDS_RE.pattern[:60]}...) "
        "but roadmap has no '## Trust Edges' section. "
        "/io-specify Step B.5 is expected to synthesize a Trust Edges / "
        "Security Boundaries section into the roadmap; verify Step B.5 "
        "ran or add the section per the io-specify template."
    ]


def check_chain(
    roadmap_text: str,
    contracts: dict[str, dict[str, object]],
) -> tuple[list[str], list[str]]:
    """Check 2: chain.

    For each declared Trust Edge component, verify the component's
    ``raises`` list contains at least one adversarial-rejection entry.

    Args:
        roadmap_text: Full text of plans/roadmap.md.
        contracts: Component contracts dict keyed by component name.

    Returns:
        Tuple of (violations, flagged_component_names). violations is
        empty on pass; flagged_component_names carries names for Check 3.
    """
    te_components = _extract_trust_edge_components(roadmap_text)
    if not te_components:
        return [], []

    violations: list[str] = []
    flagged: list[str] = []

    for te_name in te_components:
        resolved = _resolve_component_name(te_name, contracts)
        if resolved is None:
            violations.append(
                f"Check 2 (chain): Trust Edge component '{te_name}' not found "
                "in component-contracts.yaml. "
                "Ensure the component name in the Trust Edge matches a contract entry."
            )
            continue

        contract = contracts[resolved]
        raw_raises = contract.get("raises")
        raises_list: list[object] = (
            raw_raises if isinstance(raw_raises, list) else []
        )

        has_adversarial = any(
            isinstance(entry, str) and _ADVERSARIAL_TRIGGER_RE.search(entry)
            for entry in raises_list
        )

        if not has_adversarial:
            violations.append(
                f"Check 2 (chain): Component '{resolved}' is declared as a "
                "Trust Edge boundary but its raises list contains no adversarial-"
                "rejection entry (keywords: invalid, malformed, oversize, "
                "traversal, forbidden, unauthorized, tamper, replay). "
                "Add at least one raises entry covering adversarial rejection."
            )
            flagged.append(resolved)
        else:
            # Still flag for Check 3 even when chain passes.
            flagged.append(resolved)

    return violations, flagged


def check_parameterization(
    contracts: dict[str, dict[str, object]],
    flagged_components: list[str],
) -> list[str]:
    """Check 3: parameterization.

    For each flagged Trust Edge component, scan responsibilities and raises
    text for bare literal numbers adjacent to measurement units. A hit is
    a violation unless an adjacent ``Settings.<symbol>`` reference appears
    within the same line.

    Args:
        contracts: Component contracts dict keyed by component name.
        flagged_components: Component names to scan (from Check 2).

    Returns:
        List of violation strings (empty = pass).
    """
    violations: list[str] = []

    for comp_name in flagged_components:
        contract = contracts.get(comp_name, {})
        raw_resp = contract.get("responsibilities")
        raw_raises = contract.get("raises")
        responsibilities: list[object] = (
            raw_resp if isinstance(raw_resp, list) else []
        )
        raises_list: list[object] = (
            raw_raises if isinstance(raw_raises, list) else []
        )

        lines: list[object] = list(responsibilities) + list(raises_list)
        for line in lines:
            if not isinstance(line, str):
                continue
            for lit_match in _LITERAL_NUMBER_RE.finditer(line):
                # Check if the same line has a Settings.<symbol> reference.
                if not _SETTINGS_REF_RE.search(line):
                    violations.append(
                        f"Check 3 (parameterization): Component '{comp_name}' "
                        f"contains bare literal '{lit_match.group()}' in "
                        f"responsibilities/raises without an adjacent "
                        f"Settings.<symbol> reference. "
                        f"Extract the threshold into symbols.yaml and cite it "
                        f"as Settings.<symbol>. Line: {line!r}"
                    )
                    # One violation per line is sufficient.
                    break

    return violations


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Entry point for the trust-edge chain validator.

    Args:
        argv: Argument list, defaults to sys.argv[1:] when None.

    Returns:
        Exit code: 0 pass, 1 Check 1 fail, 2 Check 2 fail, 3 Check 3 fail.
        Left-to-right priority on multi-fail.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Validate the PRD trust-edge chain "
            "(presence -> chain -> parameterization) "
            "for /io-architect Step G."
        ),
    )
    parser.add_argument(
        "--prd",
        default="plans/PRD.md",
        help="Path to plans/PRD.md (Check 1 reads this for boundary keywords).",
    )
    parser.add_argument(
        "--roadmap",
        default="plans/roadmap.md",
        help=(
            "Path to plans/roadmap.md (Check 1 reads this for Trust Edges "
            "section presence; Check 2 extracts TE component names from it)."
        ),
    )
    parser.add_argument(
        "--contracts",
        default="plans/component-contracts.yaml",
        help="Path to component-contracts.yaml.",
    )
    parser.add_argument(
        "--symbols",
        default="plans/symbols.yaml",
        help="Path to symbols.yaml.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    prd_path = Path(args.prd)
    if not prd_path.exists():
        logger.error("PRD file not found: %s", prd_path)
        return 1

    prd_text = prd_path.read_text(encoding="utf-8")

    roadmap_path = Path(args.roadmap)
    if not roadmap_path.exists():
        logger.error("roadmap file not found: %s", roadmap_path)
        return 1

    roadmap_text = roadmap_path.read_text(encoding="utf-8")

    contracts_path = Path(args.contracts)
    if not contracts_path.exists():
        logger.error("contracts file not found: %s", contracts_path)
        return 2

    try:
        contracts = _load_contracts_raw(contracts_path)
    except (yaml.YAMLError, OSError, UnicodeDecodeError):
        logger.exception("failed to load %s", contracts_path)
        return 2

    symbols_path = Path(args.symbols)
    # symbols.yaml is optional for Check 3 (we pattern-match text, not the file).
    _load_symbols_raw(symbols_path)  # load for future extensibility; unused now

    # -----------------------------------------------------------------------
    # Check 1: presence
    # -----------------------------------------------------------------------
    presence_violations = check_presence(prd_text, roadmap_text)
    if presence_violations:
        for v in presence_violations:
            sys.stderr.write(f"VIOLATION: {v}\n")
        sys.stderr.write("FAIL: Check 1 (presence) failed.\n")
        return 1

    # -----------------------------------------------------------------------
    # Check 2: chain
    # -----------------------------------------------------------------------
    chain_violations, flagged_components = check_chain(roadmap_text, contracts)
    if chain_violations:
        for v in chain_violations:
            sys.stderr.write(f"VIOLATION: {v}\n")
        sys.stderr.write("FAIL: Check 2 (chain) failed.\n")
        return 2

    # -----------------------------------------------------------------------
    # Check 3: parameterization
    # -----------------------------------------------------------------------
    param_violations = check_parameterization(contracts, flagged_components)
    if param_violations:
        for v in param_violations:
            sys.stderr.write(f"VIOLATION: {v}\n")
        sys.stderr.write("FAIL: Check 3 (parameterization) failed.\n")
        return 3

    component_count = len(contracts)
    te_count = len(_extract_trust_edge_components(roadmap_text))
    sys.stdout.write(
        f"PASS: trust-edge chain valid "
        f"({te_count} trust edge(s); {component_count} component(s) checked).\n",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

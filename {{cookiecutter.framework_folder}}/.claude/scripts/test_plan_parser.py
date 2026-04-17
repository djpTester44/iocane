"""Test plan I/O for plans/test-plan.yaml.

YAML-based test-plan I/O with Pydantic validation. Provides per-method
invariant lookup used by the Test Author (Tier 1) and completeness
checks used by validate-plan (Tier 1/2).

Used by hooks, scripts, and commands via ``uv run python -c "..."``.
"""

from pathlib import Path

import yaml
from schemas import InvariantKind, TestInvariant, TestPlanEntry, TestPlanFile

# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------


def load_test_plan(path: str) -> TestPlanFile:
    """Load and validate plans/test-plan.yaml."""
    text = Path(path).read_text(encoding="utf-8")
    if not text.strip():
        return TestPlanFile()
    raw = yaml.safe_load(text)
    if raw is None:
        return TestPlanFile()
    return TestPlanFile.model_validate(raw)


def save_test_plan(path: str, plan: TestPlanFile) -> None:
    """Serialize test plan to YAML and write to disk."""
    data = plan.model_dump(mode="json", exclude_none=True)
    output = yaml.dump(
        data, default_flow_style=False, sort_keys=False, allow_unicode=True
    )
    Path(path).write_text(output, encoding="utf-8")


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


def entries_for_protocol(
    plan: TestPlanFile, protocol: str
) -> list[TestPlanEntry]:
    """Return every entry whose protocol matches ``protocol``."""
    return [entry for entry in plan.entries if entry.protocol == protocol]


def invariants_for_method(
    plan: TestPlanFile, protocol: str, method: str
) -> list[TestInvariant]:
    """Return all invariants declared on ``protocol.method``."""
    invariants: list[TestInvariant] = []
    for entry in plan.entries:
        if entry.protocol == protocol and entry.method == method:
            invariants.extend(entry.invariants)
    return invariants


def invariants_by_kind(
    plan: TestPlanFile, kind: InvariantKind
) -> list[tuple[str, str, TestInvariant]]:
    """Return ``(protocol, method, invariant)`` tuples matching ``kind``."""
    matches: list[tuple[str, str, TestInvariant]] = []
    for entry in plan.entries:
        for inv in entry.invariants:
            if inv.kind == kind:
                matches.append((entry.protocol, entry.method, inv))
    return matches


# ---------------------------------------------------------------------------
# Completeness checks
# ---------------------------------------------------------------------------


def methods_missing_invariants(
    plan: TestPlanFile, methods_by_protocol: dict[str, set[str]]
) -> dict[str, list[str]]:
    """Return methods declared on Protocols but absent from the test plan.

    ``methods_by_protocol`` is the ground-truth map produced by AST
    extraction against interfaces/*.pyi. Mapping returned is
    ``protocol_path -> [missing method names]``.
    """
    covered: dict[str, set[str]] = {}
    for entry in plan.entries:
        covered.setdefault(entry.protocol, set()).add(entry.method)
    gaps: dict[str, list[str]] = {}
    for protocol, methods in methods_by_protocol.items():
        missing = sorted(methods - covered.get(protocol, set()))
        if missing:
            gaps[protocol] = missing
    return gaps

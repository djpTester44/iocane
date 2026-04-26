"""Test plan I/O for plans/test-plan.yaml.

YAML-based test-plan I/O with Pydantic validation. Provides per-component
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


def entry_for_component(
    plan: TestPlanFile, component: str
) -> TestPlanEntry | None:
    """Return the TestPlanEntry for ``component`` or None if absent."""
    return plan.entries.get(component)


def invariants_by_kind(
    plan: TestPlanFile, kind: InvariantKind
) -> list[tuple[str, TestInvariant]]:
    """Return ``(component, invariant)`` tuples matching ``kind``.

    Method context, when populated, lives on ``invariant.method`` --
    callers needing it read it from the returned invariant directly.
    """
    matches: list[tuple[str, TestInvariant]] = []
    for component, entry in plan.entries.items():
        for inv in entry.invariants:
            if inv.kind == kind:
                matches.append((component, inv))
    return matches


# ---------------------------------------------------------------------------
# Completeness checks
# ---------------------------------------------------------------------------


def components_missing_entries(
    plan: TestPlanFile, components: set[str]
) -> list[str]:
    """Return component names absent from the test plan, sorted."""
    return sorted(c for c in components if c not in plan.entries)


def components_missing_error_propagation(
    plan: TestPlanFile, raises_by_component: dict[str, list[str]]
) -> list[str]:
    """Return component names whose declared raises lack error_propagation coverage.

    A component with non-empty ``raises`` must have at least one
    ``error_propagation`` invariant in its TestPlanEntry. Components
    without any raises are skipped.
    """
    gaps: list[str] = []
    for component, raises in raises_by_component.items():
        if not raises:
            continue
        entry = plan.entries.get(component)
        if entry is None:
            gaps.append(component)
            continue
        has_ep = any(
            inv.kind == InvariantKind.ERROR_PROPAGATION
            for inv in entry.invariants
        )
        if not has_ep:
            gaps.append(component)
    return sorted(gaps)

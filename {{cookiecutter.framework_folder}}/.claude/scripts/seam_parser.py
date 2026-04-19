"""Seam parsing utilities for plans/seams.yaml.

YAML-based seam I/O with Pydantic validation. Provides query and mutation
functions for seam components and missing CT seam tracking.

Used by hooks, scripts, and commands via ``uv run python -c "..."``.
"""

from pathlib import Path
from typing import Literal

import yaml
from schemas import MissingCtSeam, SeamComponent, SeamEntry, SeamsFile

# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------

# Fields where empty lists can be stripped for readability.
_STRIPPABLE_LISTS = {
    "receives_di",
    "receives_di_protocols",
    "key_failure_modes",
    "backlog_refs",
}


def load_seams(path: str) -> SeamsFile:
    """Load and validate plans/seams.yaml."""
    text = Path(path).read_text(encoding="utf-8")
    if not text.strip():
        return SeamsFile()
    raw = yaml.safe_load(text)
    if raw is None:
        return SeamsFile()
    return SeamsFile.model_validate(raw)


def save_seams(path: str, seams: SeamsFile) -> None:
    """Serialize seams to YAML and write to disk.

    Components are sorted by (layer, component) for human readability.
    Empty lists are stripped except where structurally required.
    """
    data = seams.model_dump(mode="json", exclude_none=True)
    # Sort components by layer then component name
    if data.get("components"):
        data["components"] = sorted(
            data["components"],
            key=lambda c: (c.get("layer", 0), c.get("component", "")),
        )
    # Strip empty lists for readability
    for comp in data.get("components", []):
        for key in _STRIPPABLE_LISTS:
            if key in comp and not comp[key]:
                del comp[key]
    # Strip empty top-level lists
    if "missing_ct_seams" in data and not data["missing_ct_seams"]:
        del data["missing_ct_seams"]
    if "components" in data and not data["components"]:
        del data["components"]
    output = yaml.dump(
        data, default_flow_style=False, sort_keys=False, allow_unicode=True,
    )
    Path(path).write_text(output, encoding="utf-8")


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


def find_by_component(seams: SeamsFile, name: str) -> SeamComponent | None:
    """Find a seam component by name."""
    for comp in seams.components:
        if comp.component == name:
            return comp
    return None


def components_by_layer(
    seams: SeamsFile, layer: Literal[1, 2, 3, 4],
) -> list[SeamComponent]:
    """Return all components in the given layer."""
    return [c for c in seams.components if c.layer == layer]


def all_di_edges(seams: SeamsFile) -> list[tuple[str, str]]:
    """Return all DI edges as (component, dependency) tuples."""
    edges: list[tuple[str, str]] = []
    for comp in seams.components:
        for dep in comp.receives_di:
            edges.append((comp.component, dep))
    return edges


def components_with_backlog_refs(seams: SeamsFile) -> list[SeamComponent]:
    """Return components that have non-empty backlog_refs."""
    return [c for c in seams.components if c.backlog_refs]


def to_seam_entry(comp: SeamComponent) -> SeamEntry:
    """Project a SeamComponent down to a SeamEntry.

    Uses SeamEntry.model_fields dynamically so adding a field to SeamEntry
    automatically propagates without manual maintenance.
    """
    return SeamEntry(**{k: getattr(comp, k) for k in SeamEntry.model_fields})


# ---------------------------------------------------------------------------
# Mutations (return new SeamsFile)
# ---------------------------------------------------------------------------


def add_component(seams: SeamsFile, component: SeamComponent) -> SeamsFile:
    """Return a new SeamsFile with the component appended."""
    return SeamsFile(
        components=[*seams.components, component],
        missing_ct_seams=seams.missing_ct_seams,
    )


def update_component(
    seams: SeamsFile, name: str, **changes: object,
) -> SeamsFile:
    """Return a new SeamsFile with the named component updated."""
    new_components: list[SeamComponent] = []
    for comp in seams.components:
        if comp.component == name:
            new_components.append(comp.model_copy(update=changes))
        else:
            new_components.append(comp)
    return SeamsFile(
        components=new_components,
        missing_ct_seams=seams.missing_ct_seams,
    )


def remove_component(seams: SeamsFile, name: str) -> SeamsFile:
    """Return a new SeamsFile with the named component removed."""
    return SeamsFile(
        components=[c for c in seams.components if c.component != name],
        missing_ct_seams=seams.missing_ct_seams,
    )


def add_missing_ct_seam(
    seams: SeamsFile, entry: MissingCtSeam,
) -> SeamsFile:
    """Return a new SeamsFile with the missing CT seam appended."""
    return SeamsFile(
        components=seams.components,
        missing_ct_seams=[*seams.missing_ct_seams, entry],
    )


def remove_missing_ct_seam(seams: SeamsFile, ct_id: str) -> SeamsFile:
    """Return a new SeamsFile with the given CT seam removed."""
    return SeamsFile(
        components=seams.components,
        missing_ct_seams=[
            m for m in seams.missing_ct_seams if m.ct_id != ct_id
        ],
    )

"""Catalog parsing utilities for catalog.toml and catalog-kinds.toml.

Three-layer structure: Schema (Pydantic models in .claude/scripts/schemas.py),
Kind enums (merged from .claude/catalog-kinds.toml + optional
catalog-kinds.local.toml), and Instances (per-entry CatalogEntry objects in
catalog.toml). The parser loads and validates all three layers and exposes
typed-citation resolution for downstream consumers (chiefly
validate_crc_budget.py for the MAX_DOMAIN_CONCERNS cap).

Specification anchors:
  plans/v5-meso-pivot/00-framework-adoption.md §4.5
  plans/v5-meso-pivot/decisions.md D-13
Schema home: .claude/scripts/schemas.py
"""

import logging
import tomllib
from pathlib import Path

from schemas import (
    Catalog,
    CatalogEntry,
    CatalogKindsFile,
)

logger = logging.getLogger(__name__)


def load_catalog_kinds(
    defaults_path: str = ".claude/catalog-kinds.toml",
    extension_path: str | None = "catalog-kinds.local.toml",
) -> CatalogKindsFile:
    """Load harness defaults + optional project extension; return merged kind enums.

    Merge semantics: union per category; deduplicate; preserve order
    (defaults first, then extension entries that aren't already present).
    Missing extension file is NOT an error -- proceed with defaults only.
    Missing defaults file IS an error (raises FileNotFoundError; every
    consumer project must have the harness defaults).
    """
    defaults_p = Path(defaults_path)
    if not defaults_p.exists():
        raise FileNotFoundError(
            f"catalog-kinds defaults not found: {defaults_path}"
        )

    with defaults_p.open("rb") as fh:
        raw_defaults = tomllib.load(fh)

    defaults = CatalogKindsFile.model_validate(raw_defaults)
    logger.debug("Loaded catalog kind defaults from %s", defaults_path)

    if extension_path is None:
        return defaults

    ext_p = Path(extension_path)
    if not ext_p.exists():
        logger.debug(
            "Extension file %s not found; using defaults only", extension_path
        )
        return defaults

    with ext_p.open("rb") as fh:
        raw_ext = tomllib.load(fh)

    ext = CatalogKindsFile.model_validate(raw_ext)
    logger.debug("Loaded catalog kind extensions from %s", extension_path)

    def _union(base: list[str], additions: list[str]) -> list[str]:
        seen = set(base)
        merged = list(base)
        for item in additions:
            if item not in seen:
                merged.append(item)
                seen.add(item)
        return merged

    return CatalogKindsFile(
        data_stores=_union(defaults.data_stores, ext.data_stores),
        external_systems=_union(defaults.external_systems, ext.external_systems),
        user_surfaces=_union(defaults.user_surfaces, ext.user_surfaces),
        nfr_axes=_union(defaults.nfr_axes, ext.nfr_axes),
    )


def load_catalog(
    path: str = "catalog.toml",
    kinds: CatalogKindsFile | None = None,
) -> Catalog:
    """Load catalog.toml, validate against kind enums, return Catalog model.

    If kinds is None, call load_catalog_kinds() with default paths.
    For every entry, validate that entry.kind is in the merged kind enum
    for its category. Raises ValueError with a structured message naming
    category + entry_name + offending kind on failure. Pydantic-side
    model_validator (entry.name == dict_key) fires automatically.
    Missing catalog file returns an empty Catalog (greenfield projects
    may not have one yet).
    """
    if kinds is None:
        kinds = load_catalog_kinds()

    kind_sets: dict[str, frozenset[str]] = {
        "data_stores": frozenset(kinds.data_stores),
        "external_systems": frozenset(kinds.external_systems),
        "user_surfaces": frozenset(kinds.user_surfaces),
        "nfr_axes": frozenset(kinds.nfr_axes),
    }

    catalog_p = Path(path)
    if not catalog_p.exists():
        return Catalog()

    with catalog_p.open("rb") as fh:
        raw = tomllib.load(fh)

    for category, allowed in kind_sets.items():
        if not allowed:
            continue
        for entry_name, entry_data in raw.get(category, {}).items():
            if not isinstance(entry_data, dict):
                continue
            entry_kind = entry_data.get("kind", "")
            if entry_kind not in allowed:
                msg = (
                    f"catalog kind validation failed: "
                    f"category={category!r}, entry={entry_name!r}, "
                    f"kind={entry_kind!r} not in allowed set"
                )
                raise ValueError(msg)

    catalog = Catalog.model_validate(raw)
    logger.debug("Loaded catalog from %s", path)
    return catalog


def resolve_citation(
    citation: str,
    catalog: Catalog,
) -> CatalogEntry:
    """Resolve a typed `<category>.<entry_name>` citation into the matching entry.

    Parses the citation on the first '.'; raises ValueError if the citation
    isn't typed (no '.'), if the category is unknown, or if the entry_name
    doesn't exist in that category. Returns the concrete subclass instance
    (e.g. ExternalSystemEntry) so callers can inspect category-specific fields.
    """
    if "." not in citation:
        msg = (
            f"citation must be typed as <category>.<entry_name>, "
            f"got {citation!r}"
        )
        raise ValueError(msg)

    category, entry_name = citation.split(".", 1)

    category_map: dict[str, dict] = {
        "data_stores": catalog.data_stores,
        "external_systems": catalog.external_systems,
        "user_surfaces": catalog.user_surfaces,
        "nfr_axes": catalog.nfr_axes,
    }

    if category not in category_map:
        msg = (
            f"unknown catalog category {category!r} in citation {citation!r}; "
            f"valid categories: {sorted(category_map)}"
        )
        raise ValueError(msg)

    entries = category_map[category]
    if entry_name not in entries:
        msg = (
            f"entry {entry_name!r} not found in category {category!r}; "
            f"available: {sorted(entries)}"
        )
        raise ValueError(msg)

    return entries[entry_name]

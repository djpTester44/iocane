"""Symbols registry I/O for plans/symbols.yaml.

YAML-based symbol I/O with Pydantic validation. Provides query helpers
used by the architect (at authoring time) and Tier-3 generators (at
read time) so no cross-CP identifier is inferred.

Used by hooks, scripts, and commands via ``uv run python -c "..."``.
"""

from collections import defaultdict
from pathlib import Path

import yaml
from schemas import Symbol, SymbolKind, SymbolsFile

# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------


def load_symbols(path: str) -> SymbolsFile:
    """Load and validate plans/symbols.yaml."""
    text = Path(path).read_text(encoding="utf-8")
    if not text.strip():
        return SymbolsFile()
    raw = yaml.safe_load(text)
    if raw is None:
        return SymbolsFile()
    return SymbolsFile.model_validate(raw)


def save_symbols(path: str, registry: SymbolsFile) -> None:
    """Serialize symbols registry to YAML and write to disk."""
    data = registry.model_dump(mode="json", exclude_none=True)
    for _name, sym in data.get("symbols", {}).items():
        if not sym.get("used_by"):
            sym.pop("used_by", None)
        if not sym.get("used_by_cps"):
            sym.pop("used_by_cps", None)
    output = yaml.dump(
        data, default_flow_style=False, sort_keys=False, allow_unicode=True
    )
    Path(path).write_text(output, encoding="utf-8")


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


def get_symbol(registry: SymbolsFile, name: str) -> Symbol | None:
    """Return the symbol declaration for ``name`` or None."""
    return registry.symbols.get(name)


def symbols_by_kind(registry: SymbolsFile, kind: SymbolKind) -> dict[str, Symbol]:
    """Return all symbols of the given kind keyed by name."""
    return {
        name: sym for name, sym in registry.symbols.items() if sym.kind == kind
    }


def symbols_used_by(registry: SymbolsFile, component: str) -> dict[str, Symbol]:
    """Return every symbol that names ``component`` in its used_by list."""
    return {
        name: sym
        for name, sym in registry.symbols.items()
        if component in sym.used_by
    }


def symbols_used_by_cp(registry: SymbolsFile, cp_id: str) -> dict[str, Symbol]:
    """Return every symbol whose checkpoint backfill names ``cp_id``."""
    return {
        name: sym
        for name, sym in registry.symbols.items()
        if cp_id in sym.used_by_cps
    }


# ---------------------------------------------------------------------------
# Conflict detection
# ---------------------------------------------------------------------------


def detect_env_var_conflicts(registry: SymbolsFile) -> dict[str, list[str]]:
    """Return env_var names that are claimed by more than one Settings field.

    An env_var colliding across two fields corrupts Settings loading --
    the last-loaded value wins silently. Returned mapping is
    ``env_var -> [symbol names that claim it]``.
    """
    env_claimants: dict[str, list[str]] = defaultdict(list)
    for name, sym in registry.symbols.items():
        if sym.kind == SymbolKind.SETTINGS_FIELD and sym.env_var:
            env_claimants[sym.env_var].append(name)
    return {env: names for env, names in env_claimants.items() if len(names) > 1}


def detect_message_pattern_conflicts(
    registry: SymbolsFile,
) -> dict[str, list[str]]:
    """Return message patterns reused across error_message symbols.

    Reusing the same literal error string from two different exception
    call sites makes log-based triage ambiguous. Returned mapping is
    ``pattern -> [symbol names that share it]``.
    """
    pattern_claimants: dict[str, list[str]] = defaultdict(list)
    for name, sym in registry.symbols.items():
        if sym.kind == SymbolKind.ERROR_MESSAGE and sym.message_pattern:
            pattern_claimants[sym.message_pattern].append(name)
    return {
        pattern: names
        for pattern, names in pattern_claimants.items()
        if len(names) > 1
    }

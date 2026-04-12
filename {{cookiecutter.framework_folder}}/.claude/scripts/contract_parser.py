"""Contract parsing utilities for plans/component-contracts.yaml.

YAML-based contract I/O with Pydantic validation.

Used by hooks, scripts, and commands via ``uv run python -c "..."``.
"""

from pathlib import Path

import yaml
from schemas import ComponentContractsFile

# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------


def load_contracts(path: str) -> ComponentContractsFile:
    """Load and validate plans/component-contracts.yaml."""
    p = Path(path)
    if not p.exists():
        return ComponentContractsFile()
    text = p.read_text(encoding="utf-8")
    if not text.strip():
        return ComponentContractsFile()
    raw = yaml.safe_load(text)
    if raw is None:
        return ComponentContractsFile()
    return ComponentContractsFile.model_validate(raw)


def save_contracts(path: str, contracts: ComponentContractsFile) -> None:
    """Serialize contracts to YAML and write to disk."""
    data = contracts.model_dump(mode="json")
    # Strip empty optional fields for readability
    for comp in data.get("components", {}).values():
        if not comp.get("collaborators"):
            comp.pop("collaborators", None)
        if not comp.get("composition_root"):
            comp.pop("composition_root", None)
        if not comp.get("protocol"):
            comp.pop("protocol", None)
        if not comp.get("responsibilities"):
            comp.pop("responsibilities", None)
        if not comp.get("must_not"):
            comp.pop("must_not", None)
        if not comp.get("features"):
            comp.pop("features", None)
    output = yaml.dump(
        data, default_flow_style=False, sort_keys=False, allow_unicode=True,
    )
    Path(path).write_text(output, encoding="utf-8")

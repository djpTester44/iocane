"""
Verify that pyproject.toml declares [[tool.mypy.overrides]] entries for any
installed packages that use implicit PEP 420 namespace packages (google.*,
grpc.*). Without these overrides, mypy crashes internally with:

    AssertionError: Cannot find module for google

instead of a clean user-facing error.
"""

import tomllib
from pathlib import Path

import pytest

# Maps a required mypy module-pattern to the PyPI package name prefixes that
# trigger the need for it. A project is flagged when ANY matching dep is found.
NAMESPACE_RULES: dict[str, list[str]] = {
    "google.*": [
        "google-cloud-",
        "google-auth",
        "googleapis-common-protos",
        "google-api-core",
        "google-crc32c",
        "protobuf",
    ],
    "grpc.*": [
        "grpcio",
        "opentelemetry-exporter-otlp-proto-grpc",
    ],
}


def _load_pyproject() -> dict:
    path = Path(__file__).parents[2] / "pyproject.toml"
    # .agent/tests/ -> .agent/ -> project root
    with path.open("rb") as fh:
        return tomllib.load(fh)


def _dep_names(data: dict) -> list[str]:
    """Return normalised bare package names from all dependency groups."""
    raw: list[str] = list(data.get("project", {}).get("dependencies", []))
    for group in data.get("dependency-groups", {}).values():
        for entry in group:
            if isinstance(entry, str):
                raw.append(entry)
    return [
        d.split(";")[0]
        .split(">=")[0].split("<=")[0].split("==")[0]
        .split("!=")[0].split(">")[0].split("<")[0]
        .strip().lower()
        for d in raw
    ]


def _override_modules(data: dict) -> set[str]:
    overrides = data.get("tool", {}).get("mypy", {}).get("overrides", [])
    result: set[str] = set()
    for entry in overrides:
        module = entry.get("module")
        if isinstance(module, str):
            result.add(module)
        elif isinstance(module, list):
            result.update(module)
    return result


def _required_overrides() -> list[tuple[str, str]]:
    """Return [(module_pattern, triggering_dep)] pairs that are needed but absent."""
    data = _load_pyproject()
    dep_names = _dep_names(data)
    existing = _override_modules(data)
    missing: list[tuple[str, str]] = []

    for pattern, triggers in NAMESPACE_RULES.items():
        if pattern in existing:
            continue
        for dep in dep_names:
            for trigger in triggers:
                if dep == trigger.lower() or dep.startswith(trigger.lower()):
                    missing.append((pattern, dep))
                    break
            else:
                continue
            break

    return missing


@pytest.mark.parametrize("pattern,dep", _required_overrides() or [pytest.param(None, None, marks=pytest.mark.skip(reason="all required mypy overrides are present"))])
def test_mypy_override_present(pattern: str, dep: str) -> None:
    """Each namespace-collision package requires a matching mypy override."""
    assert False, (
        f'Dependency "{dep}" requires [[tool.mypy.overrides]] in pyproject.toml:\n\n'
        f"  [[tool.mypy.overrides]]\n"
        f'  module = "{pattern}"\n'
        f"  ignore_missing_imports = true"
    )

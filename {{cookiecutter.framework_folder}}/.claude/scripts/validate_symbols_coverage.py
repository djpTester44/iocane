"""validate_symbols_coverage.py

Verifies coverage, conflict-freedom, and used_by health across the symbol
registry and component contracts.

  1. Every project-custom exception type referenced in a component's
     ``raises`` list is declared in ``symbols.yaml`` as
     ``kind=exception_class``.
  2. The symbol registry has no ``env_var`` or ``message_pattern``
     conflicts across settings_field / error_message symbols.
  3. Every ``used_by`` list entry in ``symbols.yaml`` resolves to a
     declared symbol or component name (referential integrity).
  4. Every component that cites a symbol in its ``responsibilities`` or
     ``raises`` surfaces appears in that symbol's ``used_by`` list
     (reciprocity).

Builtin and stdlib-module exceptions (e.g., ValueError,
subprocess.CalledProcessError, json.JSONDecodeError, socket.gaierror)
are treated as canonical Python vocabulary and skipped -- they are
already shared across CPs by the interpreter and stdlib docs.

Exit codes:
  0 -- all checks pass.
  1 -- uncovered project-custom exception OR env_var/message_pattern conflict.
  2 -- used_by referential integrity OR reciprocity drift.
       (Tie-break: 1 wins if both classes fail in the same run.)

Usage:
    uv run python .claude/scripts/validate_symbols_coverage.py
"""

import argparse
import builtins
import re
import sys
from pathlib import Path

from contract_parser import load_contracts
from schemas import ComponentContractsFile, SymbolKind, SymbolsFile
from symbols_parser import (
    detect_env_var_conflicts,
    detect_message_pattern_conflicts,
    load_symbols,
)


def _builtin_exceptions() -> frozenset[str]:
    """Return all builtin exception class names."""
    return frozenset(
        name
        for name in dir(builtins)
        if isinstance(getattr(builtins, name), type)
        and issubclass(getattr(builtins, name), BaseException)
    )


BUILTIN_EXCEPTIONS = _builtin_exceptions()


def is_stdlib_exception(name: str) -> bool:
    """Return True if ``name`` is a builtin or stdlib-module exception.

    - Bare names like ``ValueError`` -> checked against ``builtins``.
    - Dotted names like ``subprocess.CalledProcessError`` -> first
      segment checked against ``sys.stdlib_module_names`` (Python 3.10+).

    Project-custom exceptions are by construction NOT in ``builtins``
    and not in ``stdlib_module_names``, so they fall through to the
    coverage check.
    """
    if name in BUILTIN_EXCEPTIONS:
        return True
    if "." in name:
        module = name.split(".", 1)[0]
        return module in sys.stdlib_module_names
    return False


def _check_used_by_integrity(
    registry: SymbolsFile, contracts: ComponentContractsFile
) -> bool:
    """Check that every used_by entry resolves to a declared symbol or component."""
    declared_names = set(registry.symbols.keys()) | set(contracts.components.keys())
    failed = False
    for symbol_name, sym in registry.symbols.items():
        for name in sym.used_by:
            if name not in declared_names:
                sys.stderr.write(
                    f"FAIL: symbol '{symbol_name}'.used_by references '{name}' but no "
                    f"symbol or component is declared with that name "
                    f"(referential integrity)\n"
                )
                failed = True
    return failed


def _check_used_by_reciprocity(
    registry: SymbolsFile, contracts: ComponentContractsFile
) -> bool:
    """Check that components citing a symbol appear in its used_by list.

    Citation surfaces are decision-bearing only: structured ``raises[]``
    (exception class names; explicit list, not prose) and ``Settings.X``
    regex in ``responsibilities`` + ``raises`` prose (canonical citation
    form per io-architect.md authoring directive).

    Bare exception-class and shared-type name mentions in prose are
    intentionally NOT walked: they collide with English vocabulary
    (Item, Result, Pipeline, Connector, etc.) producing false-positive
    reciprocity findings on incidental prose. Per D-26, the structured
    raises[] surface carries the architectural citation; prose is for
    human readers.
    """
    exception_names = {
        n for n, s in registry.symbols.items() if s.kind == SymbolKind.EXCEPTION_CLASS
    }
    settings_field_names = {
        n for n, s in registry.symbols.items() if s.kind == SymbolKind.SETTINGS_FIELD
    }

    cite_map: dict[str, set[str]] = {}

    for comp_name, comp in contracts.components.items():
        for raises_entry in comp.raises:
            base = raises_entry.rsplit(".", 1)[-1]
            if base in exception_names:
                cite_map.setdefault(base, set()).add(comp_name)

        for prose in comp.responsibilities + list(comp.raises):
            for match in re.finditer(r"\bSettings\.(\w+)\b", prose):
                field = match.group(1)
                if field in settings_field_names:
                    cite_map.setdefault(field, set()).add(comp_name)

    failed = False
    for symbol_name, citing_comps in cite_map.items():
        declared_used_by = set(registry.symbols[symbol_name].used_by)
        missing = sorted(citing_comps - declared_used_by)
        for comp_name in missing:
            sys.stderr.write(
                f"FAIL: component '{comp_name}' cites symbol '{symbol_name}' (in "
                f"responsibilities or raises) but '{comp_name}' is absent from "
                f"'{symbol_name}'.used_by (reciprocity)\n"
            )
            failed = True
    return failed


def validate_from_objects(
    registry,
    contracts,
    contracts_label: str = "component-contracts.yaml",
) -> int:
    """Run coverage + conflict validation on pre-loaded objects.

    Callers that have already parsed ``symbols.yaml`` and
    ``component-contracts.yaml`` pass the objects through so the
    validator operates on the SAME view the downstream code will
    act on -- no re-reads, no TOCTOU. ``main()`` below is a thin
    CLI wrapper that loads the files and delegates here.

    Returns exit code 0 (PASS), 1 (existing-class FAIL), or 2 (used_by drift).
    """
    declared: set[str] = {
        name
        for name, sym in registry.symbols.items()
        if sym.kind == SymbolKind.EXCEPTION_CLASS
    }

    raised_in_contracts: dict[str, list[str]] = {}
    components_with_raises = 0
    for comp_name, comp in contracts.components.items():
        if not comp.raises:
            continue
        components_with_raises += 1
        for full_name in comp.raises:
            if is_stdlib_exception(full_name):
                continue
            base_name = full_name.rsplit(".", 1)[-1]
            raised_in_contracts.setdefault(base_name, []).append(comp_name)

    if not contracts.components:
        sys.stderr.write(
            "FAIL: nothing to validate -- no components authored in "
            f"{contracts_label}. Author ComponentContract entries "
            "before validating symbol coverage.\n"
        )
        return 1

    uncovered = sorted(set(raised_in_contracts) - declared)
    env_conflicts = detect_env_var_conflicts(registry)
    msg_conflicts = detect_message_pattern_conflicts(registry)

    existing_failed = False
    for exc in uncovered:
        sources = raised_in_contracts.get(exc, [])
        sys.stderr.write(
            f"FAIL: exception '{exc}' raised in {', '.join(sources)} but "
            f"not declared in symbols.yaml as kind=exception_class\n"
        )
        existing_failed = True
    for env_var, claimants in env_conflicts.items():
        sys.stderr.write(
            f"FAIL: env_var '{env_var}' claimed by multiple settings_field "
            f"symbols: {', '.join(claimants)}\n"
        )
        existing_failed = True
    for pattern, claimants in msg_conflicts.items():
        sys.stderr.write(
            f"FAIL: error_message pattern '{pattern}' shared by symbols: "
            f"{', '.join(claimants)}\n"
        )
        existing_failed = True

    new_failed = _check_used_by_integrity(registry, contracts)
    new_failed |= _check_used_by_reciprocity(registry, contracts)

    if existing_failed:
        return 1
    if new_failed:
        return 2
    sys.stdout.write(
        f"PASS: {len(raised_in_contracts)} project-custom exception type(s) "
        f"declared; no env_var or message_pattern conflicts; "
        f"used_by referential integrity + reciprocity OK.\n"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry -- loads files from paths and delegates to validate_from_objects.

    Script callers (``uv run python validate_symbols_coverage.py``)
    reach this path. Library callers with pre-loaded objects should
    call ``validate_from_objects`` directly to avoid a re-read that
    diverges from their in-memory view.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Verify project-custom raises types declared on "
            "ComponentContract.raises are registered in symbols.yaml "
            "and the registry has no conflicts."
        )
    )
    parser.add_argument("--symbols", default="plans/symbols.yaml")
    parser.add_argument(
        "--contracts", default="plans/component-contracts.yaml"
    )
    args = parser.parse_args(argv)

    symbols_path = Path(args.symbols)
    if not symbols_path.exists():
        sys.stderr.write(f"FAIL: symbols file not found: {symbols_path}\n")
        return 1

    registry = load_symbols(str(symbols_path))
    contracts_path = Path(args.contracts)
    contracts = (
        load_contracts(str(contracts_path))
        if contracts_path.exists()
        else ComponentContractsFile()
    )

    return validate_from_objects(
        registry,
        contracts,
        contracts_label=str(contracts_path),
    )


if __name__ == "__main__":
    sys.exit(main())

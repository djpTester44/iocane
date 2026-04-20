"""validate_test_plan_completeness.py

Verifies that every Protocol method has at least one TestPlanEntry with
at least one TestInvariant in `plans/test-plan.yaml`. The set of
Protocol methods is unioned from two sources:

1. ``plans/component-contracts.yaml`` (authoritative under v3 -- every
   ``ComponentContract`` with ``protocol:`` set carries its method
   surface on ``ComponentContract.methods[]``).
2. ``interfaces/*.pyi`` (rendered downstream output; present only after
   ``/io-gen-protocols`` has run).

On a greenfield architect run (substage H-post-validate timing),
``interfaces/`` does not yet exist -- the architect hands .pyi emission
to ``/io-gen-protocols``. This is expected and NOT a FAIL. The YAML
source alone is sufficient to evaluate completeness. When ``interfaces/``
does exist (post-codegen), both sources are unioned so a method present
only in YAML (not yet regenerated) is still required to have invariant
coverage.

Per legacy Step H-7 authoring rules, methods that were intentionally
left without invariants carried ``# noqa: TEST_PLAN`` on the .pyi def
line. v3 retires that deferral mechanism at the architect stage; the
marker is still honored when ``interfaces/`` exists so existing projects
do not regress, but new authoring should populate the entry rather than
defer.

Exit codes:
  0 -- every Protocol method is covered (or explicitly deferred).
  1 -- one or more methods are uncovered without deferral, or neither
       source contains any methods (nothing to validate).

Usage:
    uv run python .claude/scripts/validate_test_plan_completeness.py
"""

import argparse
import ast
import re
import sys
from pathlib import Path

from contract_parser import load_contracts
from schemas import ComponentContractsFile
from test_plan_parser import load_test_plan, methods_missing_invariants

NOQA_TEST_PLAN_RE = re.compile(r"#\s*noqa:\s*TEST_PLAN\b")


def collect_protocol_aliases(tree: ast.AST) -> set[str]:
    """Return every local name that resolves to ``typing.Protocol``.

    Always includes the bare ``Protocol`` (assumed imported from
    typing). Adds any aliases introduced via
    ``from typing import Protocol as P``.
    """
    aliases: set[str] = {"Protocol"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "typing":
            for alias in node.names:
                if alias.name == "Protocol":
                    aliases.add(alias.asname or alias.name)
    return aliases


def is_protocol_class(node: ast.ClassDef, aliases: set[str]) -> bool:
    """Detect every common Protocol inheritance form.

    Handles:
    - ``class Foo(Protocol):`` -- ast.Name
    - ``class Foo(typing.Protocol):`` -- ast.Attribute
    - ``class Foo(Protocol[T]):`` -- ast.Subscript over Name
    - ``class Foo(typing.Protocol[T]):`` -- ast.Subscript over Attribute
    - ``class Foo(P):`` where ``from typing import Protocol as P`` --
      via ``aliases``
    """
    for base in node.bases:
        if isinstance(base, ast.Name) and base.id in aliases:
            return True
        if isinstance(base, ast.Attribute) and base.attr == "Protocol":
            return True
        if isinstance(base, ast.Subscript):
            value = base.value
            if isinstance(value, ast.Name) and value.id in aliases:
                return True
            if isinstance(value, ast.Attribute) and value.attr == "Protocol":
                return True
    return False


def normalize_protocol_path(pyi_path: Path) -> str:
    """Anchor the path at ``interfaces/`` so it matches test-plan.yaml."""
    key = pyi_path.as_posix()
    idx = key.rfind("interfaces/")
    if idx >= 0:
        key = key[idx:]
    return key


def extract_protocol_methods(
    interfaces_dir: Path,
) -> tuple[dict[str, set[str]], dict[tuple[str, str], bool]]:
    """Return (methods_by_protocol, deferred) maps.

    ``methods_by_protocol`` maps protocol path (e.g.
    ``interfaces/router.pyi``) to the set of Protocol method names.
    ``deferred`` maps (protocol_path, method_name) to True when the
    `def` line carries ``# noqa: TEST_PLAN``.

    Methods starting with ``_`` are excluded as private helpers, EXCEPT
    ``__init__`` which IS included per io-architect Step H-7 guidance
    ("including ``__init__`` where behavior is non-trivial").
    """
    methods: dict[str, set[str]] = {}
    deferred: dict[tuple[str, str], bool] = {}
    for pyi_path in interfaces_dir.glob("*.pyi"):
        protocol_key = normalize_protocol_path(pyi_path)
        text = pyi_path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(text, filename=str(pyi_path))
        except SyntaxError as exc:
            sys.stderr.write(
                f"WARN: failed to parse {pyi_path}: {exc}\n"
            )
            continue
        aliases = collect_protocol_aliases(tree)
        lines = text.splitlines()
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            if not is_protocol_class(node, aliases):
                continue
            for item in node.body:
                if not isinstance(
                    item, (ast.FunctionDef, ast.AsyncFunctionDef)
                ):
                    continue
                name = item.name
                if name.startswith("_") and name != "__init__":
                    continue
                methods.setdefault(protocol_key, set()).add(name)
                line_idx = item.lineno - 1
                if 0 <= line_idx < len(lines) and NOQA_TEST_PLAN_RE.search(
                    lines[line_idx]
                ):
                    deferred[(protocol_key, name)] = True
    return methods, deferred


def derive_methods_from_contracts(
    contracts: ComponentContractsFile,
) -> dict[str, set[str]]:
    """Return protocol_path -> method_name set from component-contracts.yaml.

    Walks every ``ComponentContract`` with a non-empty ``protocol`` and
    ``methods`` list, using the normalized protocol path as the key and
    ``MethodSpec.name`` as the method set. Key format matches
    ``normalize_protocol_path`` so the contracts-derived map can be
    unioned with the .pyi-derived map.

    Methods whose name starts with ``_`` are excluded as private
    helpers, EXCEPT ``__init__`` which IS included per io-architect
    Step H-7 guidance.
    """
    result: dict[str, set[str]] = {}
    for comp in contracts.components.values():
        if not comp.protocol:
            continue
        key = comp.protocol
        idx = key.rfind("interfaces/")
        if idx >= 0:
            key = key[idx:]
        for m in comp.methods:
            if m.name.startswith("_") and m.name != "__init__":
                continue
            result.setdefault(key, set()).add(m.name)
    return result


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(
        description=(
            "Verify every Protocol method has a covering TestPlanEntry "
            "in plans/test-plan.yaml."
        )
    )
    parser.add_argument(
        "--test-plan",
        default="plans/test-plan.yaml",
        help="Path to test-plan.yaml.",
    )
    parser.add_argument(
        "--interfaces",
        default="interfaces",
        help=(
            "Directory containing Protocol .pyi files. Absence is "
            "expected at architect stage pre-/io-gen-protocols; YAML "
            "source alone is used."
        ),
    )
    parser.add_argument(
        "--contracts",
        default="plans/component-contracts.yaml",
        help="Path to component-contracts.yaml (authoritative method source).",
    )
    args = parser.parse_args(argv)

    plan_path = Path(args.test_plan)
    if not plan_path.exists():
        sys.stderr.write(f"FAIL: test-plan file not found: {plan_path}\n")
        return 1

    contracts_path = Path(args.contracts)
    contracts = (
        load_contracts(str(contracts_path))
        if contracts_path.exists()
        else ComponentContractsFile()
    )
    yaml_methods = derive_methods_from_contracts(contracts)

    interfaces_dir = Path(args.interfaces)
    if interfaces_dir.exists():
        pyi_methods, deferred = extract_protocol_methods(interfaces_dir)
    else:
        pyi_methods, deferred = {}, {}

    # Union the two sources so a method present in either counts.
    methods_by_protocol: dict[str, set[str]] = {}
    for protocol, names in yaml_methods.items():
        methods_by_protocol.setdefault(protocol, set()).update(names)
    for protocol, names in pyi_methods.items():
        methods_by_protocol.setdefault(protocol, set()).update(names)

    if not methods_by_protocol:
        sys.stderr.write(
            "FAIL: nothing to validate -- no methods in "
            f"{contracts_path} and no Protocol methods under "
            f"{interfaces_dir}. Author ComponentContract.methods[] "
            "entries before validating test-plan completeness.\n"
        )
        return 1

    plan = load_test_plan(str(plan_path))
    gaps = methods_missing_invariants(plan, methods_by_protocol)

    failed = False
    for protocol, missing in gaps.items():
        for method in missing:
            if deferred.get((protocol, method)):
                sys.stdout.write(
                    f"INFO: {protocol}::{method} deferred via "
                    f"# noqa: TEST_PLAN\n"
                )
                continue
            sys.stderr.write(
                f"FAIL: no TestPlanEntry for {protocol}::{method}\n"
            )
            failed = True

    if not failed:
        total_methods = sum(len(s) for s in methods_by_protocol.values())
        sys.stdout.write(
            f"PASS: every covered Protocol method has at least one "
            f"invariant ({total_methods} total).\n"
        )
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())

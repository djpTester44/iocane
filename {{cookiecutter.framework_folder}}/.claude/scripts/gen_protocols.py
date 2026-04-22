"""gen_protocols.py

Emit one ``interfaces/<stem>.pyi`` per Protocol-bearing component by
rendering ``harness/templates/interface.pyi.template`` (jinja2) with
data drawn from ``plans/component-contracts.yaml`` (components +
method signatures + CRC responsibilities), ``plans/symbols.yaml``
(exception + shared-type imports), and ``plans/test-plan.yaml``
(per-method error_propagation invariants -> docstring Raises
trigger descriptions).

Import resolution for a type name referenced in a ``MethodSpec``
signature walks three tables in order:

1. Python builtins (``_BUILTIN_TYPES``) -- no import emitted.
2. Project symbols (``symbols.yaml`` with ``declared_in: src/...``) --
   ``from <module> import <name>``.
3. Known stdlib / typing / ``collections.abc`` types
   (``_STDLIB_IMPORTS``) -- ``from <module> import <name>``.
4. Unknown -- stderr ``WARN:``; the operator either declares the name
   in ``symbols.yaml`` or extends the stdlib table.

Emitted imports are ordered stdlib-first then project, alphabetical
within each group, matching the style the YAML-authored interfaces
carry through consumer tooling (pyright, mypy strict).

Idempotent: same YAML input produces byte-identical output.

Invocation: ``uv run python harness/scripts/gen_protocols.py``. Driven
by the ``/io-gen-protocols`` command, which sets
``IOCANE_ROLE=gen_protocols`` so that ``interfaces-codegen-only.sh``
admits the writes.

Exit codes:
  0 -- emission succeeded (or no Protocol-bearing components present).
  1 -- missing input file or template; fail-fast before any write.
"""

import argparse
import ast
import re
import sys
from pathlib import Path

import jinja2
from contract_parser import load_contracts
from schemas import (
    ComponentContract,
    InvariantKind,
    MethodSpec,
    Symbol,
    SymbolKind,
    TestPlanFile,
)
from symbols_parser import load_symbols
from test_plan_parser import invariants_for_method, load_test_plan

_PASCAL_SPLIT_RE = re.compile(r"[_\-\s]+")
_IDENTIFIER_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\b")
_PROTOCOL_SUFFIX = "Protocol"
_MISSING_TRIGGER = "[trigger condition -- see test-plan invariant]"

# Python builtin types / type-expression tokens that never need import.
_BUILTIN_TYPES: frozenset[str] = frozenset(
    {
        "list",
        "dict",
        "tuple",
        "set",
        "frozenset",
        "int",
        "float",
        "str",
        "bool",
        "bytes",
        "bytearray",
        "complex",
        "type",
        "None",
        "object",
        "NotImplemented",
        "Ellipsis",
        "True",
        "False",
        "range",
        "slice",
        "memoryview",
        "property",
    }
)

# Known stdlib / typing / collections.abc type names -> import module.
# Generics migrated to collections.abc in PEP 585 are routed there rather
# than to the deprecated typing aliases.
_STDLIB_IMPORTS: dict[str, str] = {
    # datetime
    "datetime": "datetime",
    "date": "datetime",
    "time": "datetime",
    "timedelta": "datetime",
    "timezone": "datetime",
    "tzinfo": "datetime",
    # collections.abc (modern generic ABCs; preferred over typing aliases)
    "Callable": "collections.abc",
    "Mapping": "collections.abc",
    "MutableMapping": "collections.abc",
    "Sequence": "collections.abc",
    "MutableSequence": "collections.abc",
    "Iterable": "collections.abc",
    "Iterator": "collections.abc",
    "AsyncIterable": "collections.abc",
    "AsyncIterator": "collections.abc",
    "Awaitable": "collections.abc",
    "Coroutine": "collections.abc",
    "Set": "collections.abc",
    "MutableSet": "collections.abc",
    "Container": "collections.abc",
    "Collection": "collections.abc",
    "Hashable": "collections.abc",
    "Sized": "collections.abc",
    "Reversible": "collections.abc",
    "Generator": "collections.abc",
    "AsyncGenerator": "collections.abc",
    "ItemsView": "collections.abc",
    "KeysView": "collections.abc",
    "ValuesView": "collections.abc",
    # typing (non-ABC utilities)
    "Any": "typing",
    "Optional": "typing",
    "Union": "typing",
    "Literal": "typing",
    "TypeVar": "typing",
    "Generic": "typing",
    "ClassVar": "typing",
    "Final": "typing",
    "Annotated": "typing",
    "NewType": "typing",
    "Protocol": "typing",
    "runtime_checkable": "typing",
    "cast": "typing",
    "overload": "typing",
    "TypedDict": "typing",
    "NamedTuple": "typing",
    "TypeAlias": "typing",
    "ParamSpec": "typing",
    "Concatenate": "typing",
    "Self": "typing",
    "Never": "typing",
    "LiteralString": "typing",
    "TYPE_CHECKING": "typing",
    # pathlib
    "Path": "pathlib",
    "PurePath": "pathlib",
    "PurePosixPath": "pathlib",
    "PureWindowsPath": "pathlib",
    "PosixPath": "pathlib",
    "WindowsPath": "pathlib",
    # uuid
    "UUID": "uuid",
    # decimal
    "Decimal": "decimal",
    # enum
    "Enum": "enum",
    "IntEnum": "enum",
    "Flag": "enum",
    "IntFlag": "enum",
    "StrEnum": "enum",
    # fractions
    "Fraction": "fractions",
}


def _pascal_case(name: str) -> str:
    """Convert snake_case / kebab-case / mixed to PascalCase."""
    if not name:
        return name
    parts = [p for p in _PASCAL_SPLIT_RE.split(name) if p]
    return "".join(p[:1].upper() + p[1:] for p in parts)


def _protocol_class_name(component_name: str, protocol_path: str) -> str:
    """Derive the Protocol class name.

    Mechanical rule: PascalCase(component_name) + 'Protocol'. Falls
    back to the protocol file stem if component_name is empty.
    """
    base = component_name or Path(protocol_path).stem
    return _pascal_case(base) + _PROTOCOL_SUFFIX


def _py_module_path(declared_in: str) -> str:
    """Translate ``declared_in`` to a Python import path.

    Path-shaped inputs (``src/foo/bar.py``, ``tests/conftest.py``)
    are converted dot-separated by stripping the ``.py`` suffix and
    joining path parts. Bare module names (``pydantic``,
    ``sqlalchemy.orm``) are used verbatim for external-package
    imports -- a consumer declares ``declared_in: pydantic`` for a
    third-party type and the codegen emits ``from pydantic import
    <Name>``.

    The disambiguation is carried by the presence of ``/`` (after
    separator normalization) or a ``.py`` suffix; the
    ``check_declared_in_zone`` validator rejects the most likely
    ambiguous input (``src.foo.bar`` dotted-path) at schema load so
    this function does not see it.
    """
    normalized = declared_in.replace("\\", "/")
    if "/" in normalized or declared_in.endswith(".py"):
        stripped = Path(declared_in).with_suffix("")
        return ".".join(stripped.parts)
    return declared_in


def _extract_type_names(type_expr: str) -> set[str]:
    """Return every bare identifier used in a type annotation string.

    Parses ``type_expr`` as a Python expression and walks ``ast.Name``
    nodes -- robust to subscripts (``list[int]``), unions (``str | None``),
    callables (``Callable[[int], str]``), and nested generics. Falls back
    to a permissive identifier regex when the string does not parse as
    Python; unknown names surface as a stderr warning in
    ``_build_imports`` rather than being silently dropped.
    """
    if not type_expr:
        return set()
    try:
        tree = ast.parse(type_expr, mode="eval")
    except SyntaxError:
        return set(_IDENTIFIER_RE.findall(type_expr))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
    return names


def _collect_referenced_names(method: MethodSpec) -> set[str]:
    """Return every identifier referenced in a method's signature.

    Walks ``args[].type_expr``, ``return_type``, and ``raises``. Callers
    filter against symbols.yaml + the stdlib resolution table to decide
    which names require imports.
    """
    names: set[str] = set()
    for arg in method.args:
        names.update(_extract_type_names(arg.type_expr))
    names.update(_extract_type_names(method.return_type))
    names.update(method.raises)
    return names


def _build_imports(
    methods: list[MethodSpec], symbols: dict[str, Symbol]
) -> list[tuple[str, list[str]]]:
    """Return the imports to emit, ordered deterministically.

    Resolution order for each referenced name:

    1. Python builtin (``list``, ``int``, ``None`` ...) -- no import.
    2. Project symbol declared in ``symbols.yaml`` as ``shared_type``
       or ``exception_class`` with a non-empty ``declared_in`` -- emit
       ``from <module> import <name>``.
    3. Known stdlib / typing / ``collections.abc`` type (see
       ``_STDLIB_IMPORTS``) -- emit the mapped ``from <module> import
       <name>``.
    4. Unknown -- stderr warning; skip. The operator must either
       declare the name in ``symbols.yaml`` or extend ``_STDLIB_IMPORTS``.

    Module-block ordering: stdlib modules first (alphabetical), then
    project modules (alphabetical). Names within each module sorted
    alphabetically. The returned ``list[tuple[str, list[str]]]`` is
    rendered verbatim by the template in this order.
    """
    referenced: set[str] = set()
    for method in methods:
        referenced.update(_collect_referenced_names(method))

    importable = {SymbolKind.SHARED_TYPE, SymbolKind.EXCEPTION_CLASS}
    stdlib_by_module: dict[str, set[str]] = {}
    project_by_module: dict[str, set[str]] = {}
    unknown: set[str] = set()

    for name in referenced:
        if name in _BUILTIN_TYPES:
            continue
        sym = symbols.get(name)
        if (
            sym is not None
            and sym.kind in importable
            and sym.declared_in
        ):
            module = _py_module_path(sym.declared_in)
            project_by_module.setdefault(module, set()).add(name)
            continue
        if name in _STDLIB_IMPORTS:
            stdlib_by_module.setdefault(
                _STDLIB_IMPORTS[name], set()
            ).add(name)
            continue
        unknown.add(name)

    for name in sorted(unknown):
        sys.stderr.write(
            f"WARN: gen_protocols: referenced name {name!r} is neither "
            "a Python builtin, a declared symbols.yaml entry, nor a "
            "known stdlib type. Declare it in plans/symbols.yaml or "
            "extend _STDLIB_IMPORTS in "
            "harness/scripts/gen_protocols.py.\n"
        )

    ordered: list[tuple[str, list[str]]] = []
    for module in sorted(stdlib_by_module):
        ordered.append((module, sorted(stdlib_by_module[module])))
    for module in sorted(project_by_module):
        ordered.append((module, sorted(project_by_module[module])))
    return ordered


def _raises_with_triggers(
    method: MethodSpec, test_plan: TestPlanFile, protocol_path: str
) -> list[tuple[str, str]]:
    """Return ``[(exc_name, trigger_description), ...]`` for the method.

    Trigger descriptions come from test-plan invariants of kind
    ``error_propagation`` whose description mentions the exception name.
    When no matching invariant exists, a placeholder is emitted so the
    docstring remains well-formed (architect can enrich later).
    """
    if not method.raises:
        return []
    invariants = invariants_for_method(test_plan, protocol_path, method.name)
    result: list[tuple[str, str]] = []
    for exc in method.raises:
        trigger = _MISSING_TRIGGER
        exc_pattern = re.compile(rf"\b{re.escape(exc)}\b")
        for inv in invariants:
            if inv.kind != InvariantKind.ERROR_PROPAGATION:
                continue
            if exc_pattern.search(inv.description):
                trigger = inv.description
                break
        result.append((exc, trigger))
    return result


def _prepare_methods(
    methods: list[MethodSpec],
    test_plan: TestPlanFile,
    protocol_path: str,
) -> list[dict[str, object]]:
    """Package methods + computed fields for template consumption."""
    packaged: list[dict[str, object]] = []
    for m in methods:
        packaged.append(
            {
                "name": m.name,
                "args": m.args,
                "return_type": m.return_type,
                "raises": m.raises,
                "docstring": m.docstring,
                "raises_with_triggers": _raises_with_triggers(
                    m, test_plan, protocol_path
                ),
            }
        )
    return packaged


def render_protocol(
    component_name: str,
    contract: ComponentContract,
    symbols: dict[str, Symbol],
    test_plan: TestPlanFile,
    template: jinja2.Template,
) -> str:
    """Render a single Protocol .pyi from YAML sources."""
    protocol_path = contract.protocol
    return template.render(
        component_name=component_name,
        target_implementation=contract.file,
        protocol_class_name=_protocol_class_name(
            component_name, protocol_path
        ),
        responsibilities=contract.responsibilities,
        imports=_build_imports(contract.methods, symbols),
        methods=_prepare_methods(contract.methods, test_plan, protocol_path),
    )


def _resolve_template_path(explicit: str | None) -> Path:
    """Resolve the template path; default to the harness/templates sibling."""
    if explicit:
        return Path(explicit)
    script_dir = Path(__file__).resolve().parent
    return script_dir.parent / "templates" / "interface.pyi.template"


def _reject_traversal(label: str, value: str) -> str | None:
    """Return an error message if ``value`` contains a ``..`` segment.

    Author-controlled inputs (``contract.protocol``, ``--out-dir``,
    ``--template``) flow into filesystem reads/writes; ``..`` lets a
    crafted path escape the zone that ``interfaces-codegen-only.sh``
    authorizes. Reject at the boundary so codegen only reads/writes
    where the YAML and CLI explicitly name.
    """
    normalized = str(value).replace("\\", "/")
    if ".." in normalized.split("/"):
        return (
            f"FAIL: {label} contains '..' segment (path traversal): "
            f"{value!r}"
        )
    return None


def _validate_template_path(
    explicit: str | None, default_path: Path
) -> str | None:
    """Restrict --template to the harness/templates/ directory.

    Any ``--template`` override must point at an existing file inside
    the same directory as the default template (the harness-authored
    template set). Reject traversal, absolute paths that escape the
    directory, and files outside the directory.

    Returns an error message, or ``None`` if validation passes (or no
    override was given).
    """
    if explicit is None:
        return None
    if msg := _reject_traversal("--template", explicit):
        return msg
    try:
        supplied = Path(explicit).resolve(strict=False)
        templates_dir = default_path.parent.resolve(strict=False)
    except (OSError, ValueError) as exc:
        return f"FAIL: --template path resolution failed: {exc}"
    if templates_dir not in supplied.parents:
        return (
            f"FAIL: --template must live under {templates_dir} (the "
            "harness templates directory); got "
            f"{explicit!r} resolving to {supplied}"
        )
    if not supplied.is_file():
        return f"FAIL: --template path does not exist: {supplied}"
    return None


def _verify_out_dir_containment(
    out_dir_arg: str, project_root: Path
) -> tuple[Path | None, str | None]:
    """Resolve ``out_dir_arg`` and verify it stays within ``project_root``.

    Mirrors the containment check the template whitelist uses: the
    resolved path must equal ``project_root`` or be a descendant of it.
    Catches symlink escapes and absolute paths that the string-only
    ``_reject_traversal`` accepts. ``project_root`` is cwd by default
    (production: the repo root where ``/io-gen-protocols`` runs); the
    ``--root`` CLI flag overrides for testing scenarios where cwd is
    different from the authoring tree.
    """
    try:
        resolved = Path(out_dir_arg).resolve(strict=False)
        root_resolved = project_root.resolve(strict=False)
    except (OSError, ValueError) as exc:
        return None, f"FAIL: --out-dir path resolution failed: {exc}"
    if resolved != root_resolved and root_resolved not in resolved.parents:
        return None, (
            f"FAIL: --out-dir must stay within {root_resolved}; got "
            f"{out_dir_arg!r} resolving to {resolved}"
        )
    return resolved, None


def _render_all(
    contracts,
    symbols,
    test_plan,
    template,
    out_dir: Path,
) -> int:
    """Render every Protocol-bearing component and return emitted count."""
    emitted = 0
    for component_name, contract in sorted(contracts.components.items()):
        if not contract.protocol:
            continue
        stem = Path(contract.protocol).stem
        output = render_protocol(
            component_name, contract, symbols, test_plan, template
        )
        out_path = out_dir / f"{stem}.pyi"
        out_path.write_text(output, encoding="utf-8")
        emitted += 1
    return emitted


def _prune_orphans(
    contracts, out_dir: Path, prune: bool
) -> list[Path]:
    """Return orphan .pyi paths; delete them if ``prune`` is True.

    An orphan is a file under ``out_dir`` whose stem does not correspond
    to any ``ComponentContract.protocol`` in the loaded contracts. Narrowing
    a contract (removing a protocol-bearing component, or renaming the
    protocol stem) used to leave stale .pyi that failed the Step 0 validator
    on subsequent runs. The warn-by-default / ``--prune`` path gives the
    user explicit control without a silent delete.
    """
    if not out_dir.exists():
        return []
    expected_stems = {
        Path(c.protocol).stem
        for c in contracts.components.values()
        if c.protocol
    }
    orphans = [
        pyi
        for pyi in out_dir.glob("*.pyi")
        if pyi.stem not in expected_stems
    ]
    if prune:
        for path in orphans:
            path.unlink()
    return orphans


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    One-shot YAML load: ``plans/component-contracts.yaml``,
    ``plans/symbols.yaml``, and ``plans/test-plan.yaml`` are each parsed
    exactly once and the resulting objects are threaded through the
    validator and the renderer. Eliminates the round-2 TOCTOU where
    mid-invocation YAML edits produced a validator-verdict-vs-renderer
    divergence.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Emit interfaces/<stem>.pyi files from component-contracts.yaml, "
            "symbols.yaml, and test-plan.yaml via jinja2 codegen."
        )
    )
    parser.add_argument(
        "--contracts", default="plans/component-contracts.yaml"
    )
    parser.add_argument("--symbols", default="plans/symbols.yaml")
    parser.add_argument("--test-plan", default="plans/test-plan.yaml")
    parser.add_argument("--out-dir", default="interfaces")
    parser.add_argument(
        "--template",
        default=None,
        help=(
            "Path to jinja2 template; defaults to "
            "harness/templates/interface.pyi.template sibling of this script."
        ),
    )
    parser.add_argument(
        "--prune",
        action="store_true",
        help=(
            "Delete orphan .pyi files in --out-dir (any whose stem is "
            "not referenced by ComponentContract.protocol). Default "
            "behavior is to warn to stderr without deleting."
        ),
    )
    parser.add_argument(
        "--root",
        default=None,
        help=(
            "Project-root containment boundary for --out-dir. Defaults "
            "to the current working directory. The resolved --out-dir "
            "must equal or be a descendant of --root."
        ),
    )
    args = parser.parse_args(argv)

    default_template = _resolve_template_path(None)
    if msg := _validate_template_path(args.template, default_template):
        sys.stderr.write(msg + "\n")
        return 1
    template_path = _resolve_template_path(args.template)
    if not template_path.exists():
        sys.stderr.write(f"FAIL: template not found: {template_path}\n")
        return 1

    contracts_path = Path(args.contracts)
    if not contracts_path.exists():
        sys.stderr.write(
            f"FAIL: contracts file not found: {contracts_path}\n"
        )
        return 1

    symbols_path = Path(args.symbols)
    if not symbols_path.exists():
        sys.stderr.write(f"FAIL: symbols file not found: {symbols_path}\n")
        return 1

    # String-level traversal guard on --out-dir (catches literal ``..`).
    if msg := _reject_traversal("--out-dir", args.out_dir):
        sys.stderr.write(msg + "\n")
        return 1

    # Resolved-path containment: --out-dir must stay within the project
    # root (cwd, or --root override). Closes the symlink / absolute-path
    # escape the string-only guard allows.
    project_root = Path(args.root) if args.root else Path.cwd()
    out_dir_resolved, err = _verify_out_dir_containment(
        args.out_dir, project_root
    )
    if err is not None:
        sys.stderr.write(err + "\n")
        return 1
    assert out_dir_resolved is not None  # err is None implies resolved set
    out_dir = out_dir_resolved

    # One-shot YAML loads. Every downstream reader operates on these
    # objects -- no re-reads, no TOCTOU window between validator and
    # renderer even if the underlying files mutate during execution.
    contracts = load_contracts(str(contracts_path))

    # Traversal guard on author-controlled component.protocol values.
    for comp_name, comp in contracts.components.items():
        if comp.protocol and (
            msg := _reject_traversal(
                f"components.{comp_name}.protocol", comp.protocol
            )
        ):
            sys.stderr.write(msg + "\n")
            return 1

    symbols_file = load_symbols(str(symbols_path))
    symbols = symbols_file.symbols

    test_plan_path = Path(args.test_plan)
    test_plan = (
        load_test_plan(str(test_plan_path))
        if test_plan_path.exists()
        else TestPlanFile()
    )

    # Orphan housekeeping BEFORE validation. Stale .pyi files from a
    # prior run (whose corresponding ComponentContract has since been
    # removed or renamed) would otherwise block Step-0 validation --
    # the validator walks BOTH contracts AND on-disk interfaces/*.pyi.
    # Under --prune, drop orphans so the validator sees the post-render
    # view. Without --prune, emit a pre-validation warning so the user
    # understands why validator errors may reference names no longer in
    # their YAML.
    out_dir.mkdir(parents=True, exist_ok=True)
    orphans = _prune_orphans(contracts, out_dir, args.prune)
    if orphans and not args.prune:
        sys.stderr.write(
            f"WARN: {len(orphans)} orphan .pyi file(s) in {out_dir} (no "
            "corresponding ComponentContract.protocol). Re-run with "
            "--prune to delete, or remove manually to clear stale "
            "validator rejections:\n"
        )
        for path in orphans:
            sys.stderr.write(f"  orphan: {path}\n")

    # Step 0 hard gate -- same objects the renderer will use.
    from validate_symbols_coverage import validate_from_objects
    validation_rc = validate_from_objects(
        symbols_file,
        contracts,
        out_dir,
        contracts_label=str(contracts_path),
    )
    if validation_rc != 0:
        sys.stderr.write(
            "FAIL: validate_symbols_coverage rejected the inputs; codegen "
            "refused. Resolve the errors above in the YAML, then re-run.\n"
        )
        return 1

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(template_path.parent)),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
        autoescape=False,
    )
    template = env.get_template(template_path.name)

    emitted = _render_all(contracts, symbols, test_plan, template, out_dir)

    summary = f"PASS: emitted {emitted} Protocol .pyi file(s) to {out_dir}"
    if args.prune and orphans:
        summary += f"; pruned {len(orphans)} orphan(s)"
    sys.stdout.write(summary + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

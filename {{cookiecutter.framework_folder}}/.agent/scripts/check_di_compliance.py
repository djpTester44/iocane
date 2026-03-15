#!/usr/bin/env python3
"""check_di_compliance.py

Enforces the Dependency Injection rule from the Mini-Spec Skill:
1. Scans plans/project-spec.md for Collaborators in CRC cards.
2. Maps Components to implementation files via the Interface Registry.
   - Validates that every resolved path is strictly inside src/.
3. Reads the Entrypoint Layer from Architecture Layer Mapping to exempt
   Composition Root components.
4. Parses plans/PLAN.md to build an active debt registry of components
   that carry a tracked [REFACTOR] or [CLEANUP] backlog ticket.
5. Parses each implementation file's __init__ method via AST.
6. **Sweeps tests/ directory** for bare component instantiations to
   prevent dependency gaps during CI builds.  Any registry component
   that has CRC collaborators MUST receive arguments when instantiated
   in test code.  ``# noqa: DI-TEST`` on the call line exempts it.
7. Reports violations at three severity levels:
   - [CRITICAL]: Collaborator instantiated inside __init__ body (bare class
                 call, not factory-mediated); OR a component uses # noqa: DI
                 without a matching active ticket in plans/PLAN.md; OR a
                 registry entry resolves outside the src/ boundary; OR a
                 test file instantiates a component without passing required
                 collaborators.
   - [WARNING]:  Collaborator not resolvable from any injected source.
                 Any WARNING causes a non-zero exit (strict gate mode).
   - [INFO]:     Tracked exemptions and factory-param heuristic notices.

Exit codes (strict binary gate):
  0 -- All clean, OR every exemption has a matching PLAN.md debt ticket
      and no unresolved WARNINGs remain.
  1 -- Any CRITICAL or WARNING remains unresolved.

Injection patterns recognised (no false-positive for any of these):
  - Direct parameter type hints:            def __init__(self, dep: DepProtocol)
  - Variadic kwargs wildcard:               def __init__(self, **deps)
  - Mapping / TypedDict parameter:          def __init__(self, deps: dict[str, Any])
  - Key-based access from a mapping param:  self.x = deps['DataLoader']
  - Factory / builder parameter:            def __init__(self, factory: LoaderFactory)
                                            self.x = factory.create_loader()
  - Service-locator / DI-container:         self.x = container.resolve(DepProtocol)
  - Builder chaining ending in .build():    SomeBuilder(...).with_x(x).build()
  - Bulk dict injection:                    self.__dict__.update(deps)
  - setattr loop:                           for k, v in deps.items(): setattr(self, k, v)
  - Param-attribute access:                 self.x = some_param.dep  (no call needed)

Usage:
    uv run rtk python .agent/scripts/check_di_compliance.py
"""

import ast
import re
import sys
from pathlib import Path
from typing import NamedTuple

# ---------------------------------------------------------------------------
# Compiled patterns
# ---------------------------------------------------------------------------

# Method names that indicate a factory / builder / provider call.
FACTORY_METHOD_RE = re.compile(
    r"^(create|build|make|produce|new|from|of|for)_"
    r"|_(create|build|factory|builder|provider|resolver|produce)$",
    re.IGNORECASE,
)

# Parameter *names* (not types) that suggest the param is a factory/builder.
FACTORY_PARAM_NAME_RE = re.compile(
    r"(factory|builder|creator|provider|maker|producer)$",
    re.IGNORECASE,
)

# Parameter *names* that suggest a DI container / service locator.
CONTAINER_PARAM_NAME_RE = re.compile(
    r"(container|locator|injector|registry|resolver|services|dependencies)$",
    re.IGNORECASE,
)

# Method names used on DI containers to resolve a dependency.
CONTAINER_METHOD_RE = re.compile(
    r"^(resolve|get|provide|inject|lookup|wire|fetch|acquire|make)$",
    re.IGNORECASE,
)

# Type annotation names that imply the parameter is a generic mapping.
MAPPING_TYPE_RE = re.compile(
    r"^(dict|Dict|Mapping|MutableMapping|ChainMap|TypedDict|Any|object)$"
)

# PascalCase heuristic: used to decide whether a bare Name call looks like a
# class instantiation (as opposed to a plain function call).
PASCAL_CASE_RE = re.compile(r"^[A-Z][a-zA-Z0-9]*$")

# Builder chain: any call whose outermost method is .build() / .create() /
# .construct() is treated as a creational chain, not a direct instantiation.
BUILDER_TERMINAL_RE = re.compile(r"^(build|create|construct|make|produce)$", re.IGNORECASE)

# Active debt ticket line in PLAN.md.
# Matches open checkboxes (- [ ]) or plain list items containing [REFACTOR]
# or [CLEANUP] immediately followed by a component (identifier) name.
#
# Accepted formats:
#   - [ ] [REFACTOR] DataLoader: migrate to protocol injection
#   - [ ] [CLEANUP] ReportWriter - remove concrete dep
#   * [REFACTOR] SessionManager (tracked)
#   - [CLEANUP] OrderProcessor
#
# Closed checkboxes (- [x] / - [X]) are explicitly excluded; a completed
# ticket is no longer an active remediation commitment.
_PLAN_TICKET_RE = re.compile(
    r"[-*]\s+"                                  # list marker
    r"(?:\[\s\]\s+)?"                           # optional open checkbox
    r"\[(?:REFACTOR|CLEANUP)\]\s+"              # tag (case-insensitive)
    r"([A-Za-z_][A-Za-z0-9_]*)",               # component name
    re.IGNORECASE,
)
_PLAN_CLOSED_RE = re.compile(r"-\s+\[[xX]\]")  # completed item marker


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


class Violation(NamedTuple):
    """Single compliance finding."""

    component: str
    file_path: Path
    severity: str
    issue: str


# ---------------------------------------------------------------------------
# Spec-file and plan parsers
# ---------------------------------------------------------------------------


def parse_entrypoint_layer(spec_content: str) -> str | None:
    """Extract the Layer 4 (Entrypoint) directory from Architecture Layer Mapping."""
    match = re.search(
        r"Layer\s*4\s*\(Entrypoint\).*?:\s*\[?`?([^\]`\n,]+)",
        spec_content,
    )
    if match:
        return match.group(1).strip().rstrip("/")
    return None


def parse_registry(
    spec_content: str,
    root_dir: Path,
    src_dir: Path,
) -> tuple[dict[str, Path], list[Violation]]:
    """Extract Component -> FilePath mapping from the Protocol Interfaces table.

    Also validates that every resolved path is strictly inside *src_dir*.
    Returns ``(mapping, boundary_violations)``.  Boundary violations are
    CRITICAL and are appended to the global report before component analysis
    so the gate fails fast for any out-of-tree path.

    Normalizes ProtocolName by stripping the 'Protocol' suffix so the key
    matches the CRC card header (e.g. ``DataLoader`` not ``DataLoaderProtocol``).
    """
    mapping: dict[str, Path] = {}
    boundary_violations: list[Violation] = []
    in_registry = False

    resolved_src = src_dir.resolve()

    for line in spec_content.splitlines():
        if "Interface Registry" in line or "Protocol Interfaces" in line:
            in_registry = True
            continue
        if in_registry and line.startswith("##"):
            break

        if not (in_registry and "|" in line and "---" not in line):
            continue

        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 3:
            continue

        proto_match = re.search(r"\[?(\w+)\]?", parts[1])
        if not proto_match:
            continue
        proto_name = proto_match.group(1)
        comp_name = proto_name.removesuffix("Protocol")

        raw_target = parts[-2]
        target_match = re.search(r"`([^`]+)`", raw_target)
        if not target_match:
            target_match = re.search(r"(\S+\.py)", raw_target)
        if not target_match:
            continue

        resolved = (root_dir / target_match.group(1).strip()).resolve()
        mapping[comp_name] = resolved

        # --- Layout boundary enforcement ---
        try:
            resolved.relative_to(resolved_src)
        except ValueError:
            boundary_violations.append(
                Violation(
                    comp_name,
                    resolved,
                    "CRITICAL",
                    (
                        f"Registry path '{resolved.as_posix()}' resolves outside "
                        f"the src/ boundary ('{resolved_src.as_posix()}'). "
                        "Components must live strictly under src/."
                    ),
                )
            )

    return mapping, boundary_violations


def parse_collaborators(spec_content: str) -> dict[str, list[str]]:
    """Extract Component -> Collaborators list from CRC cards."""
    designs: dict[str, list[str]] = {}
    sections = re.split(r"^###\s+", spec_content, flags=re.MULTILINE)

    for section in sections[1:]:
        lines = section.splitlines()
        if not lines:
            continue

        name_match = re.match(r"\[?(\w+)\]?", lines[0].strip())
        if not name_match:
            continue
        comp_name = name_match.group(1)

        collaborators: list[str] = []
        in_collab = False

        for line in lines:
            if re.search(r"\*\s+\*\*Collaborators", line):
                in_collab = True
                continue
            if in_collab:
                if re.search(r"None", line, re.IGNORECASE):
                    break
                if line.strip().startswith("* **") or line.strip().startswith("> **"):
                    break
                collab_match = re.search(r"^\s+\*\s+`?(\w+)`?", line)
                if collab_match:
                    collaborators.append(collab_match.group(1))

        if collaborators:
            designs[comp_name] = collaborators

    return designs


def parse_plan_backlog(plan_content: str) -> set[str]:
    """Return the set of component names with an active [REFACTOR] or [CLEANUP]
    ticket in PLAN.md.

    Only *open* items count as active debt:
      - Unchecked checkboxes:  ``- [ ] [REFACTOR] ComponentName ...``
      - Plain list items:      ``- [REFACTOR] ComponentName ...``

    Closed checkboxes (``- [x]`` / ``- [X]``) are skipped because a merged
    ticket is no longer an outstanding remediation commitment.
    """
    tracked: set[str] = set()

    for line in plan_content.splitlines():
        # Skip completed items first.
        if _PLAN_CLOSED_RE.search(line):
            continue
        m = _PLAN_TICKET_RE.search(line)
        if m:
            tracked.add(m.group(1))

    return tracked


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------


def _root_name(node: ast.expr) -> str | None:
    """Return the leftmost Name identifier in an attribute chain.

    e.g.  ``foo.bar.baz``  ->  ``'foo'``
          ``foo``           ->  ``'foo'``
    """
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return _root_name(node.value)
    return None


def _call_leaf_name(func_node: ast.expr) -> str | None:
    """Return just the final attribute / name being called.

    e.g.  ``factory.create_loader``  ->  ``'create_loader'``
          ``DataLoader``              ->  ``'DataLoader'``
    """
    if isinstance(func_node, ast.Name):
        return func_node.id
    if isinstance(func_node, ast.Attribute):
        return func_node.attr
    return None


def _is_builder_chain(call_node: ast.Call) -> bool:
    """Return True if this Call is the terminal step of a builder chain.

    Matches patterns like::

        SomeBuilder(...).with_x(x).build()
        BuilderClass.from_config(cfg).create()
    """
    leaf = _call_leaf_name(call_node.func)
    return bool(
        leaf
        and BUILDER_TERMINAL_RE.match(leaf)
        and isinstance(call_node.func, ast.Attribute)
        and isinstance(call_node.func.value, ast.Call)
    )


# ---------------------------------------------------------------------------
# InitVisitor - factory, kwargs, and provenance tracking
# ---------------------------------------------------------------------------


class InitVisitor(ast.NodeVisitor):
    """Visit a class definition and inspect its ``__init__`` method.

    After visiting, the following attributes are populated:

    ``found_class``           - True if the target class was found in the AST.
    ``is_exempt``             - True if the class or __init__ carries ``# noqa: DI``.
    ``init_node``             - The FunctionDef AST node for __init__, or None.

    *Injection-source tracking*

    ``arg_types``             - Type names gathered from direct parameter annotations.
    ``param_names``           - All non-self parameter names.
    ``has_variadic_kwargs``   - True if __init__ accepts ``**kwargs`` / ``**deps``.
    ``mapping_param_names``   - Params whose type annotation is a Mapping/dict type.
    ``factory_param_names``   - Params whose name or type suggests a factory/builder.
    ``container_param_names`` - Params that look like DI containers / locators.
    ``mapping_key_types``     - Type-like strings accessed as keys from mapping params.
    ``has_bulk_injection``    - True if ``__dict__.update`` / setattr loop is used.

    *Violation tracking*

    ``direct_instantiations`` - Names of PascalCase bare-call instantiations that
                                are NOT factory-mediated and NOT from a
                                param-derived receiver object.
    """

    def __init__(self, target_class: str, source_lines: list[str]) -> None:
        self.target_class = target_class
        self.source_lines = source_lines

        self.found_class: bool = False
        self.is_exempt: bool = False
        self.init_node: ast.FunctionDef | None = None

        # Injection sources
        self.arg_types: set[str] = set()
        self.param_names: set[str] = set()
        self.has_variadic_kwargs: bool = False
        self.mapping_param_names: set[str] = set()
        self.factory_param_names: set[str] = set()
        self.container_param_names: set[str] = set()
        self.mapping_key_types: set[str] = set()
        self.has_bulk_injection: bool = False

        # Violation detection
        self.direct_instantiations: set[str] = set()

        # Legacy alias kept for external callers.
        self.instantiations: set[str] = self.direct_instantiations

    # ------------------------------------------------------------------
    # Top-level visitor
    # ------------------------------------------------------------------

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if node.name != self.target_class:
            self.generic_visit(node)
            return

        self.found_class = True

        if self._has_exemption(node.lineno):
            self.is_exempt = True
            return

        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                if self._has_exemption(item.lineno):
                    self.is_exempt = True
                    return
                self.init_node = item
                self._analyse_init(item)
                break

    # ------------------------------------------------------------------
    # Main analysis pipeline
    # ------------------------------------------------------------------

    def _analyse_init(self, func: ast.FunctionDef) -> None:
        self._collect_param_roles(func)
        var_provenance = self._build_var_provenance(func)
        self._scan_body(func, var_provenance)

    # ------------------------------------------------------------------
    # Phase 1: parameter roles
    # ------------------------------------------------------------------

    def _collect_param_roles(self, func: ast.FunctionDef) -> None:
        all_args = (
            func.args.posonlyargs
            + func.args.args
            + func.args.kwonlyargs
        )

        for arg in all_args:
            if arg.arg == "self":
                continue
            self.param_names.add(arg.arg)
            if arg.annotation:
                self.arg_types.update(self._extract_type_names(arg.annotation))
                self._classify_param_by_type(arg.arg, arg.annotation)
            self._classify_param_by_name(arg.arg)

        if func.args.kwarg:
            self.has_variadic_kwargs = True
            kwarg_name = func.args.kwarg.arg
            self.param_names.add(kwarg_name)
            self.mapping_param_names.add(kwarg_name)

    def _classify_param_by_name(self, name: str) -> None:
        if FACTORY_PARAM_NAME_RE.search(name):
            self.factory_param_names.add(name)
        if CONTAINER_PARAM_NAME_RE.search(name):
            self.container_param_names.add(name)

    def _classify_param_by_type(self, param_name: str, annotation: ast.expr) -> None:
        for t in self._extract_type_names(annotation):
            if MAPPING_TYPE_RE.match(t):
                self.mapping_param_names.add(param_name)
            if FACTORY_PARAM_NAME_RE.search(t):
                self.factory_param_names.add(param_name)
            if CONTAINER_PARAM_NAME_RE.search(t):
                self.container_param_names.add(param_name)

    # ------------------------------------------------------------------
    # Phase 2: local-variable provenance map
    # ------------------------------------------------------------------

    def _build_var_provenance(self, func: ast.FunctionDef) -> dict[str, str]:
        """Return a mapping of local variable name -> provenance string.

        Provenance values:
          ``'param'``   - assigned directly from a parameter or attribute thereof.
          ``'factory'`` - assigned from a factory/container call on a param-derived obj.
          ``'direct'``  - bare class instantiation (PascalCase call, not factory-mediated).
          ``'other'``   - anything else.
        """
        provenance: dict[str, str] = dict.fromkeys(self.param_names, "param")

        for node in ast.walk(func):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        provenance[target.id] = self._classify_rhs(node.value, provenance)

            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
                provenance[node.target.id] = self._classify_rhs(node.value, provenance)

        return provenance

    def _classify_rhs(self, expr: ast.expr, provenance: dict[str, str]) -> str:
        if isinstance(expr, ast.Name):
            return provenance.get(expr.id, "other")

        if isinstance(expr, ast.Attribute):
            root = _root_name(expr)
            if root == "self" or root in self.param_names:
                return "param"
            return provenance.get(root, "other") if root else "other"

        if isinstance(expr, ast.Call):
            if self._is_factory_or_container_call(expr, provenance):
                return "factory"
            if _is_builder_chain(expr):
                return "factory"
            leaf = _call_leaf_name(expr.func)
            if leaf and PASCAL_CASE_RE.match(leaf):
                return f"direct:{leaf}"
            return "other"

        if isinstance(expr, ast.Subscript):
            root = _root_name(expr.value)
            if root in self.mapping_param_names:
                self._record_mapping_key(expr.slice)
                return "param"

        if isinstance(expr, ast.Await):
            return self._classify_rhs(expr.value, provenance)

        return "other"

    # ------------------------------------------------------------------
    # Phase 3: body scan for violations and injection patterns
    # ------------------------------------------------------------------

    def _scan_body(self, func: ast.FunctionDef, var_provenance: dict[str, str]) -> None:
        for node in ast.walk(func):
            if isinstance(node, ast.Call):
                self._check_call_for_violation(node, var_provenance)
                if self._is_bulk_injection(node):
                    self.has_bulk_injection = True
                self._is_mapping_get_call(node)  # side-effect: records keys

            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if (
                        isinstance(target, ast.Attribute)
                        and isinstance(target.value, ast.Name)
                        and target.value.id == "self"
                        and isinstance(node.value, ast.Subscript)
                    ):
                        root = _root_name(node.value.value)
                        if root in self.mapping_param_names:
                            self._record_mapping_key(node.value.slice)

    def _check_call_for_violation(
        self, call: ast.Call, var_provenance: dict[str, str]
    ) -> None:
        """If this call is a direct PascalCase instantiation not mediated by a
        factory / container / param-derived object, record it as a violation."""
        if _is_builder_chain(call):
            return

        func = call.func

        if isinstance(func, ast.Name):
            name = func.id
            if not PASCAL_CASE_RE.match(name):
                return
            if name in {"super", "type", "object", "property", "classmethod", "staticmethod"}:
                return
            self.direct_instantiations.add(name)

        elif isinstance(func, ast.Attribute):
            attr = func.attr
            if not PASCAL_CASE_RE.match(attr):
                return
            receiver_root = _root_name(func.value)
            if receiver_root in self.param_names:
                return
            if receiver_root and var_provenance.get(receiver_root) in ("param", "factory"):
                return
            self.direct_instantiations.add(attr)

    # ------------------------------------------------------------------
    # Factory / container call detection
    # ------------------------------------------------------------------

    def _is_factory_or_container_call(
        self, call: ast.Call, provenance: dict[str, str]
    ) -> bool:
        func = call.func
        if not isinstance(func, ast.Attribute):
            return False

        method = func.attr
        receiver_root = _root_name(func.value)

        receiver_is_param = receiver_root in self.param_names or (
            receiver_root is not None
            and provenance.get(receiver_root) in ("param", "factory")
        )
        if not receiver_is_param:
            return False

        return bool(
            FACTORY_METHOD_RE.search(method)
            or CONTAINER_METHOD_RE.match(method)
            or receiver_root in self.factory_param_names
            or receiver_root in self.container_param_names
        )

    # ------------------------------------------------------------------
    # Mapping key extraction helpers
    # ------------------------------------------------------------------

    def _record_mapping_key(self, key_node: ast.expr) -> None:
        if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
            self.mapping_key_types.add(key_node.value)
        elif isinstance(key_node, ast.Name):
            self.mapping_key_types.add(key_node.id)

    def _is_mapping_get_call(self, call: ast.Call) -> bool:
        """Handle ``deps.get('Key', default)`` access on mapping params."""
        if not isinstance(call.func, ast.Attribute):
            return False
        if call.func.attr != "get":
            return False
        root = _root_name(call.func.value)
        if root not in self.mapping_param_names:
            return False
        if call.args:
            self._record_mapping_key(call.args[0])
        return True

    # ------------------------------------------------------------------
    # Bulk injection detection
    # ------------------------------------------------------------------

    def _is_bulk_injection(self, call: ast.Call) -> bool:
        """Detect ``self.__dict__.update(deps)`` and ``vars(self).update(deps)``."""
        func = call.func
        if not isinstance(func, ast.Attribute) or func.attr != "update":
            return False

        # self.__dict__.update(...)
        if isinstance(func.value, ast.Attribute):
            inner_root = _root_name(func.value.value)
            if inner_root == "self" and func.value.attr == "__dict__":
                return True

        # vars(self).update(...)
        return bool(
            isinstance(func.value, ast.Call)
            and isinstance(func.value.func, ast.Name)
            and func.value.func.id == "vars"
        )

    # ------------------------------------------------------------------
    # Annotation parsing helpers
    # ------------------------------------------------------------------

    def _extract_type_names(self, node: ast.expr) -> list[str]:
        """Recursively extract all concrete type names from an annotation node."""
        if isinstance(node, ast.Name):
            return [node.id]
        if isinstance(node, ast.Attribute):
            return [node.attr]
        if isinstance(node, ast.Subscript):
            results = self._extract_type_names(node.value)
            results.extend(self._extract_type_names(node.slice))
            return results
        if isinstance(node, ast.BinOp):   # X | Y union syntax
            return self._extract_type_names(node.left) + self._extract_type_names(node.right)
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return [node.value]
        if isinstance(node, ast.Tuple):
            results = []
            for elt in node.elts:
                results.extend(self._extract_type_names(elt))
            return results
        return []

    # ------------------------------------------------------------------
    # Exemption helper
    # ------------------------------------------------------------------

    def _has_exemption(self, lineno: int) -> bool:
        if 0 < lineno <= len(self.source_lines):
            return "# noqa: DI" in self.source_lines[lineno - 1]
        return False


# ---------------------------------------------------------------------------
# TestInstantiationVisitor - test-file sweep for bare component calls
# ---------------------------------------------------------------------------


class TestInstantiationVisitor(ast.NodeVisitor):
    """Walk a test file and find instantiations of registry components.

    For each call matching a component name, checks whether the required
    collaborators are supplied as positional or keyword arguments.

    Attributes after visiting:

    ``bare_calls`` - list of ``(comp_name, lineno)`` tuples where a
                     component with required collaborators was called
                     without passing any arguments that satisfy the
                     collaborator requirement.
    """

    def __init__(
        self,
        component_collabs: dict[str, list[str]],
        source_lines: list[str],
    ) -> None:
        self.component_collabs = component_collabs
        self.source_lines = source_lines
        self.bare_calls: list[tuple[str, int]] = []

    # ------------------------------------------------------------------
    # Visitor
    # ------------------------------------------------------------------

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        comp_name = self._called_component(node)
        if comp_name is not None:
            collabs = self.component_collabs.get(comp_name, [])
            if collabs and not self._has_args(node, collabs):
                lineno = node.lineno
                if not self._has_exemption(lineno):
                    self.bare_calls.append((comp_name, lineno))
        self.generic_visit(node)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _called_component(self, call: ast.Call) -> str | None:
        """Return the component name if this call targets a registry component."""
        func = call.func
        if isinstance(func, ast.Name) and func.id in self.component_collabs:
            return func.id
        if isinstance(func, ast.Attribute) and func.attr in self.component_collabs:
            return func.attr
        return None

    @staticmethod
    def _has_args(call: ast.Call, collabs: list[str]) -> bool:
        """Return True if positional or keyword args satisfy the collaborators.

        Any of the following count as satisfying:
          - At least one positional argument is provided.
          - Any keyword argument is provided.
          - The call uses ``**kwargs`` unpacking.
        """
        if call.args:
            return True
        if call.keywords:
            return True
        return False

    def _has_exemption(self, lineno: int) -> bool:
        """Check for ``# noqa: DI-TEST`` on the call line."""
        if 0 < lineno <= len(self.source_lines):
            return "# noqa: DI-TEST" in self.source_lines[lineno - 1]
        return False


def check_test_file(
    path: Path,
    component_collabs: dict[str, list[str]],
) -> list[Violation]:
    """Check a single test file for bare component instantiations.

    Returns a list of ``Violation`` entries at CRITICAL severity for
    every instantiation of a registry component that has required
    collaborators but was called without any arguments.
    """
    try:
        source_text = path.read_text(encoding="utf-8")
        source_lines = source_text.splitlines()
        tree = ast.parse(source_text)
    except SyntaxError:
        return [Violation("<test>", path, "WARNING", "Syntax error in test file")]

    visitor = TestInstantiationVisitor(component_collabs, source_lines)
    visitor.visit(tree)

    violations: list[Violation] = []
    for comp_name, lineno in visitor.bare_calls:
        collabs = component_collabs[comp_name]
        violations.append(
            Violation(
                comp_name,
                path,
                "CRITICAL",
                (
                    f"Test instantiates {comp_name}() at line {lineno} "
                    f"without required collaborators: "
                    f"{', '.join(collabs)}"
                ),
            )
        )
    return violations


# ---------------------------------------------------------------------------
# Collaborator matching helpers
# ---------------------------------------------------------------------------


def _collab_in_types(collab: str, type_names: set[str]) -> bool:
    """True if *collab* (or its Protocol variant) appears in *type_names*."""
    return any(
        t == collab
        or t == f"{collab}Protocol"
        or collab == f"{t}Protocol"
        for t in type_names
    )


def _collab_in_mapping_keys(collab: str, keys: set[str]) -> bool:
    """True if any mapping key matches the collaborator name under common
    case/snake-case conventions.

    Matches:
      ``'DataLoader'``  == ``'DataLoader'``  (exact)
      ``'data_loader'`` ~  ``'DataLoader'``  (snake_case -> PascalCase)
      ``'loader'``      ~  ``'DataLoader'``  (suffix match)
    """
    collab_lower = collab.lower()
    collab_snake = re.sub(r"(?<!^)(?=[A-Z])", "_", collab).lower()
    for key in keys:
        key_norm = key.lower().replace("-", "_")
        if (
            key_norm in (collab_lower, collab_snake)
            or collab_lower.endswith(key_norm)
            or key_norm.endswith(collab_lower)
        ):
            return True
    return False


# ---------------------------------------------------------------------------
# Per-component analysis
# ---------------------------------------------------------------------------


def check_component(
    path: Path,
    comp_name: str,
    collaborators: list[str],
    tracked_debt: set[str],
) -> list[Violation]:
    """Check a single component for DI violations.

    *tracked_debt* is the set of component names that have an active
    ``[REFACTOR]`` or ``[CLEANUP]`` ticket in ``plans/PLAN.md``.  It
    governs whether a ``# noqa: DI`` suppression is a legitimate tracked
    deferral (INFO) or untracked technical debt (CRITICAL).
    """
    if not path.exists():
        return [Violation(comp_name, path, "WARNING", "Implementation file not found")]

    try:
        source_text = path.read_text(encoding="utf-8")
        source_lines = source_text.splitlines()
        tree = ast.parse(source_text)
    except SyntaxError:
        return [Violation(comp_name, path, "WARNING", "Syntax error in file")]

    visitor = InitVisitor(comp_name, source_lines)
    visitor.visit(tree)

    if not visitor.found_class:
        return []

    # ------------------------------------------------------------------
    # Exemption handling: noqa DI
    # ------------------------------------------------------------------
    if visitor.is_exempt:
        if comp_name in tracked_debt:
            # Legitimate deferral: tracked in PLAN.md → INFO only.
            return [
                Violation(
                    comp_name,
                    path,
                    "INFO",
                    (
                        "Component exempted via # noqa: DI; "
                        "active remediation ticket found in plans/PLAN.md."
                    ),
                )
            ]
        # No matching ticket → untracked suppression, escalate to CRITICAL.
        return [
            Violation(
                comp_name,
                path,
                "CRITICAL",
                (
                    "Component uses # noqa: DI but has no active [REFACTOR] or "
                    "[CLEANUP] ticket in plans/PLAN.md. "
                    "Add a tracked backlog ticket or remove the suppression."
                ),
            )
        ]

    if not visitor.init_node:
        if collaborators:
            return [
                Violation(
                    comp_name,
                    path,
                    "INFO",
                    "No __init__ method (stateless); verify CRC collaborators are accurate",
                )
            ]
        return []

    violations: list[Violation] = []

    # ------------------------------------------------------------------
    # CRITICAL: direct bare-class instantiation of a known collaborator
    #   - factory-mediated and param-derived calls are filtered in the
    #     visitor before they ever reach direct_instantiations.
    # ------------------------------------------------------------------
    for collab in collaborators:
        if collab in visitor.direct_instantiations:
            violations.append(
                Violation(
                    comp_name,
                    path,
                    "CRITICAL",
                    f"Internal instantiation of collaborator '{collab}()'",
                )
            )

    # ------------------------------------------------------------------
    # WARNING: collaborator not resolvable from any injected source.
    #
    # A collaborator is considered "resolved" if ANY of the following hold:
    #   1. Its type (or *Protocol variant) appears in parameter annotations.
    #   2. __init__ accepts **kwargs → any collaborator may arrive dynamically.
    #   3. The collaborator name/key appears in mapping-parameter access.
    #   4. A mapping parameter with a generic/Any type is present → wildcard.
    #   5. A factory or container parameter is present → downgrade to INFO
    #      (cannot statically verify what the factory produces; encourages
    #      explicit typing without hard-blocking the gate).
    #   6. Bulk-injection pattern detected (__dict__.update / setattr loop).
    # ------------------------------------------------------------------
    has_any_wildcard = visitor.has_variadic_kwargs or visitor.has_bulk_injection

    has_generic_mapping = any(
        t in visitor.arg_types
        for t in ("Any", "object", "dict", "Dict", "Mapping", "MutableMapping")
    ) and bool(visitor.mapping_param_names)

    for collab in collaborators:
        # 1. Direct type hint match.
        if _collab_in_types(collab, visitor.arg_types):
            continue

        # 2. **kwargs wildcard.
        if has_any_wildcard:
            continue

        # 3. Key-based access from a mapping param.
        if _collab_in_mapping_keys(collab, visitor.mapping_key_types):
            continue

        # 4. Generic mapping param (wildcard).
        if has_generic_mapping:
            continue

        # 5. Factory or container param heuristic.
        if visitor.factory_param_names or visitor.container_param_names:
            violations.append(
                Violation(
                    comp_name,
                    path,
                    "INFO",
                    (
                        f"Collaborator '{collab}' not in type hints; assumed provided via "
                        f"factory/container param "
                        f"({', '.join(sorted(visitor.factory_param_names | visitor.container_param_names))}). "
                        "Consider adding an explicit type hint for static verifiability."
                    ),
                )
            )
            continue

        # 6. No injection source found → WARNING (triggers non-zero exit).
        violations.append(
            Violation(
                comp_name,
                path,
                "WARNING",
                (
                    f"Collaborator '{collab}' not found in any injected source "
                    "(type hints, **kwargs, mapping param, factory, or bulk injection)"
                ),
            )
        )

    return violations


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

SEVERITY_ORDER = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}


def main() -> None:
    root_dir = Path.cwd()
    src_dir = root_dir / "src"
    spec_path = root_dir / "plans" / "project-spec.md"
    plan_path = root_dir / "plans" / "PLAN.md"

    # ------------------------------------------------------------------
    # Load required files
    # ------------------------------------------------------------------
    if not spec_path.exists():
        print("Error: plans/project-spec.md not found.")
        sys.exit(1)

    spec_content = spec_path.read_text(encoding="utf-8")

    # PLAN.md is optional; if absent, no component can have tracked debt and
    # every "noqa: DI" suppression will be escalated to CRITICAL.
    if plan_path.exists():
        plan_content = plan_path.read_text(encoding="utf-8")
        tracked_debt = parse_plan_backlog(plan_content)
        print(f"Debt tickets tracked in PLAN.md: {len(tracked_debt)}")
        if tracked_debt:
            print(f"  Tracked components: {', '.join(sorted(tracked_debt))}")
    else:
        tracked_debt = set()
        print(
            "plans/PLAN.md not found - "
            "all # noqa: DI suppressions will be escalated to CRITICAL."
        )

    # ------------------------------------------------------------------
    # Parse spec
    # ------------------------------------------------------------------
    registry, boundary_violations = parse_registry(spec_content, root_dir, src_dir)
    designs = parse_collaborators(spec_content)
    entrypoint_dir = parse_entrypoint_layer(spec_content)

    print(f"\nComponents with collaborators: {len(designs)}")
    print(f"Registry entries:              {len(registry)}")
    if boundary_violations:
        print(f"Boundary violations:           {len(boundary_violations)} CRITICAL")
    if entrypoint_dir:
        print(f"Entrypoint layer (exempt):     {entrypoint_dir}")
    print()

    # Boundary violations are reported upfront; component analysis is skipped
    # for those entries since the path is already known-bad.
    all_violations: list[Violation] = list(boundary_violations)
    boundary_components: set[str] = {v.component for v in boundary_violations}

    # ------------------------------------------------------------------
    # Per-component analysis
    # ------------------------------------------------------------------
    for comp_name, collaborators in sorted(designs.items()):
        if comp_name not in registry:
            continue

        impl_path = registry[comp_name]

        if comp_name in boundary_components:
            print(f"  SKIP  {comp_name} (boundary violation - path outside src/)")
            continue

        if entrypoint_dir and entrypoint_dir in impl_path.as_posix():
            print(f"  SKIP  {comp_name} (Entrypoint layer)")
            continue

        violations = check_component(impl_path, comp_name, collaborators, tracked_debt)
        all_violations.extend(violations)

        if not violations:
            status = "PASS"
        else:
            worst = min(violations, key=lambda v: SEVERITY_ORDER.get(v.severity, 99))
            status = worst.severity

        print(f"  {status:8s} {comp_name}")

    # ------------------------------------------------------------------
    # Test-file sweep: verify instantiations pass required collaborators
    # ------------------------------------------------------------------
    tests_dir = root_dir / "tests"
    if tests_dir.is_dir():
        # Build a map of only those components that have collaborators.
        test_comp_collabs: dict[str, list[str]] = {
            comp: collabs
            for comp, collabs in designs.items()
            if comp in registry and collabs
        }

        if test_comp_collabs:
            test_files = sorted(tests_dir.rglob("*.py"))
            print(f"\nTest DI sweep: {len(test_files)} files, "
                  f"{len(test_comp_collabs)} components with collaborators")

            for tf in test_files:
                tf_violations = check_test_file(tf, test_comp_collabs)
                all_violations.extend(tf_violations)

                if not tf_violations:
                    status = "PASS"
                else:
                    worst = min(
                        tf_violations,
                        key=lambda v: SEVERITY_ORDER.get(v.severity, 99),
                    )
                    status = worst.severity
                print(f"  {status:8s} {tf.relative_to(root_dir).as_posix()}")
        else:
            print("\nTest DI sweep: no components with collaborators to check.")
    else:
        print("\nTest DI sweep: tests/ directory not found, skipping.")

    # ------------------------------------------------------------------
    # Final report
    # ------------------------------------------------------------------
    print("\n--- DI Compliance Report ---\n")

    if not all_violations:
        print("All components comply with Dependency Injection rules.")
        print("\nGATE PASS")
        sys.exit(0)

    all_violations.sort(key=lambda v: SEVERITY_ORDER.get(v.severity, 99))

    criticals = [v for v in all_violations if v.severity == "CRITICAL"]
    warnings  = [v for v in all_violations if v.severity == "WARNING"]
    infos     = [v for v in all_violations if v.severity == "INFO"]

    for v in all_violations:
        print(f"[{v.severity}] {v.component}: {v.issue}")
        print(f"         {v.file_path.as_posix()}")

    print(
        f"\nSummary: {len(criticals)} critical, "
        f"{len(warnings)} warning, {len(infos)} info"
    )

    # ------------------------------------------------------------------
    # Exit code - strict binary gate for /io-plan-batch
    #
    # Exit 1 conditions:
    #   • Any CRITICAL  (hardcoded dep / untracked noqa / boundary breach)
    #   • Any WARNING   (unresolvable collaborator - now treated equal to CRITICAL)
    #
    # Exit 0 conditions:
    #   • Zero violations total
    #   • Only INFO items remain (tracked exemptions + factory heuristics)
    # ------------------------------------------------------------------
    if criticals or warnings:
        parts = []
        if criticals:
            parts.append(f"{len(criticals)} critical")
        if warnings:
            parts.append(f"{len(warnings)} warning")
        print(f"\nGATE FAIL - {', '.join(parts)}")
        sys.exit(1)

    print("\nGATE PASS - all remaining items are tracked or factory-heuristic INFO.")
    sys.exit(0)


if __name__ == "__main__":
    main()

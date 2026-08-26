"""Scan one Python file into a :class:`ModuleInfo` using the stdlib ``ast``.

The index runs over the whole project on every invocation, so this pass is
deliberately cheap: ``ast.parse`` rather than LibCST, no formatting, no exact
columns beyond what ``ast`` hands us for free.  The one comment-dependent
feature -- the ``# drf-lint:`` markers -- is a line scan of source we have
already read.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from mitol.drf_lint.index.model import (
    ClassInfo,
    ImportedName,
    Member,
    MemberRef,
    ModuleInfo,
    QueryHit,
)
from mitol.drf_lint.rules import patterns

_MARKER_RE = re.compile(r"#\s*drf-lint:\s*(no-query|query)\b")

_PROPERTY_DECORATORS = frozenset({"property", "cached_property"})
_RELATION_CHAIN_LEN = 3


def _flatten_ast_chain(node: ast.expr) -> tuple[str, ...]:
    """Flatten an ``ast`` attribute path, mirroring the LibCST flattener."""
    segments: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        segments.append(current.attr)
        current = current.value
    segments.append(current.id if isinstance(current, ast.Name) else patterns.UNKNOWN)
    segments.reverse()
    return tuple(segments)


def _relation_root(chain: tuple[str, ...]) -> str | None:
    """Relation name for a ``self.<relation>.<method>`` chain.

    Only chains of exactly three segments qualify.  A deeper chain such as
    ``self.author.books.all()`` would need a ``author__books`` prefetch, which
    ``is_prefetched()`` cannot evaluate, so treating it as uncoverable avoids
    advising a developer to add an entry that can never be satisfied.
    """
    if len(chain) == _RELATION_CHAIN_LEN and chain[0] == "self":
        return chain[1]
    return None


def _decorator_kind(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Classify a function by its decorators."""
    for decorator in node.decorator_list:
        name = decorator
        if isinstance(name, ast.Call):
            name = name.func
        if not isinstance(name, ast.Attribute | ast.Name):
            continue
        last = _flatten_ast_chain(name)[-1]
        if last in _PROPERTY_DECORATORS:
            return "cached_property" if last == "cached_property" else "property"
        if last in {"classmethod", "staticmethod"}:
            return last
    return "method"


class _BodyVisitor(ast.NodeVisitor):
    """Collect direct query hits and outgoing references from one function body."""

    def __init__(self, relations: dict[str, str]) -> None:
        self.relations = relations
        self.hits: list[QueryHit] = []
        self.refs: list[MemberRef] = []

    # -------------------------------------------------------------- #

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        # Nested defs belong to the enclosing member: keep walking.
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef  # noqa: N815

    def visit_Call(self, node: ast.Call) -> None:
        chain = _flatten_ast_chain(node.func)
        self._record_call(node, chain)
        self._record_ref(chain, is_call=True, line=node.lineno)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        chain = _flatten_ast_chain(node)
        # Bare relation descriptor traversal: `self.author.name` fetches the
        # related row unless the caller select_related()'d it.
        if (
            len(chain) == _RELATION_CHAIN_LEN
            and chain[0] == "self"
            and chain[1] in self.relations
        ):
            self.hits.append(
                QueryHit(
                    line=node.lineno,
                    relation_root=chain[1],
                    method=None,
                    prefetch_safe=True,
                )
            )
        self._record_ref(chain, is_call=False, line=node.lineno)
        self.generic_visit(node)

    # -------------------------------------------------------------- #

    def _record_call(self, node: ast.Call, chain: tuple[str, ...]) -> None:
        if patterns.chain_has_manager(chain):
            self.hits.append(
                QueryHit(
                    line=node.lineno,
                    relation_root=None,
                    method=chain[-1],
                    prefetch_safe=False,
                )
            )
            return
        if patterns.is_queryset_method_call(chain):
            method = chain[-1]
            self.hits.append(
                QueryHit(
                    line=node.lineno,
                    relation_root=_relation_root(chain),
                    method=method,
                    prefetch_safe=method in patterns.PREFETCH_SAFE_METHODS,
                )
            )
            return
        # Model-body-only vocabulary: `self.children.count()`.  Zero arguments
        # and a >=3 segment chain keep `self.data.get("k")` out.
        if (
            len(chain) >= _RELATION_CHAIN_LEN
            and chain[-1] in patterns.MODEL_QUERY_METHODS_NOARG
            and not node.args
            and not node.keywords
        ):
            self.hits.append(
                QueryHit(
                    line=node.lineno,
                    relation_root=_relation_root(chain),
                    method=chain[-1],
                    prefetch_safe=False,
                )
            )
            return
        if chain[-1] in patterns.RAW_SQL_METHODS and len(chain) > 1:
            self.hits.append(
                QueryHit(
                    line=node.lineno,
                    relation_root=None,
                    method=chain[-1],
                    prefetch_safe=False,
                )
            )

    def _record_ref(self, chain: tuple[str, ...], *, is_call: bool, line: int) -> None:
        if patterns.UNKNOWN in chain:
            return
        max_ref_len = 3
        if 1 <= len(chain) <= max_ref_len:
            self.refs.append(MemberRef(path=chain, is_call=is_call, line=line))


def _string_elements(node: ast.expr) -> list[tuple[str, int, int]]:
    """Extract string literals from a list/tuple/set literal, with positions."""
    if not isinstance(node, ast.List | ast.Tuple | ast.Set):
        return []
    return [
        (element.value, element.lineno, element.col_offset)
        for element in node.elts
        if isinstance(element, ast.Constant) and isinstance(element.value, str)
    ]


def _relation_target(node: ast.expr, kinds: frozenset[str]) -> str | None:
    """Return the declared target of a relation field call of one of *kinds*."""
    if not isinstance(node, ast.Call):
        return None
    chain = _flatten_ast_chain(node.func)
    if chain[-1] not in kinds:
        return None
    if node.args:
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            return first.value
        return ".".join(_flatten_ast_chain(first))
    return ""


def _markers(source: str) -> dict[int, str]:
    """Map 1-based line numbers to their ``# drf-lint:`` marker, if any."""
    out: dict[int, str] = {}
    for number, line in enumerate(source.splitlines(), start=1):
        match = _MARKER_RE.search(line)
        if match:
            out[number] = match.group(1)
    return out


def _forced(
    node: ast.FunctionDef | ast.AsyncFunctionDef, markers: dict[int, str]
) -> str | None:
    """Marker attached to a function's ``def`` line or any decorator line."""
    lines = [node.lineno, *(d.lineno for d in node.decorator_list)]
    for line in lines:
        if line in markers:
            return markers[line]
    return None


def _scan_imports(tree: ast.Module) -> dict[str, ImportedName]:
    """Build the module's ``local alias -> import target`` table."""
    imports: dict[str, ImportedName] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                local = alias.asname or alias.name.split(".")[0]
                target = alias.name if alias.asname else alias.name.split(".")[0]
                imports[local] = ImportedName(module=target, name=None, level=0)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                local = alias.asname or alias.name
                imports[local] = ImportedName(
                    module=node.module, name=alias.name, level=node.level
                )
    return imports


def _scan_class(node: ast.ClassDef, module: str, markers: dict[int, str]) -> ClassInfo:
    """Scan a class body into a :class:`ClassInfo`."""
    info = ClassInfo(
        name=node.name,
        module=module,
        line=node.lineno,
        col=node.col_offset,
        bases=tuple(_flatten_ast_chain(base) for base in node.bases),
    )

    # First pass: class-level assignments.  Relations must be known before the
    # method bodies are walked, since `self.<relation>` traversal is a hit.
    for statement in node.body:
        if isinstance(statement, ast.Assign | ast.AnnAssign):
            _scan_class_assignment(statement, info)

    # Second pass: method bodies.
    for statement in node.body:
        if isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef):
            info.members[statement.name] = _scan_function(
                statement, info.relations, markers
            )

    return info


def _scan_class_assignment(
    statement: ast.Assign | ast.AnnAssign, info: ClassInfo
) -> None:
    """Record one class-level assignment: a relation, a contract, or a shadow."""
    targets = (
        statement.targets if isinstance(statement, ast.Assign) else [statement.target]
    )
    value = statement.value
    for target in targets:
        if not isinstance(target, ast.Name):
            continue
        if target.id == "required_prefetches" and value is not None:
            info.prefetch_entries = tuple(_string_elements(value))
            info.required_prefetches = tuple(e[0] for e in info.prefetch_entries)
            info.prefetch_line = statement.lineno
            continue
        if value is not None:
            relation = _relation_target(value, patterns.RELATION_FIELD_TYPES)
            if relation is not None:
                info.relations[target.id] = relation
            many = _relation_target(value, patterns.MANY_RELATION_FIELD_TYPES)
            if many is not None:
                info.many_relations[target.id] = many
        # Recorded even when it is a plain value, so that an assignment in a
        # subclass shadows a querying property of the same name on a base.
        info.members[target.id] = Member(
            name=target.id,
            kind="attribute",
            line=statement.lineno,
            col=statement.col_offset,
        )


def _scan_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    relations: dict[str, str],
    markers: dict[int, str],
    kind: str | None = None,
) -> Member:
    """Scan a function body into a :class:`Member`."""
    visitor = _BodyVisitor(relations)
    for statement in node.body:
        visitor.visit(statement)
    return Member(
        name=node.name,
        kind=kind or _decorator_kind(node),
        line=node.lineno,
        col=node.col_offset,
        hits=tuple(visitor.hits),
        refs=tuple(visitor.refs),
        forced=_forced(node, markers),
    )


def scan_source(
    source: str,
    dotted: str,
    path: str,
    *,
    is_package: bool = False,
    stat: tuple[int, int] = (0, 0),
) -> ModuleInfo | None:
    """Scan *source* into a :class:`ModuleInfo`, or None if it will not parse.

    *stat* is the ``(mtime_ns, size)`` pair the cache keys invalidation on.
    """
    mtime_ns, size = stat
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError):
        return None

    markers = _markers(source)
    module = ModuleInfo(
        dotted=dotted,
        path=path,
        is_package=is_package,
        imports=_scan_imports(tree),
        mtime_ns=mtime_ns,
        size=size,
    )
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            module.classes[node.name] = _scan_class(node, dotted, markers)
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            module.functions[node.name] = _scan_function(node, {}, markers, "function")
    return module


def scan_file(
    path: Path, dotted: str, *, is_package: bool = False
) -> ModuleInfo | None:
    """Read and scan *path*.  Returns None on any read or parse failure."""
    try:
        info = path.stat()
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    return scan_source(
        source,
        dotted,
        str(path),
        is_package=is_package,
        stat=(info.st_mtime_ns, info.st_size),
    )

"""LibCST visitor that checks for ORM violations in DRF serializer classes."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import libcst as cst
from libcst.metadata import MetadataWrapper, ParentNodeProvider, PositionProvider
from mitol.drf_lint.index import ClassInfo, ProjectIndex, explain, transitive_hits
from mitol.drf_lint.index.model import MemberId, MemberRef
from mitol.drf_lint.index.resolve import (
    class_all_relations,
    class_member,
    class_relations,
    class_required_prefetches,
    inherits_from,
    lookup_class,
    resolve_ref,
)
from mitol.drf_lint.rules import (
    orm001,
    orm002,
    orm003,
    orm004,
    orm005,
    orm006,
    orm007,
    orm008,
    orm009,
    patterns,
    prefetch,
)
from mitol.drf_lint.rules.base import Violation

ALL_RULES: frozenset[str] = frozenset(
    {
        orm001.RULE,
        orm002.RULE,
        orm003.RULE,
        orm004.RULE,
        orm005.RULE,
        orm006.RULE,
        orm007.RULE,
        orm008.RULE,
        orm009.RULE,
    }
)

#: Rules that need nothing beyond the file under check.
LOCAL_RULES: frozenset[str] = frozenset({orm001.RULE, orm002.RULE})

#: Everything else, which depends on the project index or on a
#: ``required_prefetches`` declaration.
CROSS_FILE_RULES: frozenset[str] = ALL_RULES - LOCAL_RULES

# These serializer methods are only ever invoked during write operations
# (POST / PATCH / PUT) on a single resource, so N+1 queries cannot occur
# in the same way as in read-path methods like `to_representation` or
# `get_*` methods.  Flagging them produces false positives.
# NOTE: This exemption intentionally does NOT apply to ListSerializer
# subclasses, whose create/update methods handle bulk operations where
# N+1 patterns can and do occur.
_EXEMPT_METHODS: frozenset[str] = frozenset(
    {
        "validate",
        "create",
        "update",
        "to_internal_value",
    }
)

_ALL_FIELDS = "__all__"
_RECEIVER_PARAM_COUNT = 2


@dataclass(frozen=True)
class CheckContext:
    """Everything the cross-file rules need beyond the source under check.

    A ``None`` index (the default) disables every cross-file rule, so
    ``check_source(src)`` behaves exactly as it did before the index existed.
    """

    index: ProjectIndex | None = None
    module: str | None = None
    receiver_mode: str = "strict"
    model_resolution: str = "unique"
    enabled_rules: frozenset[str] = ALL_RULES
    prefetch_bases: frozenset[str] = prefetch.DEFAULT_PREFETCH_BASES
    prefetch_aware: bool = True
    """Whether ``required_prefetches`` declarations are honoured at all.

    Kept separate from :attr:`index` because the declaration is local to the
    file under check: it stays useful without an index, and is only turned off
    wholesale by ``--no-cross-file``.
    """

    unresolved: list[tuple[int, str]] = field(default_factory=list)

    @property
    def cross_file(self) -> bool:
        """Whether cross-file analysis is possible at all."""
        return self.index is not None and self.module is not None

    def enabled(self, rule: str) -> bool:
        """Whether *rule* should be reported."""
        return rule in self.enabled_rules


@dataclass
class _DeclaredField:
    """A field written out explicitly in the serializer body."""

    name: str
    line: int
    col: int
    source: str | None = None
    source_line: int = 0
    source_col: int = 0
    method_name: str | None = None
    is_method_field: bool = False
    is_nested: bool = False


@dataclass
class _SerializerInfo:
    """Everything the pre-pass learned about one serializer class."""

    name: str
    line: int
    col: int
    is_list: bool
    model: ClassInfo | None = None
    model_expr: str | None = None
    model_line: int = 0
    fields: tuple[tuple[str, int, int], ...] = ()
    fields_dynamic: bool = False
    fields_all: bool = False
    declared: dict[str, _DeclaredField] = field(default_factory=dict)
    required_prefetches: tuple[str, ...] | None = None
    prefetch_entries: tuple[tuple[str, int, int], ...] = ()
    prefetch_local: bool = False
    is_prefetch_base: bool = False

    @property
    def method_field_names(self) -> set[str]:
        """Names of the ``get_*`` methods backing ``SerializerMethodField``s."""
        return {
            declared.method_name or f"get_{declared.name}"
            for declared in self.declared.values()
            if declared.is_method_field
        }


# ------------------------------------------------------------------ #
# Serializer / class heuristics
# ------------------------------------------------------------------ #


def _is_serializer_class(node: cst.ClassDef) -> bool:
    """Heuristic: class name ends in 'Serializer' or a base contains 'Serializer'."""
    if node.name.value.endswith("Serializer"):
        return True
    return any(_expr_contains_serializer(base.value) for base in node.bases)


def _is_list_serializer_class(node: cst.ClassDef | None) -> bool:
    """Return True if the class appears to be a ListSerializer subclass.

    ListSerializer.create/update operate on multiple objects and can have
    genuine N+1 issues, so write-path exemptions do not apply.
    """
    if node is None:
        return False
    if node.name.value.endswith("ListSerializer"):
        return True
    return any(_expr_contains_list_serializer(base.value) for base in node.bases)


def _expr_contains_list_serializer(expr: cst.BaseExpression) -> bool:
    if isinstance(expr, cst.Name):
        return expr.value.endswith("ListSerializer")
    if isinstance(expr, cst.Attribute):
        return expr.attr.value.endswith(
            "ListSerializer"
        ) or _expr_contains_list_serializer(expr.value)
    return False


def _expr_contains_serializer(expr: cst.BaseExpression) -> bool:
    if isinstance(expr, cst.Name):
        return "Serializer" in expr.value
    if isinstance(expr, cst.Attribute):
        return "Serializer" in expr.attr.value or _expr_contains_serializer(expr.value)
    return False


def _is_exempt_method(node: cst.FunctionDef) -> bool:
    """Return True if *node* is a write-path method exempt from ORM checks."""
    name = node.name.value
    return name in _EXEMPT_METHODS or name.startswith("validate_")


# ------------------------------------------------------------------ #
# Small CST helpers
# ------------------------------------------------------------------ #


def _string_value(node: cst.BaseExpression) -> str | None:
    """Evaluate a plain string literal, or None if it isn't one."""
    if isinstance(node, cst.SimpleString):
        value = node.evaluated_value
        return value if isinstance(value, str) else None
    return None


def _iter_assignments(
    body: cst.IndentedBlock,
) -> Iterator[tuple[str, cst.BaseExpression, cst.CSTNode]]:
    """Yield ``(name, value, target_node)`` for each simple assignment in a body."""
    for statement in body.body:
        if not isinstance(statement, cst.SimpleStatementLine):
            continue
        for small in statement.body:
            if isinstance(small, cst.Assign):
                for target in small.targets:
                    if isinstance(target.target, cst.Name):
                        yield target.target.value, small.value, target.target
            elif (
                isinstance(small, cst.AnnAssign)
                and isinstance(small.target, cst.Name)
                and small.value is not None
            ):
                yield small.target.value, small.value, small.target


def _call_kwarg(node: cst.Call, name: str) -> cst.BaseExpression | None:
    """Return the value of keyword argument *name*, if present."""
    for arg in node.args:
        if arg.keyword is not None and arg.keyword.value == name:
            return arg.value
    return None


# ------------------------------------------------------------------ #
# Pre-pass: collect per-serializer metadata
# ------------------------------------------------------------------ #


class _InfoCollector(cst.CSTVisitor):
    """Gather ``Meta``, declared fields and ``required_prefetches`` per class.

    This runs before the main walk because ``class Meta`` may appear textually
    after the methods that depend on it.
    """

    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self, ctx: CheckContext) -> None:
        self.ctx = ctx
        self.infos: dict[tuple[int, int], _SerializerInfo] = {}

    def visit_ClassDef(self, node: cst.ClassDef) -> None:  # noqa: N802
        if not _is_serializer_class(node):
            return
        start = self.get_metadata(PositionProvider, node).start
        info = _SerializerInfo(
            name=node.name.value,
            line=start.line,
            col=start.column,
            is_list=_is_list_serializer_class(node),
        )
        self._read_body(node, info)
        self._resolve_model(info)
        self.infos[start.line, start.column] = info

    # -------------------------------------------------------------- #

    def _read_body(self, node: cst.ClassDef, info: _SerializerInfo) -> None:
        if not isinstance(node.body, cst.IndentedBlock):
            return
        for name, value, target in _iter_assignments(node.body):
            if name == "required_prefetches":
                entries, _ = self._string_elements(value)
                info.prefetch_entries = tuple(entries)
                info.required_prefetches = tuple(entry[0] for entry in entries)
                info.prefetch_local = True
            elif isinstance(value, cst.Call):
                declared = self._declared_field(name, value, target)
                if declared is not None:
                    info.declared[name] = declared
        for statement in node.body.body:
            if isinstance(statement, cst.ClassDef) and statement.name.value == "Meta":
                self._read_meta(statement, info)

    def _declared_field(
        self, name: str, value: cst.Call, target: cst.CSTNode
    ) -> _DeclaredField | None:
        chain = patterns.flatten_cst_chain(value.func)
        callee = chain[-1]
        if not callee.endswith(("Field", "Serializer")):
            return None
        start = self.get_metadata(PositionProvider, target).start
        declared = _DeclaredField(
            name=name,
            line=start.line,
            col=start.column,
            is_method_field=callee == "SerializerMethodField",
            is_nested=callee.endswith("Serializer"),
        )
        source = _call_kwarg(value, "source")
        if source is not None:
            declared.source = _string_value(source)
            source_start = self.get_metadata(PositionProvider, source).start
            declared.source_line = source_start.line
            declared.source_col = source_start.column
        method_name = _call_kwarg(value, "method_name")
        if method_name is not None:
            declared.method_name = _string_value(method_name)
        return declared

    def _read_meta(self, node: cst.ClassDef, info: _SerializerInfo) -> None:
        if not isinstance(node.body, cst.IndentedBlock):
            return
        for name, value, _ in _iter_assignments(node.body):
            if name == "model":
                info.model_expr = ".".join(patterns.flatten_cst_chain(value))
                info.model_line = self.get_metadata(PositionProvider, value).start.line
            elif name == "fields":
                if _string_value(value) == _ALL_FIELDS:
                    info.fields_all = True
                    continue
                entries, dynamic = self._string_elements(value)
                info.fields = tuple(entries)
                info.fields_dynamic = dynamic

    def _string_elements(
        self, node: cst.BaseExpression
    ) -> tuple[list[tuple[str, int, int]], bool]:
        """Extract string literals from a sequence literal, with their positions.

        Returns the entries plus a flag saying whether part of the expression
        was opaque (a constant, a comprehension), in which case the list is
        known to be incomplete.
        """
        if isinstance(node, cst.List | cst.Tuple | cst.Set):
            entries: list[tuple[str, int, int]] = []
            dynamic = False
            for element in node.elements:
                value = _string_value(element.value)
                if value is None:
                    dynamic = True
                    continue
                start = self.get_metadata(PositionProvider, element.value).start
                entries.append((value, start.line, start.column))
            return entries, dynamic
        if isinstance(node, cst.BinaryOperation) and isinstance(node.operator, cst.Add):
            left, left_dynamic = self._string_elements(node.left)
            right, right_dynamic = self._string_elements(node.right)
            return [*left, *right], left_dynamic or right_dynamic
        return [], True

    def _resolve_model(self, info: _SerializerInfo) -> None:
        """Resolve ``Meta.model`` and the prefetch contract through the index."""
        ctx = self.ctx
        index = ctx.index
        if index is None or ctx.module is None:
            return
        if info.model_expr:
            info.model = lookup_class(
                index,
                ctx.module,
                tuple(info.model_expr.split(".")),
                fallback=ctx.model_resolution,
            )
            if info.model is None:
                ctx.unresolved.append((info.model_line, info.model_expr))

        own = index.modules.get(ctx.module)
        own_class = own.classes.get(info.name) if own else None
        if own_class is None:
            return
        info.is_prefetch_base = inherits_from(
            index, own_class, ctx.prefetch_bases, fallback=ctx.model_resolution
        )
        if info.required_prefetches is None:
            inherited = class_required_prefetches(
                index, own_class, fallback=ctx.model_resolution
            )
            if inherited is not None:
                info.required_prefetches = inherited[1]


# ------------------------------------------------------------------ #
# Main pass
# ------------------------------------------------------------------ #


class _SerializerORMVisitor(cst.CSTVisitor):
    """Walk a CST looking for ORM calls inside serializer class methods."""

    METADATA_DEPENDENCIES = (PositionProvider, ParentNodeProvider)

    def __init__(
        self,
        ctx: CheckContext,
        infos: dict[tuple[int, int], _SerializerInfo],
    ) -> None:
        self.ctx = ctx
        self.infos = infos
        self._class_stack: list[cst.ClassDef] = []
        self._info_stack: list[_SerializerInfo | None] = []
        self._in_serializer_method: bool = False
        self._method_state_stack: list[bool] = []
        self._receiver_stack: list[set[str]] = []
        self._receivers: set[str] = set()
        # Tracks how many function scopes deep we are.  Class definitions do
        # not increment this counter, so a direct method on a class always
        # sees depth 0 when it is first entered.
        self._function_depth: int = 0
        self.violations: list[Violation] = []

    # ------------------------------------------------------------------ #
    # Class tracking
    # ------------------------------------------------------------------ #

    def visit_ClassDef(self, node: cst.ClassDef) -> None:  # noqa: N802
        self._class_stack.append(node)
        start = self.get_metadata(PositionProvider, node).start
        info = self.infos.get((start.line, start.column))
        self._info_stack.append(info)
        if info is not None:
            self._check_class_declaration(info)

    def leave_ClassDef(self, node: cst.ClassDef) -> None:  # noqa: ARG002, N802
        info = self._info_stack.pop() if self._info_stack else None
        if info is not None:
            self._check_fields(info)
        if self._class_stack:
            self._class_stack.pop()

    def _required(self, info: _SerializerInfo | None) -> tuple[str, ...] | None:
        """Return the prefetch contract in force, or None if it is ignored."""
        if info is None or not self.ctx.prefetch_aware:
            return None
        return info.required_prefetches

    @property
    def _info(self) -> _SerializerInfo | None:
        """The innermost serializer class currently being visited."""
        for info in reversed(self._info_stack):
            if info is not None:
                return info
        return None

    # ------------------------------------------------------------------ #
    # Method tracking
    # ------------------------------------------------------------------ #

    def visit_FunctionDef(self, node: cst.FunctionDef) -> None:  # noqa: N802
        # Save current state before entering this function.
        self._method_state_stack.append(self._in_serializer_method)
        self._receiver_stack.append(self._receivers)
        if self._function_depth == 0:
            # Direct class method (or module-level function): apply the full
            # serializer / exempt-name logic.  Nested classes (e.g. Meta) also
            # produce depth-0 entry points, and their non-serializer class name
            # correctly suppresses checking via _is_serializer_class.
            enclosing = self._class_stack[-1] if self._class_stack else None
            in_serializer = bool(enclosing and _is_serializer_class(enclosing))
            # Write-path methods are exempt only for regular (single-resource)
            # serializers.  ListSerializer.create/update handle bulk operations
            # and can have genuine N+1 issues, so they are NOT exempt.
            is_list = _is_list_serializer_class(enclosing)
            exempt = in_serializer and not is_list and _is_exempt_method(node)
            self._in_serializer_method = in_serializer and not exempt
            self._receivers = self._instance_params(node, is_list=is_list)
        # else: nested function - inherit the enclosing function's state so
        # that helpers defined inside an exempt method stay exempt, and helpers
        # inside a checked method are still checked.
        self._function_depth += 1

    def leave_FunctionDef(self, node: cst.FunctionDef) -> None:  # noqa: ARG002, N802
        self._function_depth -= 1
        if self._method_state_stack:
            self._in_serializer_method = self._method_state_stack.pop()
        if self._receiver_stack:
            self._receivers = self._receiver_stack.pop()

    def _instance_params(self, node: cst.FunctionDef, *, is_list: bool) -> set[str]:
        """Parameter names this method is guaranteed to receive the model in.

        Only DRF's own contracts are trusted: the second argument of a
        ``get_<field>`` method and of ``to_representation``.  Inferring from a
        parameter *named* ``instance`` fires inside generic helpers, so that is
        opt-in via ``receiver_mode="names"``.
        """
        info = self._info
        params = node.params.params
        if len(params) < _RECEIVER_PARAM_COUNT:
            return set()
        name = node.name.value
        trusted = name.startswith("get_") or (
            name == "to_representation" and not is_list
        )
        if info is not None and name in info.method_field_names:
            trusted = True
        if not trusted and self.ctx.receiver_mode == "names":
            trusted = params[1].name.value in {"instance", "obj"}
        return {params[1].name.value} if trusted else set()

    def visit_Assign(self, node: cst.Assign) -> None:  # noqa: N802
        """Track single-name aliases of the model instance."""
        if not self._in_serializer_method:
            return
        targets = [t.target for t in node.targets if isinstance(t.target, cst.Name)]
        if not targets:
            return
        chain = patterns.flatten_cst_chain(node.value)
        aliased = bool(chain) and self._receiver_length(chain) == len(chain)
        for target in targets:
            if aliased:
                self._receivers.add(target.value)
            else:
                self._receivers.discard(target.value)

    # ------------------------------------------------------------------ #
    # Receiver inference
    # ------------------------------------------------------------------ #

    def _receiver_length(self, chain: tuple[str, ...]) -> int:
        """How many leading segments of *chain* denote the model instance."""
        if not chain:
            return 0
        if chain[0] in self._receivers:
            return 1
        if (
            len(chain) >= _RECEIVER_PARAM_COUNT
            and chain[0] == "self"
            and chain[1] == "instance"
        ):
            return _RECEIVER_PARAM_COUNT
        return 0

    # ------------------------------------------------------------------ #
    # Violation detection
    # ------------------------------------------------------------------ #

    def visit_Call(self, node: cst.Call) -> None:  # noqa: N802
        if not self._in_serializer_method:
            return
        start = self.get_metadata(PositionProvider, node).start
        line, col = start.line, start.column
        chain = patterns.flatten_cst_chain(node.func)

        violation = orm001.check(node, line, col)
        if violation is not None:
            self._add(violation)
            return
        if patterns.is_queryset_method_call(chain):
            self._check_related_call(chain, line, col)
            return
        self._check_callable(chain, line, col)

    def visit_Attribute(self, node: cst.Attribute) -> None:  # noqa: N802
        if not self._in_serializer_method or not self.ctx.cross_file:
            return
        info = self._info
        if info is None or info.model is None:
            return
        parent = self.get_metadata(ParentNodeProvider, node)
        if isinstance(parent, cst.Call) and parent.func is node:
            return  # the call itself is ORM004's business
        if isinstance(parent, cst.AssignTarget | cst.AugAssign | cst.Del):
            return
        chain = patterns.flatten_cst_chain(node)
        prefix = self._receiver_length(chain)
        if prefix == 0 or len(chain) != prefix + 1:
            return
        start = self.get_metadata(PositionProvider, node).start
        self._check_model_attribute(info, chain[-1], start.line, start.column)

    # -------------------------------------------------------------- #

    def _check_related_call(self, chain: tuple[str, ...], line: int, col: int) -> None:
        """ORM002 / ORM007 for ``<receiver>.<relation>.<method>()``."""
        info = self._info
        prefix = self._receiver_length(chain)
        method = chain[-1]
        relation = chain[prefix] if prefix and len(chain) > prefix + 1 else None
        required = self._required(info)

        if relation is None or required is None:
            self._add(Violation(orm002.RULE, orm002.MESSAGE, line, col))
            return

        safe = method in patterns.PREFETCH_SAFE_METHODS
        declared = relation in required
        if declared and safe:
            return  # provably reads the prefetch cache
        if declared:
            self._add(
                Violation(
                    orm002.RULE, orm002.prefetched_message(relation, method), line, col
                )
            )
            return
        if safe:
            self._add(
                Violation(
                    orm007.RULE,
                    orm007.message((relation,), f"relation {relation}"),
                    line,
                    col,
                )
            )
            return
        self._add(Violation(orm002.RULE, orm002.MESSAGE, line, col))

    def _check_callable(self, chain: tuple[str, ...], line: int, col: int) -> None:
        """ORM004: a call that reaches the database somewhere down the stack."""
        ctx = self.ctx
        index = ctx.index
        if index is None or ctx.module is None or patterns.UNKNOWN in chain:
            return
        info = self._info

        prefix = self._receiver_length(chain)
        if prefix and len(chain) == prefix + 1 and info is not None and info.model:
            self._check_model_attribute(info, chain[-1], line, col, called=True)
            return

        target = resolve_ref(
            index,
            ctx.module,
            info.name if info else "",
            MemberRef(path=chain, is_call=True, line=line),
            fallback=ctx.model_resolution,
        )
        if target is None:
            return
        member = index.member(*target)
        if member is None or not member.queries:
            return
        verdict = prefetch.classify(
            transitive_hits(index, target), self._required(info)
        )
        label = f"{target[1]}.{target[2]}" if target[1] else target[2]
        self._emit(
            verdict,
            Violation(
                orm004.RULE, orm004.message(label, explain(index, target)), line, col
            ),
            label,
        )

    def _check_model_attribute(
        self,
        info: _SerializerInfo,
        name: str,
        line: int,
        col: int,
        *,
        called: bool = False,
    ) -> None:
        """ORM003 / ORM006 / ORM007 for a member touched on the model instance."""
        ctx = self.ctx
        index = ctx.index
        model = info.model
        if index is None or model is None:
            return

        relations = class_relations(index, model, fallback=ctx.model_resolution)
        if name in relations and not called:
            self._check_relation_traversal(info, model, name, line, col)
            return

        found = class_member(index, model, name, fallback=ctx.model_resolution)
        if found is None:
            return
        owner, member = found
        if not member.queries or (not called and not member.is_property):
            return
        member_id: MemberId = (owner.module, owner.name, name)
        verdict = prefetch.classify(
            transitive_hits(index, member_id), self._required(info)
        )
        chain = explain(index, member_id)
        label = f"{model.name}.{name}"
        rule, text = (
            (orm004.RULE, orm004.message(label, chain))
            if called
            else (orm003.RULE, orm003.message(model.name, name, chain))
        )
        self._emit(verdict, Violation(rule, text, line, col), label)

    def _check_relation_traversal(
        self,
        info: _SerializerInfo,
        model: ClassInfo,
        name: str,
        line: int,
        col: int,
    ) -> None:
        """ORM006 / ORM007 for a bare foreign-key traversal."""
        required = self._required(info)
        if required is not None:
            if name in required:
                return
            self._add(
                Violation(
                    orm007.RULE,
                    orm007.message((name,), f"relation {name}"),
                    line,
                    col,
                )
            )
            return
        self._add(Violation(orm006.RULE, orm006.message(model.name, name), line, col))

    # -------------------------------------------------------------- #
    # Declarative checks
    # -------------------------------------------------------------- #

    def _check_class_declaration(self, info: _SerializerInfo) -> None:
        """ORM008 / ORM009 on the class statement and its declaration."""
        if not self.ctx.prefetch_aware:
            return
        if info.is_prefetch_base and info.required_prefetches is None:
            self._add(
                Violation(orm008.RULE, orm008.message(info.name), info.line, info.col)
            )
        if not info.prefetch_local:
            return
        for entry, line, col in info.prefetch_entries:
            if prefetch.is_unsatisfiable(entry):
                self._add(Violation(orm009.RULE, orm009.message(entry), line, col))

    def _check_fields(self, info: _SerializerInfo) -> None:
        """ORM005 / ORM007 for members pulled in declaratively.

        ``fields = "__all__"`` and ``exclude`` both expand through
        ``model._meta``, which only knows concrete fields and relations, so a
        plain property cannot enter that way.  Declared fields carrying a
        ``source=`` still can, and are checked regardless.
        """
        if self.ctx.index is None or info.model is None:
            return
        for name, line, col in info.fields:
            if self._check_field_relation(info, name, line, col):
                continue
            if name in info.declared:
                continue
            self._check_field_member(info, name, name, line, col)
        for declared in info.declared.values():
            if declared.is_method_field or declared.is_nested:
                continue
            if declared.source is not None:
                self._check_field_member(
                    info,
                    declared.name,
                    declared.source.split(".")[0],
                    declared.source_line,
                    declared.source_col,
                )
            else:
                self._check_field_member(
                    info, declared.name, declared.name, declared.line, declared.col
                )

    def _check_field_relation(
        self, info: _SerializerInfo, name: str, line: int, col: int
    ) -> bool:
        """ORM007 for a relation serialized as a field without a declared prefetch.

        Serializing a relation -- as a nested serializer, a
        ``PrimaryKeyRelatedField``, anything -- reads it for every object, so
        ``BaseSerializer`` requires it in ``required_prefetches``.  This is
        scoped to serializers that already carry the contract: on an ordinary
        ``ModelSerializer`` there is nothing to check it against, and flagging
        every nested field would be pure noise.
        """
        ctx = self.ctx
        index = ctx.index
        model = info.model
        required = self._required(info)
        if index is None or model is None or required is None:
            return False
        relations = class_all_relations(index, model, fallback=ctx.model_resolution)
        if name not in relations:
            return False
        if name not in required:
            self._add(
                Violation(
                    orm007.RULE,
                    orm007.message((name,), f'field "{name}"'),
                    line,
                    col,
                )
            )
        return True

    def _check_field_member(
        self,
        info: _SerializerInfo,
        field_name: str,
        member_name: str,
        line: int,
        col: int,
    ) -> None:
        """Report a single ``fields``/``source=`` entry that reaches the database."""
        ctx = self.ctx
        index = ctx.index
        model = info.model
        if index is None or model is None:
            return
        found = class_member(index, model, member_name, fallback=ctx.model_resolution)
        if found is None:
            return
        owner, member = found
        if not member.queries:
            return
        member_id: MemberId = (owner.module, owner.name, member_name)
        verdict = prefetch.classify(
            transitive_hits(index, member_id), self._required(info)
        )
        self._emit(
            verdict,
            Violation(
                orm005.RULE,
                orm005.message(
                    field_name, model.name, member_name, explain(index, member_id)
                ),
                line,
                col,
            ),
            f'field "{field_name}"',
        )

    # -------------------------------------------------------------- #

    def _emit(
        self, verdict: prefetch.Verdict, violation: Violation, label: str
    ) -> None:
        """Record the verdict, preferring the actionable prefetch advice.

        When a missing prefetch is all that stands between the access and
        being free, ORM007 replaces the generic finding: naming the entry to
        add is more useful than restating that a query happens.
        """
        if verdict.silent:
            return
        if verdict.kind == prefetch.PREFETCH:
            self._add(
                Violation(
                    orm007.RULE,
                    orm007.message(verdict.relations, label),
                    violation.line,
                    violation.col,
                )
            )
            return
        self._add(violation)

    def _add(self, violation: Violation) -> None:
        if self.ctx.enabled(violation.rule):
            self.violations.append(violation)


# ------------------------------------------------------------------ #
# Entry points
# ------------------------------------------------------------------ #


def _dedupe(violations: list[Violation]) -> list[Violation]:
    """Keep one violation per position, preferring the lowest rule code."""
    best: dict[tuple[int, int], Violation] = {}
    for violation in violations:
        key = (violation.line, violation.col)
        current = best.get(key)
        if current is None or violation.rule < current.rule:
            best[key] = violation
    return sorted(best.values(), key=lambda v: (v.line, v.col, v.rule))


def check_source(
    source_code: str,
    context: CheckContext | None = None,
) -> list[Violation]:
    """Parse *source_code* and return ORM violations, respecting ``# noqa`` comments."""
    try:
        module = cst.parse_module(source_code)
    except cst.ParserSyntaxError:
        return []

    ctx = context or CheckContext()
    wrapper = MetadataWrapper(module)

    collector = _InfoCollector(ctx)
    wrapper.visit(collector)

    visitor = _SerializerORMVisitor(ctx, collector.infos)
    wrapper.visit(visitor)

    source_lines = source_code.splitlines()
    return [v for v in _dedupe(visitor.violations) if not _is_noqa(source_lines, v)]


def check_file(path: Path, context: CheckContext | None = None) -> list[Violation]:
    """Read *path* and return all ORM violations."""
    return check_source(path.read_text(encoding="utf-8"), context)


def _is_noqa(source_lines: list[str], violation: Violation) -> bool:
    """Return True if the violation's source line carries a ``# noqa`` suppression."""
    if violation.line < 1 or violation.line > len(source_lines):
        return False
    line = source_lines[violation.line - 1]
    if "# noqa" not in line:
        return False
    # Bare noqa (no codes) suppresses everything on this line.
    if "# noqa:" not in line:
        return True
    # Specific rule codes, e.g. ``ORM001`` or ``ORM001,ORM002`` after "# noqa:"
    # Strip any trailing inline comment like ``# explanation``
    noqa_part = line[line.index("# noqa:") + 7 :].split("#")[0].strip()
    codes = {c.strip() for c in noqa_part.split(",")}
    return violation.rule in codes

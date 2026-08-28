"""Dataclasses describing the project index.

The index is a coarse, purely syntactic map of every class, member and import
in the project.  It exists to answer one question the single-file checker
cannot: *does touching this name run a query?*
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

#: Identifies one member: module dotted path, owning class name (empty for a
#: module-level function), then the member's own name.
MemberId = tuple[str, str, str]

# Member kinds.  Properties are called for you on attribute access, which is
# what makes them dangerous in a serializer; plain attributes exist only so
# that a subclass assignment can shadow a querying base member.
PROPERTY_KINDS = frozenset({"property", "cached_property"})


@dataclass(frozen=True, slots=True)
class QueryHit:
    """A single database query found directly in a member body."""

    line: int
    relation_root: str | None
    """The ``self.<relation>`` this query hangs off, if any.

    ``None`` for anything a ``required_prefetches`` declaration could never
    cover, such as ``SomeModel.objects.filter(...)``.
    """

    method: str | None
    prefetch_safe: bool
    """Whether this access reads Django's prefetch cache instead of re-querying."""


@dataclass(frozen=True, slots=True)
class MemberRef:
    """An unresolved outgoing reference from one member body to something else."""

    path: tuple[str, ...]
    is_call: bool
    line: int


@dataclass(frozen=True, slots=True)
class ImportedName:
    """One name brought into a module's namespace by an import statement."""

    module: str | None
    name: str | None
    level: int


@dataclass(slots=True)
class Member:
    """A method, property, function or class-level attribute."""

    name: str
    kind: str
    line: int
    col: int
    hits: tuple[QueryHit, ...] = ()
    refs: tuple[MemberRef, ...] = ()
    forced: str | None = None
    queries: bool = False
    via: MemberId | None = None

    @property
    def is_property(self) -> bool:
        """Whether merely *accessing* this member runs its body."""
        return self.kind in PROPERTY_KINDS


@dataclass(slots=True)
class ClassInfo:
    """A class definition and everything the index knows about it."""

    name: str
    module: str
    line: int
    col: int
    bases: tuple[tuple[str, ...], ...] = ()
    members: dict[str, Member] = field(default_factory=dict)
    relations: dict[str, str] = field(default_factory=dict)
    many_relations: dict[str, str] = field(default_factory=dict)
    required_prefetches: tuple[str, ...] | None = None
    prefetch_entries: tuple[tuple[str, int, int], ...] = ()
    prefetch_line: int | None = None

    @property
    def qualname(self) -> str:
        """Dotted ``module.ClassName``."""
        return f"{self.module}.{self.name}"


@dataclass(slots=True)
class ModuleInfo:
    """One scanned source file."""

    dotted: str
    path: str
    is_package: bool = False
    imports: dict[str, ImportedName] = field(default_factory=dict)
    classes: dict[str, ClassInfo] = field(default_factory=dict)
    functions: dict[str, Member] = field(default_factory=dict)
    mtime_ns: int = 0
    size: int = 0


@dataclass
class ProjectIndex:
    """Every scanned module, plus the resolved call graph over their members."""

    root: Path
    modules: dict[str, ModuleInfo] = field(default_factory=dict)
    by_path: dict[str, str] = field(default_factory=dict)
    by_class_name: dict[str, list[str]] = field(default_factory=dict)
    edges: dict[MemberId, frozenset[MemberId]] = field(default_factory=dict)
    _hit_cache: dict[MemberId, tuple[QueryHit, ...]] = field(default_factory=dict)

    def add(self, module: ModuleInfo) -> None:
        """Register (or replace) a scanned module."""
        self.modules[module.dotted] = module
        self.by_path[module.path] = module.dotted

    def reindex_names(self) -> None:
        """Rebuild the bare-class-name lookup used by the ``unique`` fallback."""
        self.by_class_name = {}
        for module in self.modules.values():
            for name in module.classes:
                self.by_class_name.setdefault(name, []).append(module.dotted)

    def member(self, module: str, cls: str, name: str) -> Member | None:
        """Look up a member by its id components, without walking bases."""
        mod = self.modules.get(module)
        if mod is None:
            return None
        if not cls:
            return mod.functions.get(name)
        info = mod.classes.get(cls)
        return None if info is None else info.members.get(name)

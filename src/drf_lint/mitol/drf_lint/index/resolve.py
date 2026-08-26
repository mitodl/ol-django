"""Resolve names, imports and inheritance across the indexed modules.

Everything here is lexical: it follows ``import`` statements and base-class
expressions as written.  Nothing is imported or executed, so a project that
cannot be booted (missing settings, missing services) still resolves fine.
"""

from __future__ import annotations

from collections.abc import Iterator

from mitol.drf_lint.index.model import (
    ClassInfo,
    ImportedName,
    Member,
    MemberId,
    MemberRef,
    ModuleInfo,
    ProjectIndex,
)

#: Fallback policies for a ``Meta.model`` that imports cannot resolve.
FALLBACK_MODES = ("never", "unique", "any")

_MAX_MODULE_PREFIX = 2


def absolute_module(
    current: str, imported: ImportedName, *, is_package: bool
) -> str | None:
    """Turn a possibly-relative import into an absolute dotted module name."""
    if imported.level == 0:
        return imported.module
    parts = current.split(".")
    if is_package:
        parts = [*parts, ""]
    if imported.level > len(parts):
        return None
    base = parts[: len(parts) - imported.level]
    if imported.module:
        base = [*base, *imported.module.split(".")]
    return ".".join(p for p in base if p) or None


def _import_module_target(index: ProjectIndex, module: str, alias: str) -> str | None:
    """Resolve a local alias that names a *module* to its dotted path."""
    info = index.modules.get(module)
    if info is None:
        return None
    imported = info.imports.get(alias)
    if imported is None:
        return None
    absolute = absolute_module(module, imported, is_package=info.is_package)
    if absolute is None:
        return None
    if imported.name is None:
        # `import a.b as c` / `import a`
        return absolute
    # `from a import b` - b may itself be a module.
    candidate = f"{absolute}.{imported.name}"
    return candidate if candidate in index.modules else None


def resolve_base_qualname(
    index: ProjectIndex, module: str, path: tuple[str, ...]
) -> str | None:
    """Dotted qualname for a base-class expression, even if it isn't indexed.

    This is what lets the checker recognise ``mitol.common.serializers``'s
    ``BaseSerializer`` without indexing site-packages: the import statement
    already spells out where the name came from.
    """
    info = index.modules.get(module)
    if info is None or not path:
        return None
    head, rest = path[0], path[1:]
    imported = info.imports.get(head)
    if imported is None:
        return f"{module}.{'.'.join(path)}" if head in info.classes else None
    absolute = absolute_module(module, imported, is_package=info.is_package)
    if absolute is None:
        return None
    segments = [absolute]
    if imported.name is not None:
        segments.append(imported.name)
    segments.extend(rest)
    return ".".join(segments)


def lookup_class(
    index: ProjectIndex,
    module: str,
    path: tuple[str, ...],
    *,
    fallback: str = "unique",
) -> ClassInfo | None:
    """Resolve a dotted class reference written inside *module*."""
    if not path:
        return None
    info = index.modules.get(module)
    name = path[-1]

    if info is not None:
        found = _lookup_exact(index, info, module, path)
        if found is not None:
            return found

    return _lookup_fallback(index, name, fallback)


def _lookup_exact(
    index: ProjectIndex, info: ModuleInfo, module: str, path: tuple[str, ...]
) -> ClassInfo | None:
    """Resolve strictly through this module's namespace and imports."""
    head, name = path[0], path[-1]

    if len(path) == 1:
        local = info.classes.get(name)
        if local is not None:
            return local
        imported = info.imports.get(name)
        if imported is not None and imported.name is not None:
            absolute = absolute_module(module, imported, is_package=info.is_package)
            target = index.modules.get(absolute) if absolute else None
            if target is not None:
                return target.classes.get(imported.name)
        return None

    # `models.Foo`, `myapp.models.Foo`, `m.Foo`
    prefix = path[:-1]
    target_module = _import_module_target(index, module, head)
    if target_module is not None and len(prefix) > 1:
        target_module = ".".join([target_module, *prefix[1:]])
    if target_module is None and len(prefix) <= _MAX_MODULE_PREFIX:
        target_module = ".".join(prefix)
    target = index.modules.get(target_module) if target_module else None
    if target is not None:
        return target.classes.get(name)
    return None


def _lookup_fallback(index: ProjectIndex, name: str, fallback: str) -> ClassInfo | None:
    """Bare-name lookup, used only when exact resolution failed."""
    if fallback == "never":
        return None
    candidates = index.by_class_name.get(name, [])
    if not candidates:
        return None
    if len(candidates) > 1 and fallback != "any":
        return None
    return index.modules[candidates[0]].classes.get(name)


def iter_mro(
    index: ProjectIndex, cls: ClassInfo, *, fallback: str = "unique"
) -> Iterator[ClassInfo]:
    """Yield *cls* then each indexed ancestor, depth-first, left to right."""
    seen: set[str] = set()
    stack = [cls]
    while stack:
        current = stack.pop(0)
        if current.qualname in seen:
            continue
        seen.add(current.qualname)
        yield current
        resolved = [
            base
            for base in (
                lookup_class(index, current.module, path, fallback=fallback)
                for path in current.bases
            )
            if base is not None
        ]
        stack = [*resolved, *stack]


def class_member(
    index: ProjectIndex, cls: ClassInfo, name: str, *, fallback: str = "unique"
) -> tuple[ClassInfo, Member] | None:
    """Find *name* on *cls* or its ancestors; the first match wins.

    Returning the owning class as well is what lets a caller build the
    member's id, and what makes a subclass attribute correctly shadow a
    querying base property.
    """
    for ancestor in iter_mro(index, cls, fallback=fallback):
        member = ancestor.members.get(name)
        if member is not None:
            return ancestor, member
    return None


def class_relations(
    index: ProjectIndex, cls: ClassInfo, *, fallback: str = "unique"
) -> dict[str, str]:
    """Return relation fields from *cls* and its ancestors, merged."""
    merged: dict[str, str] = {}
    for ancestor in reversed(list(iter_mro(index, cls, fallback=fallback))):
        merged.update(ancestor.relations)
    return merged


def class_all_relations(
    index: ProjectIndex, cls: ClassInfo, *, fallback: str = "unique"
) -> dict[str, str]:
    """Return every relation on *cls*, single- and multi-valued, incl. inherited."""
    merged: dict[str, str] = {}
    for ancestor in reversed(list(iter_mro(index, cls, fallback=fallback))):
        merged.update(ancestor.relations)
        merged.update(ancestor.many_relations)
    return merged


def class_required_prefetches(
    index: ProjectIndex, cls: ClassInfo, *, fallback: str = "unique"
) -> tuple[ClassInfo, tuple[str, ...]] | None:
    """Nearest ``required_prefetches`` declaration on *cls* or an ancestor."""
    for ancestor in iter_mro(index, cls, fallback=fallback):
        if ancestor.required_prefetches is not None:
            return ancestor, ancestor.required_prefetches
    return None


def inherits_from(
    index: ProjectIndex,
    cls: ClassInfo,
    qualnames: frozenset[str],
    *,
    fallback: str = "unique",
) -> bool:
    """Whether *cls* derives from any of *qualnames*, indexed or not."""
    for ancestor in iter_mro(index, cls, fallback=fallback):
        if ancestor.qualname in qualnames:
            return True
        for path in ancestor.bases:
            resolved = resolve_base_qualname(index, ancestor.module, path)
            if resolved in qualnames:
                return True
    return False


def resolve_ref(
    index: ProjectIndex,
    module: str,
    cls_name: str,
    ref: MemberRef,
    *,
    fallback: str = "unique",
) -> MemberId | None:
    """Resolve one outgoing reference to the member id it points at."""
    info = index.modules.get(module)
    if info is None:
        return None
    path = ref.path

    if path[0] == "self":
        return _resolve_self(index, info, cls_name, path, fallback=fallback)
    if len(path) == 1:
        return _resolve_function(index, info, module, path[0])
    return _resolve_qualified(index, module, path, fallback=fallback)


def _resolve_self(
    index: ProjectIndex,
    info: ModuleInfo,
    cls_name: str,
    path: tuple[str, ...],
    *,
    fallback: str,
) -> MemberId | None:
    """Resolve ``self.<member>`` against the enclosing class and its bases."""
    if len(path) != _MAX_MODULE_PREFIX or not cls_name:
        return None
    owner = info.classes.get(cls_name)
    if owner is None:
        return None
    found = class_member(index, owner, path[1], fallback=fallback)
    return None if found is None else (found[0].module, found[0].name, path[1])


def _resolve_qualified(
    index: ProjectIndex, module: str, path: tuple[str, ...], *, fallback: str
) -> MemberId | None:
    """Resolve ``Klass.member(...)`` or ``module_alias.function(...)``."""
    owner_cls = lookup_class(index, module, path[:-1], fallback=fallback)
    if owner_cls is not None:
        found = class_member(index, owner_cls, path[-1], fallback=fallback)
        if found is not None:
            return (found[0].module, found[0].name, path[-1])
    target_module = _import_module_target(index, module, path[0])
    if target_module is not None and len(path) > _MAX_MODULE_PREFIX:
        target_module = ".".join([target_module, *path[1:-1]])
    target = index.modules.get(target_module) if target_module else None
    if target is not None and path[-1] in target.functions:
        return (target.dotted, "", path[-1])
    return None


def _resolve_function(
    index: ProjectIndex, info: ModuleInfo, module: str, name: str
) -> MemberId | None:
    """Resolve a bare ``name(...)`` call to a module-level function."""
    if name in info.functions:
        return (module, "", name)
    imported = info.imports.get(name)
    if imported is None or imported.name is None:
        return None
    absolute = absolute_module(module, imported, is_package=info.is_package)
    target = index.modules.get(absolute) if absolute else None
    if target is None:
        return None
    if imported.name in target.functions:
        return (target.dotted, "", imported.name)
    return None

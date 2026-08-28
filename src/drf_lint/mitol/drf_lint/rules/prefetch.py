"""Reason about ``required_prefetches`` declarations.

``mitol.common.serializers.BaseSerializer`` asks subclasses to declare which
relations the caller must have prefetched, and ``to_representation`` enforces
it at runtime.  That declaration is the one trustworthy answer to the question
a static checker otherwise cannot answer -- *is this relation already
fetched?* -- so it is used here both to silence provable non-issues and to
tell a developer exactly which entry to add.
"""

from __future__ import annotations

from dataclasses import dataclass

from mitol.drf_lint.index.model import QueryHit

#: Serializer base classes whose subclasses carry the contract.
DEFAULT_PREFETCH_BASES: frozenset[str] = frozenset(
    {"mitol.common.serializers.BaseSerializer"}
)

#: Django's ``prefetch_related`` path separator.
PREFETCH_SEPARATOR = "__"

SILENT = "silent"
FLAG = "flag"
PREFETCH = "prefetch"


@dataclass(frozen=True)
class Verdict:
    """What to do about a set of queries reached from one serializer access."""

    kind: str
    relations: tuple[str, ...] = ()

    @property
    def silent(self) -> bool:
        """Whether the access is provably free."""
        return self.kind == SILENT


def is_covered(required: tuple[str, ...] | None, hit: QueryHit) -> bool:
    """Whether a declared prefetch actually saves *hit* from hitting the database.

    Both halves matter.  A query that isn't rooted at a relation -- say
    ``SomeModel.objects.filter(...)`` inside a property -- can never be covered
    by any prefetch.  And a relation that *is* prefetched only helps for
    accesses that read the cache: ``.filter()`` and friends build a fresh
    queryset, and ``.count()``/``.exists()``/``.first()`` add their own SQL, so
    they re-query no matter what the caller prefetched.
    """
    if required is None or hit.relation_root is None:
        return False
    return hit.relation_root in required and hit.prefetch_safe


def classify(hits: tuple[QueryHit, ...], required: tuple[str, ...] | None) -> Verdict:
    """Decide whether a set of reached queries is silent, fixable, or a problem."""
    if not hits:
        return Verdict(SILENT)
    uncovered = [hit for hit in hits if not is_covered(required, hit)]
    if not uncovered:
        return Verdict(SILENT)
    if required is not None and all(
        hit.prefetch_safe and hit.relation_root for hit in uncovered
    ):
        relations = tuple(sorted({hit.relation_root for hit in uncovered}))
        return Verdict(PREFETCH, relations)
    return Verdict(FLAG)


def is_unsatisfiable(entry: str) -> bool:
    """Whether ``is_prefetched()`` can never satisfy this ``required_prefetches`` entry.

    ``is_prefetched`` looks the name up with ``Model._meta.get_field()`` and in
    ``_prefetched_objects_cache`` / ``instance.__dict__``.  A traversal path
    such as ``"author__books"`` is not a field name and is never a key in
    either cache, so it raises on every single serialization.

    A plain name that is not a model field is deliberately *not* reported:
    django-prefetch's ``prefetch()`` populates arbitrary names in
    ``instance.__dict__``, which ``is_prefetched`` honours on purpose.
    """
    return PREFETCH_SEPARATOR in entry

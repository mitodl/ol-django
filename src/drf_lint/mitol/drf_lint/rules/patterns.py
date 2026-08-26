"""Shared query-detection vocabulary.

Two very different parsers need to agree on what "performs a query" means: the
LibCST checker that walks the files under check, and the :mod:`ast`-based
project indexer that scans everything else.  Keeping the vocabulary and the
predicates here is what stops the two from drifting apart.

Chains are flattened attribute paths.  ``instance.children.all()`` flattens to
``("instance", "children", "all")``.  A segment that isn't a plain name -- a
call, a subscript -- flattens to :data:`UNKNOWN` rather than aborting, so
``get_obj().children.all()`` still reads as related manager traversal while
``User.objects.filter(x).first()`` does not (its receiver collapses to a
single unknown segment, leaving the chain too short).
"""

from __future__ import annotations

import libcst as cst

# Django ORM-specific queryset methods.  Intentionally excludes .get() and
# .values(), which collide with dict/list builtins too often to be safe in a
# serializer body.
QUERYSET_METHODS: frozenset[str] = frozenset(
    {
        "filter",
        "all",
        "exclude",
        "annotate",
        "order_by",
        "select_related",
        "prefetch_related",
        "values_list",
        "exists",
        "first",
        "last",
    }
)

# Attributes that expose a model manager.
MANAGER_ATTRS: frozenset[str] = frozenset(
    {"objects", "_default_manager", "_base_manager"}
)

# Field classes whose attribute access triggers a lazy fetch when the relation
# was not select_related()'d.
RELATION_FIELD_TYPES: frozenset[str] = frozenset(
    {"ForeignKey", "OneToOneField", "ParentalKey"}
)

# Multi-valued relations.  Touching one of these returns a manager without
# querying, so they are deliberately kept out of RELATION_FIELD_TYPES -- but
# serializing one still needs a prefetch, so they count for that check.
MANY_RELATION_FIELD_TYPES: frozenset[str] = frozenset(
    {"ManyToManyField", "ParentalManyToManyField"}
)

# Query methods that are only safe to look for inside a *model* body, where a
# `self.<relation>.<method>()` chain is unambiguous.  Callers must additionally
# require a >=3 segment chain and zero arguments, which is what keeps
# `self.data.get("k")` and `some_list.count(x)` out.
MODEL_QUERY_METHODS_NOARG: frozenset[str] = frozenset(
    {"count", "exists", "aggregate", "values", "get"}
)

# Methods that read Django's prefetch cache instead of issuing a fresh query.
# Everything else in QUERYSET_METHODS re-queries even on a prefetched manager:
# .filter()/.exclude()/.order_by()/.annotate() build a new queryset, and
# .count()/.exists()/.first()/.last() add their own SQL.
PREFETCH_SAFE_METHODS: frozenset[str] = frozenset({"all"})

# Raw SQL escape hatches.
RAW_SQL_METHODS: frozenset[str] = frozenset({"raw", "execute"})

# Placeholder for a chain segment that is not a plain name.
UNKNOWN = "*"

_MIN_RELATED_CHAIN = 3


def chain_has_manager(chain: tuple[str, ...]) -> bool:
    """Return True if *chain* traverses a model manager.

    The first segment is skipped: it is the receiver, so a local variable that
    merely happens to be named ``objects`` is not a manager access.
    """
    return any(segment in MANAGER_ATTRS for segment in chain[1:])


def is_queryset_method_call(chain: tuple[str, ...]) -> bool:
    """Return True if *chain* is a queryset method on a related manager.

    At least three segments are required (``instance.children.all``) so that a
    bare local-variable queryset call (``qs.all()``) is not mistaken for
    related manager traversal.
    """
    return len(chain) >= _MIN_RELATED_CHAIN and chain[-1] in QUERYSET_METHODS


def relation_root(chain: tuple[str, ...]) -> str | None:
    """Return the relation name a ``self.<relation>.…`` chain is rooted at.

    Returns None for chains rooted at anything other than ``self``, which are
    the chains a ``required_prefetches`` declaration can never cover.
    """
    if len(chain) >= _MIN_RELATED_CHAIN and chain[0] == "self":
        return chain[1]
    return None


def flatten_cst_chain(expr: cst.BaseExpression) -> tuple[str, ...]:
    """Flatten a LibCST attribute path into a tuple of segment names."""
    segments: list[str] = []
    node = expr
    while isinstance(node, cst.Attribute):
        segments.append(node.attr.value if isinstance(node.attr, cst.Name) else UNKNOWN)
        node = node.value
    segments.append(node.value if isinstance(node, cst.Name) else UNKNOWN)
    segments.reverse()
    return tuple(segments)

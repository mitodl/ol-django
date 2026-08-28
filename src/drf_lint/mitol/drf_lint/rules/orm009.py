"""ORM009: a ``required_prefetches`` entry that can never be satisfied.

``is_prefetched()`` resolves a name through ``Model._meta.get_field()``,
``_prefetched_objects_cache`` and ``instance.__dict__``.  A traversal path such
as ``"author__books"`` matches none of those, so the check fails on every
serialization no matter what the caller prefetched.

A plain name that is not a model field is *not* reported: django-prefetch's
``prefetch()`` populates arbitrary names in ``instance.__dict__``, and
``is_prefetched`` honours that on purpose.
"""

from __future__ import annotations

RULE = "ORM009"


def message(entry: str) -> str:
    """Explain why the entry can never be satisfied."""
    return (
        f'required_prefetches entry "{entry}" can never be satisfied - '
        f"is_prefetched() cannot resolve a traversal path, so this raises "
        f"RequiredPrefetchMissingError on every serialization"
    )

"""ORM006: traversing an unfetched foreign key.

``instance.author.name`` fetches the related row unless the caller
``select_related``'d it, which is a query per serialized object.  On a
``BaseSerializer`` subclass this rule defers to ORM007, which can name the
``required_prefetches`` entry that would fix it.
"""

from __future__ import annotations

RULE = "ORM006"


def message(model: str, relation: str) -> str:
    """Describe the relation being traversed."""
    return (
        f"traversing {model}.{relation} in a serializer method fetches the "
        f"related object unless it was select_related/prefetch_related'd - "
        f"risk of N+1"
    )

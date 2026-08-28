"""ORM007: a relation used by the serializer but missing from ``required_prefetches``.

``BaseSerializer.to_representation`` already raises ``RequiredPrefetchMissingError``
for this under ``DEBUG`` and pytest -- but only once something actually
serializes that object.  Checking it statically moves the failure to commit
time, and the message names the exact string to add.
"""

from __future__ import annotations

RULE = "ORM007"


def message(relations: tuple[str, ...], detail: str) -> str:
    """Name the entries that should be added to ``required_prefetches``."""
    quoted = ", ".join(f'"{relation}"' for relation in relations)
    return (
        f"{detail} requires {quoted} to be prefetched - add to "
        f"required_prefetches (and prefetch_related it in the queryset)"
    )

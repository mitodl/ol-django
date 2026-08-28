"""ORM008: a ``BaseSerializer`` subclass that never declares ``required_prefetches``.

``BaseSerializer.__init__`` raises ``RequiredPrefetchesNotDefinedError``, but
only when the class is instantiated, so a serializer no test exercises ships
broken.  An abstract intermediate base that legitimately leaves the attribute
to its subclasses should carry ``# noqa: ORM008``.
"""

from __future__ import annotations

RULE = "ORM008"


def message(name: str) -> str:
    """Name the serializer missing its declaration."""
    return (
        f"{name} subclasses BaseSerializer but does not define "
        f"required_prefetches - it will raise RequiredPrefetchesNotDefinedError "
        f"when instantiated"
    )

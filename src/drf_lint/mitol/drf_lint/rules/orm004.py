"""ORM004: calling a function or method that performs a query.

Covers the indirection the single-file rules cannot see: a helper in another
module, a method on the model, or a method on the serializer itself, any of
which may reach the database several calls deep.
"""

from __future__ import annotations

RULE = "ORM004"


def message(target: str, chain: str) -> str:
    """Describe the callee and the chain by which it reaches the database."""
    detail = f" (via {chain})" if chain and chain != target else ""
    return (
        f"{target} called in a serializer method performs a database query"
        f"{detail} - risk of N+1"
    )

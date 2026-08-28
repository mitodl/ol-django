"""ORM005: a serializer field backed by a query-performing model member.

DRF resolves a name in ``fields`` against the model, and a plain Python
property named there becomes a ``ReadOnlyField`` whose value is computed per
object.  Nothing at the call site hints that a query is involved::

    class Meta:
        model = Course
        fields = ["id", "run_count"]    # ORM005 on "run_count"

Note that ``fields = "__all__"`` cannot pull a property in: DRF expands it via
``model._meta``, which only knows concrete fields and relations.  A property
becomes a field only when it is named explicitly.
"""

from __future__ import annotations

RULE = "ORM005"


def message(field: str, model: str, name: str, chain: str) -> str:
    """Describe the field, the member it maps to, and the query behind it."""
    detail = f" (via {chain})" if chain and chain != f"{model}.{name}" else ""
    return (
        f'field "{field}" maps to {model}.{name}, which performs a database '
        f"query{detail} - risk of N+1"
    )

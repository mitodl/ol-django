"""ORM002: Related manager queryset call inside serializer methods.

Detects patterns like::

    instance.children.order_by("position").first()
    instance.resource_prices.all()
    self.some_attr.filter(published=True)

These access a Django related manager and execute a queryset method, issuing a
database query for every serialized object instance (N+1).
"""

from __future__ import annotations

import libcst as cst
from mitol.drf_lint.rules.base import Violation

RULE = "ORM002"
MESSAGE = (
    "Queryset method call on related manager inside serializer method — risk of N+1"
)

# Queryset methods that are Django ORM-specific (not common Python builtins).
# Intentionally excludes .get() and .values() to reduce false positives.
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


def check(node: cst.Call, line: int, col: int) -> Violation | None:
    """Return a Violation if *node* is a related-manager queryset call, else None."""
    if _is_related_manager_call(node):
        return Violation(rule=RULE, message=MESSAGE, line=line, col=col)
    return None


def _is_related_manager_call(node: cst.Call) -> bool:
    """Check if the call is a queryset method on a multi-level attribute chain.

    Requires at least two levels of attribute access (e.g. ``instance.children.all()``)
    to distinguish related manager traversal from a bare local-variable queryset call.
    """
    func = node.func
    return (
        isinstance(func, cst.Attribute)
        and isinstance(func.attr, cst.Name)
        and func.attr.value in QUERYSET_METHODS
        and isinstance(func.value, cst.Attribute)
    )

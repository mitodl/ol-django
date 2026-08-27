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
from mitol.drf_lint.rules import patterns
from mitol.drf_lint.rules.base import Violation

RULE = "ORM002"
MESSAGE = (
    "Queryset method call on related manager inside serializer method - risk of N+1"
)

# Retained for backwards compatibility with importers of this name.
QUERYSET_METHODS = patterns.QUERYSET_METHODS


def check(node: cst.Call, line: int, col: int) -> Violation | None:
    """Return a Violation if *node* is a related-manager queryset call, else None."""
    chain = patterns.flatten_cst_chain(node.func)
    if patterns.is_queryset_method_call(chain, has_args=bool(node.args)):
        return Violation(rule=RULE, message=MESSAGE, line=line, col=col)
    return None


def prefetched_message(relation: str, method: str) -> str:
    """Message for a relation that *is* prefetched but is accessed unsafely.

    ``.all()`` reads Django's prefetch cache, but ``.filter()`` and friends
    build a fresh queryset and hit the database again, so declaring the
    relation in ``required_prefetches`` does not make the access free.
    """
    return (
        f'relation "{relation}" is prefetched, but .{method}() re-queries the '
        f"database - use Prefetch(queryset=...) or filter in Python"
    )

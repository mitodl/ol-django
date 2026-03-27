"""ORM001: Django manager access inside serializer methods.

Detects patterns like::

    User.objects.filter(username=instance.username).first()
    MyModel.objects.get(pk=instance.pk)

These execute a database query for every serialized object instance, causing
N+1 query bugs.
"""

from __future__ import annotations

import libcst as cst

from mitol.drf_lint.rules.base import Violation

RULE = "ORM001"
MESSAGE = "Django ORM manager access (.objects) inside serializer method — risk of N+1"


def check(node: cst.Call, line: int, col: int) -> Violation | None:
    """Return a Violation if *node* is a Django ORM manager call, else None."""
    if isinstance(node.func, cst.Attribute) and _chain_has_objects(node.func):
        return Violation(rule=RULE, message=MESSAGE, line=line, col=col)
    return None


def _chain_has_objects(expr: cst.BaseExpression) -> bool:
    """Return True if the attribute chain contains a ``.objects`` access."""
    if isinstance(expr, cst.Attribute):
        if isinstance(expr.attr, cst.Name) and expr.attr.value == "objects":
            return True
        return _chain_has_objects(expr.value)
    return False

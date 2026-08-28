"""ORM001: Django manager access inside serializer methods.

Detects patterns like::

    User.objects.filter(username=instance.username).first()
    MyModel.objects.get(pk=instance.pk)

These execute a database query for every serialized object instance, causing
N+1 query bugs.
"""

from __future__ import annotations

import libcst as cst
from mitol.drf_lint.rules import patterns
from mitol.drf_lint.rules.base import Violation

RULE = "ORM001"
MESSAGE = "Django ORM manager access (.objects) inside serializer method - risk of N+1"


def check(node: cst.Call, line: int, col: int) -> Violation | None:
    """Return a Violation if *node* is a Django ORM manager call, else None."""
    chain = patterns.flatten_cst_chain(node.func)
    if patterns.chain_has_manager(chain):
        return Violation(rule=RULE, message=MESSAGE, line=line, col=col)
    return None

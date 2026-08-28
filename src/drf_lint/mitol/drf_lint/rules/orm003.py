"""ORM003: accessing a model property that performs a query.

A ``@property`` looks free at the call site but runs its body on attribute
access, so a serializer that touches one is issuing a query per serialized
object::

    class Course(models.Model):
        @property
        def run_count(self):
            return self.runs.count()

    def get_summary(self, instance):
        return f"{instance.run_count} runs"   # ORM003
"""

from __future__ import annotations

RULE = "ORM003"


def message(model: str, name: str, chain: str) -> str:
    """Describe which property was touched and how it reaches the database."""
    detail = f" (via {chain})" if chain and chain != f"{model}.{name}" else ""
    return (
        f"property {model}.{name} accessed in a serializer method performs a "
        f"database query{detail} - risk of N+1"
    )

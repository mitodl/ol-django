"""A second model sharing a member name, to prove strict resolution works."""

from django.db import models  # type: ignore[import-untyped]


class Unrelated(models.Model):
    """Has a querying `run_count`, but no serializer points at it."""

    @property
    def run_count(self):
        """Same name as Course.run_count, different class."""
        return self.somethings.count()

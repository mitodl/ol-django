"""Fixture models: the query lives here, the serializer only touches it."""

from functools import cached_property

from django.db import models  # type: ignore[import-untyped]
from myapp.utils import compute_stats


class AbstractTimestamped(models.Model):
    """Abstract base contributing a query-performing property."""

    class Meta:
        abstract = True

    @property
    def revision_count(self):
        """Inherited property that queries - should be flagged on subclasses."""
        return self.revisions.count()


class Author(models.Model):
    """Plain related model."""

    name = models.CharField(max_length=255)


class Course(AbstractTimestamped):
    """The model under test."""

    author = models.ForeignKey(Author, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)

    @property
    def run_count(self):
        """Queries with .count(), which re-queries even when prefetched."""
        return self.runs.count()

    @property
    def run_list(self):
        """Queries with .all(), which reads the prefetch cache."""
        return self.runs.all()

    @property
    def plain_name(self):
        """No query at all."""
        return self.name.upper()

    @property
    def author_name(self):
        """Traverses a foreign key."""
        return self.author.name

    @property
    def summary(self):
        """Reaches a query two calls away."""
        return self.get_price()

    @cached_property
    def cached_runs(self):
        """Caching is per-instance, so a list response still runs it N times."""
        return self.runs.all()

    def get_price(self):
        """Calls a module-level helper that queries."""
        return compute_stats(self)

    def cheap(self):
        """No query."""
        return 42

    @property
    def loop_a(self):
        """Mutually recursive with loop_b; must not hang or be flagged."""
        return self.loop_b

    @property
    def loop_b(self):
        """Mutually recursive with loop_a."""
        return self.loop_a

    @property
    def marked_clean(self):  # drf-lint: no-query
        """Marked clean by hand; the marker also cuts propagation to callers."""
        return self.runs.all()

    @property
    def calls_marked_clean(self):
        """Calls a hand-marked member, so it stays clean too."""
        return self.marked_clean


class Track(Course):
    """Overrides a querying property with a clean one."""

    @property
    def run_count(self):
        """Shadowing override - must not be flagged."""
        return 0

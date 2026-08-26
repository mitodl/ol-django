"""Fixture serializers exercising the required_prefetches contract."""

from mitol.common.serializers import BaseSerializer  # type: ignore[import-untyped]
from myapp.models import Course


class UndeclaredSerializer(BaseSerializer):
    """Declares no required_prefetches at all - ORM008."""

    class Meta:
        model = Course
        fields = ["id"]


class MissingPrefetchSerializer(BaseSerializer):
    """Uses relations it never declares - ORM007."""

    required_prefetches = []

    class Meta:
        model = Course
        fields = ["id", "run_list"]

    def get_things(self, instance):
        """Cache-safe access to an undeclared relation."""
        return list(instance.runs.all())


class UnsatisfiableSerializer(BaseSerializer):
    """Declares a traversal path is_prefetched() can never resolve - ORM009."""

    required_prefetches = ["author__books"]

    class Meta:
        model = Course
        fields = ["id"]


class ReQueryingSerializer(BaseSerializer):
    """Declares the relation, but filters it, which re-queries anyway - ORM002."""

    required_prefetches = ["runs"]

    class Meta:
        model = Course
        fields = ["id"]

    def get_published(self, instance):
        """.filter() builds a new queryset regardless of the prefetch."""
        return instance.runs.filter(published=True)

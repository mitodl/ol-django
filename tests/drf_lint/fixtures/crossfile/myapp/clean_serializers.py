"""Fixture serializers that must produce no violations at all."""

from mitol.common.serializers import BaseSerializer  # type: ignore[import-untyped]
from myapp.models import Course, Track
from myapp.utils import pure_helper
from rest_framework import serializers  # type: ignore[import-untyped]


class CleanSerializer(serializers.ModelSerializer):
    """Touches only non-querying members."""

    class Meta:
        model = Course
        fields = ["id", "plain_name", "marked_clean", "calls_marked_clean"]

    def get_thing(self, instance):
        """Plain attribute access and a pure helper."""
        pure_helper(instance.plain_name)
        return instance.cheap()

    def get_context_thing(self, instance):
        """Serializer context is not the model instance."""
        return self.context["request"].user.run_count

    def validate_name(self, value):
        """Write-path methods stay exempt even with the index available."""
        return value.subtopics.filter(enabled=True).first()


class AllFieldsSerializer(serializers.ModelSerializer):
    """`__all__` expands through model._meta, which cannot include a property."""

    class Meta:
        model = Course
        fields = "__all__"


class ShadowedSerializer(serializers.ModelSerializer):
    """Track overrides run_count with a clean property."""

    class Meta:
        model = Track
        fields = ["id", "run_count"]


class PrefetchedSerializer(BaseSerializer):
    """Declares every relation it reads, and reads them cache-safely."""

    required_prefetches = ["runs", "author"]

    class Meta:
        model = Course
        fields = ["id", "run_list"]

    def get_names(self, instance):
        """Both accesses are covered by the declaration above."""
        return [instance.author.name, list(instance.runs.all())]


class NoModelSerializer(serializers.Serializer):
    """No Meta.model to resolve, so nothing model-aware can fire."""

    def get_thing(self, instance):
        """Unresolvable receiver type."""
        return instance.run_count

"""Fixture serializers: every violation here comes from a cross-file rule."""

from myapp.models import Course
from myapp.utils import compute_stats, pure_helper
from rest_framework import serializers  # type: ignore[import-untyped]


class CourseSerializer(serializers.ModelSerializer):
    """Serializer whose queries all live in models.py or utils.py."""

    total = serializers.IntegerField(source="run_count")
    label = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            "id",
            "plain_name",
            "run_count",
            "summary",
            "total",
            "label",
        ]

    def get_label(self, instance):
        """Touches a query property, a query method, and a foreign key."""
        pure_helper(instance.plain_name)
        compute_stats(instance)
        return f"{instance.run_count} {instance.author.name} {instance.cheap()}"

    def get_inherited(self, obj):
        """Property inherited from an abstract base still counts."""
        return obj.revision_count

    def get_via_alias(self, instance):
        """A single-assignment alias of the instance is still the instance."""
        alias = instance
        return alias.summary

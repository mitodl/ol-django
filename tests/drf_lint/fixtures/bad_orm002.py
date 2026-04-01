"""Fixture: ORM002 violations — related manager traversal inside serializers."""

from rest_framework import serializers  # type: ignore[import-untyped]


class LearningPathSerializer(serializers.Serializer):
    """Serializer with ORM002-triggering related manager calls."""

    image = serializers.SerializerMethodField()
    prices = serializers.SerializerMethodField()
    run_count = serializers.SerializerMethodField()

    def get_image(self, instance):
        """Return image from first child — triggers ORM002 via order_by."""
        list_item = instance.children.order_by("position").first()
        if list_item and list_item.child.image:
            return list_item.child.image
        return None

    def get_prices(self, instance):
        """Return price list — triggers ORM002 via resource_prices.all()."""
        return [p.amount for p in instance.resource_prices.all()]

    def get_run_count(self, instance):
        """Return published run count — triggers ORM002 via runs.filter()."""
        return instance.runs.filter(published=True).count()

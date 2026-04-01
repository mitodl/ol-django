"""Fixture: clean serializer — no ORM violations."""

from rest_framework import serializers  # type: ignore[import-untyped]


class GoodSerializer(serializers.Serializer):
    """Serializer with no ORM calls in its methods."""

    name = serializers.CharField()

    def get_display(self, instance):
        """Access a plain attribute — no DB query."""
        return instance.name.upper()

    def validate_name(self, value):
        """Validate the name field — no DB query."""
        return value.strip()

    class Meta:
        """Serializer metadata."""

        fields = ["name"]

        def meta_helper(self):
            """Inner-class method — should not be flagged even with ORM calls."""
            from django.contrib.auth import get_user_model  # noqa: PLC0415

            User = get_user_model()
            return User.objects.all()

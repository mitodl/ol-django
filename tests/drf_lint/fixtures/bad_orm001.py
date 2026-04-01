"""Fixture: ORM001 violations — .objects manager access inside serializers."""

from django.contrib.auth import get_user_model  # type: ignore[import-untyped]
from rest_framework import serializers  # type: ignore[import-untyped]

User = get_user_model()


class UserSummarySerializer(serializers.Serializer):
    """Serializer with ORM001-triggering manager access."""

    email = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()

    def get_email(self, instance):
        """Return email by querying User.objects — triggers ORM001."""
        return (
            User.objects.filter(username=instance.username)
            .values_list("email", flat=True)
            .first()
        )

    def get_full_name(self, instance):
        """Return full name by querying Profile.objects — triggers ORM001."""
        from profiles.models import Profile  # noqa: PLC0415

        return Profile.objects.get(user=instance).name

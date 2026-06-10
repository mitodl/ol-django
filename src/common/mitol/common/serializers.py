"""DRF serializers"""

from django.core.exceptions import FieldDoesNotExist
from mitol.common.exceptions import (
    RequiredPrefetchesNotDefinedError,
    RequiredPrefetchMissingError,
)
from rest_framework import serializers

# sentinel object to indicate that you're disabling prefetch checks in non-API code
THIS_IS_NOT_AN_API = object()


class BaseSerializer(serializers.ModelSerializer):
    """Base serializer with common functionality"""

    required_prefetches: list[str]

    def __init__(self, *args, **kwargs):
        if not hasattr(self, "required_prefetches"):
            raise RequiredPrefetchesNotDefinedError(self.__class__)

        super().__init__(*args, **kwargs)

    def to_representation(self, instance):
        """Serialize to JSON typically"""
        # This is an escape hatch ONLY for tests or non-API code
        if self.context.get("skip_prefetch_checks", None) is not THIS_IS_NOT_AN_API:
            for prefetch_name in self.required_prefetches:
                try:
                    field = instance._meta.get_field(prefetch_name)  # noqa: SLF001
                    field_is_cached = field.is_cached(instance)
                except FieldDoesNotExist:
                    field_is_cached = False

                if (
                    # django's builtin select_related()
                    not field_is_cached
                    and
                    # django's builtin prefetch_related()
                    prefetch_name
                    not in getattr(instance, "_prefetched_objects_cache", {})
                    and
                    # django-prefetch's prefetch()
                    prefetch_name not in instance.__dict__
                ):
                    raise RequiredPrefetchMissingError(prefetch_name)

        return super().to_representation(instance)

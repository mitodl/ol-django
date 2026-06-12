"""DRF serializers"""

from mitol.common.exceptions import (
    RequiredPrefetchesNotDefinedError,
    RequiredPrefetchMissingError,
)
from mitol.common.utils.queryset import is_prefetched
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
                if not is_prefetched(instance, prefetch_name):
                    raise RequiredPrefetchMissingError(prefetch_name)

        return super().to_representation(instance)

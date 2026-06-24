"""DRF serializers"""

import os

import structlog
from django.conf import settings
from mitol.common.exceptions import (
    RequiredPrefetchesNotDefinedError,
    RequiredPrefetchMissingError,
    SerializerTreePath,
)
from mitol.common.utils.queryset import is_prefetched
from rest_framework import serializers

log = structlog.get_logger(__name__)

# sentinel object to indicate that you're disabling prefetch checks in non-API code
THIS_IS_NOT_AN_API = object()


def _running_under_pytest() -> bool:
    """
    Whether we appear to be running inside a pytest test run.

    ol-django has no dedicated ``TESTING`` setting, and pytest-django forces
    ``settings.DEBUG = False`` during tests, so ``DEBUG`` alone can't tell us
    we're in a test. pytest exports ``PYTEST_CURRENT_TEST`` for the duration of
    each test, which is the most reliable signal available here.
    """
    return "PYTEST_CURRENT_TEST" in os.environ


def get_serializer_tree_path(
    serializer: serializers.Serializer, field_name: str | None = None
) -> SerializerTreePath:
    path = (
        get_serializer_tree_path(serializer.parent, serializer.field_name)
        if serializer.parent is not None
        else []
    )

    if isinstance(serializer, serializers.ListSerializer):
        path.append((f"{serializer.child.__class__.__name__}(many=True)", field_name))
    else:
        path.append((serializer.__class__.__name__, field_name))

    return path


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
                    # In development, CI, and tests a missing required prefetch is a
                    # programming error worth raising loudly so N+1 queries are caught
                    # before they ship. In production we don't want a missing prefetch
                    # to turn a slow-but-correct serialization into a hard 500, so we
                    # log a structured, greppable warning and fall through to serialize
                    # (lazily) instead.
                    if settings.DEBUG or _running_under_pytest():
                        raise RequiredPrefetchMissingError(
                            prefetch_name, get_serializer_tree_path(self)
                        )

                    log.error(
                        "A required prefetch is missing",
                        serializers=self.__class__.__name__,
                        prefetch=prefetch_name,
                        model=instance._meta.label,  # noqa: SLF001
                    )

        return super().to_representation(instance)

"""VersionedSerializerMixin for DRF serializers.

This mixin hooks into DRF's to_representation and to_internal_value methods
to automatically apply version transforms. It works with ModelSerializer
and any other serializer base class (it's a mixin, not a replacement).

Usage::

    class MySerializer(VersionedSerializerMixin, serializers.ModelSerializer):
        class Meta:
            model = MyModel
            fields = "__all__"

When a request comes in for an older API version, the mixin:

- On response: applies transforms backwards (newest first) to convert
  the latest-version data to the requested version's shape.
- On request: applies transforms forwards (oldest first) to convert
  the older version's input to the latest version's shape before validation.
"""

import logging

from mitol.api_versioning.versions import (
    get_latest_version,
    get_transforms_backwards,
    get_transforms_forwards,
)
from rest_framework import serializers

log = logging.getLogger(__name__)


class VersionedSerializerMixin:
    """Mixin that applies version transforms to serializer input/output.

    Add this as the first base class (before ModelSerializer) so its
    to_representation and to_internal_value are called first in the MRO.
    """

    def __init_subclass__(cls, **kwargs):
        """Verify correct MRO placement at class definition time."""
        super().__init_subclass__(**kwargs)
        mixin_idx = None
        serializer_idx = None
        for idx, klass in enumerate(cls.__mro__):
            if klass is VersionedSerializerMixin and mixin_idx is None:
                mixin_idx = idx
            if klass is serializers.Serializer and serializer_idx is None:
                serializer_idx = idx

        if (
            mixin_idx is not None
            and serializer_idx is not None
            and mixin_idx > serializer_idx
        ):
            msg = (
                f"{cls.__name__}: VersionedSerializerMixin must appear "
                f"before the Serializer base class in the inheritance list. "
                f"Use: class {cls.__name__}(VersionedSerializerMixin, ...)"
            )
            raise TypeError(msg)

    def to_representation(self, instance):
        """Serialize instance, then apply backwards transforms for older versions."""
        data = super().to_representation(instance)
        request = self.context.get("request")
        if not request or not hasattr(request, "version"):
            return data

        latest = get_latest_version()
        if not latest or request.version == latest:
            return data

        transforms = get_transforms_backwards(self.__class__, request.version)
        if transforms:
            log.debug(
                "to_representation: %s version=%s -> %s, applying %d transform(s): %s",
                self.__class__.__name__,
                latest,
                request.version,
                len(transforms),
                " -> ".join(t.__name__ for t in transforms),
            )
        for transform_cls in transforms:
            data = transform_cls().to_representation(data, request, instance)

        return data

    def to_internal_value(self, data):
        """Apply forwards transforms for older versions, then validate."""
        request = self.context.get("request")
        if request and hasattr(request, "version"):
            latest = get_latest_version()
            if latest and request.version != latest:
                data = data.copy() if hasattr(data, "copy") else dict(data)
                transforms = get_transforms_forwards(self.__class__, request.version)
                if transforms:
                    log.debug(
                        (
                            "to_internal_value: %s version=%s -> %s, applying "
                            "%d transform(s): %s"
                        ),
                        self.__class__.__name__,
                        request.version,
                        latest,
                        len(transforms),
                        " -> ".join(t.__name__ for t in transforms),
                    )
                for transform_cls in transforms:
                    data = transform_cls().to_internal_value(data, request)

        return super().to_internal_value(data)


def transform_dict_backwards(data, serializer_class, request, *, recursive=False):
    """Apply backwards transforms to a raw dict (no model instance).

    Use this for data that bypasses DRF serialization, such as
    OpenSearch results that should match a serializer's output format.

    Args:
        data: A dict in the latest version's format.
        serializer_class: The serializer class whose transforms to apply.
        request: The DRF request (used to determine the API version).
        recursive: If True, also inspect the serializer's fields and
            recursively apply transforms to any nested serializer fields
            that have their own transforms registered.

    Returns:
        The transformed dict, or the original dict if no transforms apply.
    """
    if not request or not hasattr(request, "version"):
        return data

    latest = get_latest_version()
    if not latest or request.version == latest:
        return data

    if recursive:
        _transform_nested_fields(data, serializer_class, request)

    transforms = get_transforms_backwards(serializer_class, request.version)
    if transforms:
        log.debug(
            "transform_dict_backwards: %s version=%s, applying %d transform(s): %s",
            serializer_class.__name__,
            request.version,
            len(transforms),
            " -> ".join(t.__name__ for t in transforms),
        )
    for transform_cls in transforms:
        data = transform_cls().to_representation(data, request, instance=None)

    return data


def _apply_transforms_to_data(transforms, data, request):
    """Apply a list of transform classes to a dict or list of dicts."""
    if isinstance(data, dict):
        for transform_cls in transforms:
            transform_cls().to_representation(data, request, instance=None)
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                for transform_cls in transforms:
                    transform_cls().to_representation(item, request, instance=None)


def _transform_nested_fields(data, serializer_class, request):
    """Recursively apply transforms to nested serializer fields.

    Introspects the serializer's declared fields. For each field that
    is itself a serializer (not a primitive field), checks if transforms
    are registered for that serializer class and applies them to the
    corresponding nested dict in data. Recurses into children so that
    deeply nested serializer trees are fully transformed.
    """
    try:
        fields = serializer_class().fields
    except Exception:  # noqa: BLE001
        log.debug(
            "Failed to instantiate %s for nested field introspection",
            serializer_class.__name__,
        )
        return

    for field_name, field in fields.items():
        nested_data = data.get(field_name)
        if nested_data is None:
            continue

        child_serializer_class = _get_field_serializer_class(field)
        if child_serializer_class is None:
            continue

        # Recurse first so deepest fields are transformed before their parents
        if isinstance(nested_data, dict):
            _transform_nested_fields(nested_data, child_serializer_class, request)
        elif isinstance(nested_data, list):
            for item in nested_data:
                if isinstance(item, dict):
                    _transform_nested_fields(item, child_serializer_class, request)

        child_transforms = get_transforms_backwards(
            child_serializer_class, request.version
        )
        if child_transforms:
            _apply_transforms_to_data(child_transforms, nested_data, request)


def _get_field_serializer_class(field):
    """Extract the serializer class from a DRF field, if it is a serializer.

    Handles both direct serializer fields and many=True (ListSerializer)
    wrappers.
    """
    if isinstance(field, serializers.ListSerializer):
        return type(field.child)
    if isinstance(field, serializers.Serializer):
        return type(field)
    return None

"""Transform base class for API versioning.

Each Transform represents a single breaking change introduced in a specific
API version. Transforms define how to convert data and OpenAPI schemas between
the version that introduced the change and the previous version.

Transforms auto-register with the version registry via a metaclass.
"""

from typing import Any

from mitol.api_versioning.versions import register_transform


class TransformMeta(type):
    """Metaclass that auto-registers Transform subclasses.

    When a Transform subclass is defined with a `version` attribute, it is
    automatically registered so the versioning system can discover it.
    Validates required attributes at class definition time to catch errors early.
    """

    def __new__(cls, name, bases, dct):
        """Create a Transform subclass and auto-register concrete transforms."""
        subclass = super().__new__(cls, name, bases, dct)
        if dct.get("version") is not None:
            _validate_transform(subclass, name)
            register_transform(subclass)
        return subclass


def _validate_transform(transform_cls, name):
    """Validate a Transform subclass has correctly configured attributes.

    Raises TypeError at class definition time for misconfiguration.
    """
    version = transform_cls.version
    if not isinstance(version, str) or not version:
        msg = (
            f"Transform '{name}' has invalid version: {version!r}. "
            f"Must be a non-empty string (e.g., 'v2')."
        )
        raise TypeError(msg)

    serializer = transform_cls.serializer
    if not serializer:
        msg = (
            f"Transform '{name}' must define a 'serializer' attribute "
            f"(dotted path to the target serializer class)."
        )
        raise TypeError(msg)

    if not isinstance(serializer, (str, type)):
        msg = (
            f"Transform '{name}' has serializer={serializer!r} of type "
            f"{type(serializer).__name__}. Must be a dotted-path string or "
            f"a serializer class."
        )
        raise TypeError(msg)

    if isinstance(serializer, str) and "." not in serializer:
        msg = (
            f"Transform '{name}' has serializer={serializer!r} which "
            f"is not a dotted path. Use the full path like "
            f"'myapp.serializers.MySerializer'."
        )
        raise TypeError(msg)


class Transform(metaclass=TransformMeta):
    """Base class for API version transforms.

    Subclasses must define:
        version (str): The API version that introduced this change (e.g., "v2").
        description (str): Human-readable description of the breaking change.
        serializer (str): Dotted path to the serializer class this applies to
            (e.g., "myapp.serializers.MySerializer").
        component_name (str, optional): Explicit drf-spectacular schema component
            name to target. If not set, the name is derived from the serializer
            by stripping the "Serializer" suffix. Use this when a serializer has
            custom component naming via @extend_schema(component_name=...).

    Subclasses implement whichever methods are relevant to the change:
        - to_representation: for response data transforms
        - to_internal_value: for request data transforms
        - transform_schema: for OpenAPI schema transforms

    Data transform methods (``to_representation`` and ``to_internal_value``)
    may either mutate ``data`` in place and return it, or return a new dict.
    Both patterns are supported. The only invalid return value is ``None``.
    """

    version: str | None = None
    description: str = ""
    serializer: str | type | None = None
    component_name: str | None = None

    def to_representation(
        self,
        data: dict[str, Any],
        request: Any,  # noqa: ARG002
        instance: Any,  # noqa: ARG002
    ) -> dict[str, Any]:
        """Transform response data backwards (latest version -> older version).

        Called when a client requests an older API version. Reshape ``data``
        into the older version's expected response shape. You may either
        mutate ``data`` in place and return it, or return a new dict; both
        are supported.

        Args:
            data: The serialized response dict (latest version format).
            request: The DRF request object.
            instance: The model instance being serialized.

        Returns:
            The transformed data dict (may be the same object as ``data`` or
            a new one). Returning ``None`` raises ``TypeError``.
        """
        return data

    def to_internal_value(self, data: dict[str, Any], request: Any) -> dict[str, Any]:  # noqa: ARG002
        """Transform request data forwards (older version -> latest version).

        Called when a client sends data using an older API version format.
        Reshape ``data`` into the latest version's expected input. You may
        either mutate ``data`` in place and return it, or return a new dict;
        both are supported.

        Args:
            data: The incoming request data dict (older version format).
            request: The DRF request object.

        Returns:
            The transformed data dict (may be the same object as ``data`` or
            a new one). Returning ``None`` raises ``TypeError``.
        """
        return data

    def transform_schema(self, schema: dict[str, Any]) -> dict[str, Any]:
        """Transform an OpenAPI schema component for version compatibility.

        Called during OpenAPI spec generation to produce correct schemas
        for older API versions. This ensures generated TypeScript clients
        have accurate type definitions for each version.

        Args:
            schema: The OpenAPI schema dict for a component.

        Returns:
            The transformed schema dict.
        """
        return schema

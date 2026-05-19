"""Version registry for API versioning.

Maintains an ordered list of API versions and a registry mapping
versions to their transforms. Integrates with DRF's ALLOWED_VERSIONS
setting as the source of truth.
"""

from collections import defaultdict
from typing import TYPE_CHECKING

from django.conf import settings

if TYPE_CHECKING:
    from mitol.api_versioning.transforms import Transform


def get_allowed_versions() -> list[str]:
    """Get the ordered list of allowed API versions from DRF settings."""
    return settings.REST_FRAMEWORK.get("ALLOWED_VERSIONS", [])


def get_latest_version() -> str | None:
    """Get the latest (newest) API version."""
    versions = get_allowed_versions()
    return versions[-1] if versions else None


# Registry mapping version strings to lists of Transform classes.
# Populated via Transform metaclass auto-registration.
_transform_registry = defaultdict(list)
_registered_transforms = set()


def register_transform(transform_cls: type["Transform"]) -> None:
    """
    Register a transform class for its declared version.
    """
    if transform_cls in _registered_transforms:
        return
    _registered_transforms.add(transform_cls)
    _transform_registry[transform_cls.version].append(transform_cls)


def get_transforms_for_version(version: str) -> list[type["Transform"]]:
    """Get all transforms introduced in a specific version."""
    return list(_transform_registry.get(version, []))


def get_transforms_between(
    from_version: str, to_version: str
) -> list[type["Transform"]]:
    """Get all transforms for versions > from_version and <= to_version.

    Ordered by version (oldest first). Used to collect all transforms
    that need to be applied when converting between two versions.
    """
    versions = get_allowed_versions()
    try:
        from_idx = versions.index(from_version)
        to_idx = versions.index(to_version)
    except ValueError:
        return []

    transforms = []
    for version in versions[from_idx + 1 : to_idx + 1]:
        transforms.extend(_transform_registry.get(version, []))
    return transforms


def get_transforms_backwards(
    serializer_class: type,
    request_version: str,
    *,
    latest: str | None = None,
) -> list[type["Transform"]]:
    """Get transforms to apply backwards (newest first) for a serializer.

    Returns transform classes whose serializer matches the given class
    (by dotted path or direct class reference), ordered newest-version-first.
    """
    if latest is None:
        latest = get_latest_version()
    if not latest or request_version == latest:
        return []

    serializer_path = f"{serializer_class.__module__}.{serializer_class.__qualname__}"
    transforms = get_transforms_between(request_version, latest)

    matching = [
        t for t in transforms if t.serializer in {serializer_path, serializer_class}
    ]
    return list(reversed(matching))


def list_transforms_for_serializer(serializer_class: type) -> list[type["Transform"]]:
    """List every registered transform whose serializer matches a class.

    Debugging helper. Returns transforms across all versions, ordered
    oldest-version-first. Each entry is the transform class itself; use
    ``cls.version`` and ``cls.description`` for human-readable output.
    """
    serializer_path = f"{serializer_class.__module__}.{serializer_class.__qualname__}"
    matching = []
    for version in get_allowed_versions():
        matching.extend(
            transform_cls
            for transform_cls in _transform_registry.get(version, [])
            if transform_cls.serializer in {serializer_path, serializer_class}
        )
    return matching


def get_transforms_forwards(
    serializer_class: type,
    request_version: str,
    *,
    latest: str | None = None,
) -> list[type["Transform"]]:
    """Get transforms to apply forwards (oldest first) for a serializer.

    Returns transform classes whose serializer matches the given class,
    ordered oldest-version-first.
    """
    if latest is None:
        latest = get_latest_version()
    if not latest or request_version == latest:
        return []

    serializer_path = f"{serializer_class.__module__}.{serializer_class.__qualname__}"
    transforms = get_transforms_between(request_version, latest)

    return [
        t for t in transforms if t.serializer in {serializer_path, serializer_class}
    ]

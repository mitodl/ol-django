"""Version registry for API versioning.

Maintains an ordered list of API versions and a registry mapping
versions to their transforms. Integrates with DRF's ALLOWED_VERSIONS
setting as the source of truth.
"""

from collections import defaultdict

from django.conf import settings


def get_allowed_versions():
    """Get the ordered list of allowed API versions from DRF settings."""
    return settings.REST_FRAMEWORK.get("ALLOWED_VERSIONS", [])


def get_latest_version():
    """Get the latest (newest) API version."""
    versions = get_allowed_versions()
    return versions[-1] if versions else None


# Registry mapping version strings to lists of Transform classes.
# Populated via Transform metaclass auto-registration.
_transform_registry = defaultdict(list)
_registered_transforms = set()


def register_transform(transform_cls):
    """
    Register a transform class for its declared version.
    """
    if transform_cls in _registered_transforms:
        return
    _registered_transforms.add(transform_cls)
    _transform_registry[transform_cls.version].append(transform_cls)


def get_transforms_for_version(version):
    """Get all transforms introduced in a specific version."""
    return list(_transform_registry.get(version, []))


def get_transforms_between(from_version, to_version):
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


def get_transforms_backwards(serializer_class, request_version):
    """Get transforms to apply backwards (newest first) for a serializer.

    Returns transform classes whose serializer matches the given class
    (by dotted path or direct class reference), ordered newest-version-first.
    """
    latest = get_latest_version()
    if not latest or request_version == latest:
        return []

    serializer_path = f"{serializer_class.__module__}.{serializer_class.__qualname__}"
    transforms = get_transforms_between(request_version, latest)

    matching = [
        t for t in transforms if t.serializer in {serializer_path, serializer_class}
    ]
    return list(reversed(matching))


def get_transforms_forwards(serializer_class, request_version):
    """Get transforms to apply forwards (oldest first) for a serializer.

    Returns transform classes whose serializer matches the given class,
    ordered oldest-version-first.
    """
    latest = get_latest_version()
    if not latest or request_version == latest:
        return []

    serializer_path = f"{serializer_class.__module__}.{serializer_class.__qualname__}"
    transforms = get_transforms_between(request_version, latest)

    return [
        t for t in transforms if t.serializer in {serializer_path, serializer_class}
    ]

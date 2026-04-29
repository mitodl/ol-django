"""Tests for the version registry."""

import pytest
from mitol.api_versioning.transforms import Transform
from mitol.api_versioning.versions import (
    _registered_transforms,
    _transform_registry,
    get_allowed_versions,
    get_latest_version,
    get_transforms_backwards,
    get_transforms_between,
    get_transforms_for_version,
    get_transforms_forwards,
    register_transform,
)


@pytest.fixture(autouse=True)
def _clear_registry():
    """Clear the transform registry before and after each test."""
    saved_registry = dict(_transform_registry)
    saved_registered = set(_registered_transforms)
    _transform_registry.clear()
    _registered_transforms.clear()
    yield
    _transform_registry.clear()
    _registered_transforms.clear()
    _transform_registry.update(saved_registry)
    _registered_transforms.update(saved_registered)


class DummySerializer:
    """Dummy serializer class for testing."""

    __module__ = "myapp.serializers"
    __qualname__ = "DummySerializer"


class OtherSerializer:
    """Another dummy serializer class for testing."""

    __module__ = "myapp.serializers"
    __qualname__ = "OtherSerializer"


def _make_transform(version, serializer_path):
    """Create a Transform subclass for testing without triggering metaclass."""

    class TestTransform(Transform):
        pass

    TestTransform.version = version
    TestTransform.serializer = serializer_path
    register_transform(TestTransform)
    return TestTransform


def test_get_allowed_versions(settings):
    """Test reading ALLOWED_VERSIONS from DRF settings."""
    settings.REST_FRAMEWORK = {"ALLOWED_VERSIONS": ["v0", "v1", "v2"]}
    assert get_allowed_versions() == ["v0", "v1", "v2"]


def test_get_latest_version(settings):
    """Test that latest version is the last in the list."""
    settings.REST_FRAMEWORK = {"ALLOWED_VERSIONS": ["v0", "v1"]}
    assert get_latest_version() == "v1"


def test_get_latest_version_empty(settings):
    """Test latest version with empty list returns None."""
    settings.REST_FRAMEWORK = {"ALLOWED_VERSIONS": []}
    assert get_latest_version() is None


def test_register_and_get_transforms(settings):
    """Test registering transforms and retrieving by version."""
    settings.REST_FRAMEWORK = {"ALLOWED_VERSIONS": ["v0", "v1", "v2"]}
    t1 = _make_transform("v2", "myapp.serializers.DummySerializer")
    t2 = _make_transform("v2", "myapp.serializers.OtherSerializer")

    result = get_transforms_for_version("v2")
    assert t1 in result
    assert t2 in result
    assert get_transforms_for_version("v1") == []


def test_get_transforms_between(settings):
    """Test collecting transforms across a version range."""
    settings.REST_FRAMEWORK = {"ALLOWED_VERSIONS": ["v0", "v1", "v2", "v3"]}
    t_v2 = _make_transform("v2", "myapp.serializers.DummySerializer")
    t_v3 = _make_transform("v3", "myapp.serializers.DummySerializer")

    assert get_transforms_between("v1", "v3") == [t_v2, t_v3]
    assert get_transforms_between("v0", "v2") == [t_v2]
    assert get_transforms_between("v2", "v3") == [t_v3]
    assert get_transforms_between("v2", "v2") == []


def test_get_transforms_between_invalid_version(settings):
    """Test that invalid versions return empty list."""
    settings.REST_FRAMEWORK = {"ALLOWED_VERSIONS": ["v0", "v1"]}
    assert get_transforms_between("v99", "v1") == []
    assert get_transforms_between("v0", "v99") == []


def test_get_transforms_backwards(settings):
    """Test backwards ordering (newest first) for response transforms."""
    settings.REST_FRAMEWORK = {"ALLOWED_VERSIONS": ["v0", "v1", "v2", "v3"]}
    t_v2 = _make_transform("v2", "myapp.serializers.DummySerializer")
    t_v3 = _make_transform("v3", "myapp.serializers.DummySerializer")

    result = get_transforms_backwards(DummySerializer, "v1")
    assert result == [t_v3, t_v2]


def test_get_transforms_backwards_filters_by_serializer(settings):
    """Test that backwards transforms filter by serializer class."""
    settings.REST_FRAMEWORK = {"ALLOWED_VERSIONS": ["v0", "v1", "v2"]}
    _make_transform("v2", "myapp.serializers.DummySerializer")
    t_other = _make_transform("v2", "myapp.serializers.OtherSerializer")

    result = get_transforms_backwards(OtherSerializer, "v1")
    assert result == [t_other]


def test_get_transforms_backwards_latest_returns_empty(settings):
    """Test that latest version gets no transforms."""
    settings.REST_FRAMEWORK = {"ALLOWED_VERSIONS": ["v0", "v1"]}
    _make_transform("v1", "myapp.serializers.DummySerializer")

    result = get_transforms_backwards(DummySerializer, "v1")
    assert result == []


def test_get_transforms_forwards(settings):
    """Test forwards ordering (oldest first) for request transforms."""
    settings.REST_FRAMEWORK = {"ALLOWED_VERSIONS": ["v0", "v1", "v2", "v3"]}
    t_v2 = _make_transform("v2", "myapp.serializers.DummySerializer")
    t_v3 = _make_transform("v3", "myapp.serializers.DummySerializer")

    result = get_transforms_forwards(DummySerializer, "v1")
    assert result == [t_v2, t_v3]


def test_get_transforms_forwards_latest_returns_empty(settings):
    """Test that latest version gets no forwards transforms."""
    settings.REST_FRAMEWORK = {"ALLOWED_VERSIONS": ["v0", "v1"]}
    _make_transform("v1", "myapp.serializers.DummySerializer")

    result = get_transforms_forwards(DummySerializer, "v1")
    assert result == []


def test_register_transform_is_idempotent(settings):
    """Test that registering the same transform twice only adds it once."""
    settings.REST_FRAMEWORK = {"ALLOWED_VERSIONS": ["v0", "v1", "v2"]}
    t = _make_transform("v2", "myapp.serializers.DummySerializer")

    # Register again
    register_transform(t)
    register_transform(t)

    result = get_transforms_for_version("v2")
    assert result.count(t) == 1

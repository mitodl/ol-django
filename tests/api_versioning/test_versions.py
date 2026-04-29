"""Tests for the version registry."""

import pytest
from mitol.api_versioning.transforms import Transform
from mitol.api_versioning.versions import (
    get_allowed_versions,
    get_latest_version,
    get_transforms_backwards,
    get_transforms_between,
    get_transforms_for_version,
    get_transforms_forwards,
    list_transforms_for_serializer,
    register_transform,
)

DUMMY_PATH = "myapp.serializers.DummySerializer"
OTHER_PATH = "myapp.serializers.OtherSerializer"

VERSIONS_SHORT = ["v0", "v1"]
VERSIONS_LONG = ["v0", "v1", "v2", "v3"]


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


@pytest.mark.usefixtures("_versions")
def test_get_allowed_versions():
    """Test reading ALLOWED_VERSIONS from DRF settings."""
    assert get_allowed_versions() == ["v0", "v1", "v2"]


@pytest.mark.parametrize(
    ("_versions", "expected"),
    [(VERSIONS_SHORT, "v1"), ([], None)],
    indirect=["_versions"],
    ids=["non_empty", "empty"],
)
def test_get_latest_version(_versions, expected):
    """Latest version is the last entry, or None when empty."""
    assert get_latest_version() == expected


@pytest.mark.usefixtures("_versions")
def test_register_and_get_transforms():
    """Test registering transforms and retrieving by version."""
    t1 = _make_transform("v2", DUMMY_PATH)
    t2 = _make_transform("v2", OTHER_PATH)

    result = get_transforms_for_version("v2")
    assert t1 in result
    assert t2 in result
    assert get_transforms_for_version("v1") == []


@pytest.mark.parametrize("_versions", [VERSIONS_LONG], indirect=True)
def test_get_transforms_between(_versions):
    """Test collecting transforms across a version range."""
    t_v2 = _make_transform("v2", DUMMY_PATH)
    t_v3 = _make_transform("v3", DUMMY_PATH)

    assert get_transforms_between("v1", "v3") == [t_v2, t_v3]
    assert get_transforms_between("v0", "v2") == [t_v2]
    assert get_transforms_between("v2", "v3") == [t_v3]
    assert get_transforms_between("v2", "v2") == []


@pytest.mark.parametrize("_versions", [VERSIONS_SHORT], indirect=True)
def test_get_transforms_between_invalid_version(_versions):
    """Test that invalid versions return empty list."""
    assert get_transforms_between("v99", "v1") == []
    assert get_transforms_between("v0", "v99") == []


@pytest.mark.parametrize(
    ("get_func", "reverse"),
    [
        (get_transforms_backwards, True),
        (get_transforms_forwards, False),
    ],
    ids=["backwards", "forwards"],
)
@pytest.mark.parametrize("_versions", [VERSIONS_LONG], indirect=True)
def test_get_transforms_directional_ordering(_versions, get_func, reverse):
    """Backwards returns newest-first; forwards returns oldest-first."""
    t_v2 = _make_transform("v2", DUMMY_PATH)
    t_v3 = _make_transform("v3", DUMMY_PATH)

    expected = [t_v3, t_v2] if reverse else [t_v2, t_v3]
    assert get_func(DummySerializer, "v1") == expected


@pytest.mark.usefixtures("_versions")
def test_get_transforms_backwards_filters_by_serializer():
    """Test that backwards transforms filter by serializer class."""
    _make_transform("v2", DUMMY_PATH)
    t_other = _make_transform("v2", OTHER_PATH)

    result = get_transforms_backwards(OtherSerializer, "v1")
    assert result == [t_other]


@pytest.mark.parametrize(
    "get_func", [get_transforms_backwards, get_transforms_forwards]
)
@pytest.mark.parametrize("_versions", [VERSIONS_SHORT], indirect=True)
def test_get_transforms_at_latest_returns_empty(_versions, get_func):
    """At the latest version, neither direction yields transforms."""
    _make_transform("v1", DUMMY_PATH)
    assert get_func(DummySerializer, "v1") == []


@pytest.mark.parametrize("_versions", [VERSIONS_LONG], indirect=True)
def test_list_transforms_for_serializer(_versions):
    """Test that list_transforms_for_serializer returns matching transforms."""
    t_v2 = _make_transform("v2", DUMMY_PATH)
    t_v3 = _make_transform("v3", DUMMY_PATH)
    _make_transform("v2", OTHER_PATH)

    result = list_transforms_for_serializer(DummySerializer)
    assert result == [t_v2, t_v3]


@pytest.mark.usefixtures("_versions")
def test_register_transform_is_idempotent():
    """Test that registering the same transform twice only adds it once."""
    t = _make_transform("v2", DUMMY_PATH)

    register_transform(t)
    register_transform(t)

    result = get_transforms_for_version("v2")
    assert result.count(t) == 1

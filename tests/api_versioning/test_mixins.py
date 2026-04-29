"""Tests for the VersionedSerializerMixin."""

from types import SimpleNamespace

import pytest
from mitol.api_versioning.mixins import (
    VersionedSerializerMixin,
    transform_dict_backwards,
)
from mitol.api_versioning.transforms import Transform
from mitol.api_versioning.versions import _registered_transforms, _transform_registry
from rest_framework import serializers


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


@pytest.fixture
def _versions(settings):
    settings.REST_FRAMEWORK = {
        **getattr(settings, "REST_FRAMEWORK", {}),
        "ALLOWED_VERSIONS": ["v0", "v1", "v2"],
    }


class SampleSerializer(VersionedSerializerMixin, serializers.Serializer):
    """Sample serializer for testing."""

    name = serializers.CharField()
    value = serializers.IntegerField()


def test_mro_enforcement_rejects_wrong_order():
    """Mixin after Serializer in bases should raise TypeError."""
    with pytest.raises(TypeError, match="must appear before"):

        class BadSerializer(serializers.Serializer, VersionedSerializerMixin):
            name = serializers.CharField()


def _make_request(version):
    """Create a mock request with a version attribute."""
    return SimpleNamespace(version=version)


@pytest.mark.usefixtures("_versions")
def test_mixin_no_transforms():
    """With no transforms, mixin should be a no-op."""
    request = _make_request("v1")
    context = {"request": request}
    serializer = SampleSerializer(context=context)

    instance = SimpleNamespace(name="test", value=42)
    data = serializer.to_representation(instance)
    assert data == {"name": "test", "value": 42}


@pytest.mark.usefixtures("_versions")
def test_mixin_latest_version_no_transform():
    """Requests at the latest version should not apply transforms."""
    serializer_path = f"{SampleSerializer.__module__}.{SampleSerializer.__qualname__}"

    class RenameTransform(Transform):
        version = "v2"
        description = "Rename name to title"
        serializer = serializer_path

        def to_representation(self, data, request, instance):  # noqa: ARG002
            data["name_old"] = data.pop("name")
            return data

    request = _make_request("v2")  # latest
    context = {"request": request}
    serializer = SampleSerializer(context=context)

    instance = SimpleNamespace(name="test", value=42)
    data = serializer.to_representation(instance)
    assert data == {"name": "test", "value": 42}


@pytest.mark.usefixtures("_versions")
def test_mixin_older_version_applies_transform():
    """Requests at an older version should apply transforms backwards."""
    serializer_path = f"{SampleSerializer.__module__}.{SampleSerializer.__qualname__}"

    class RenameTransform(Transform):
        version = "v2"
        description = "Rename name to title"
        serializer = serializer_path

        def to_representation(self, data, request, instance):  # noqa: ARG002
            if "name" in data:
                data["title"] = data.pop("name")
            return data

    request = _make_request("v1")
    context = {"request": request}
    serializer = SampleSerializer(context=context)

    instance = SimpleNamespace(name="test", value=42)
    data = serializer.to_representation(instance)
    assert data == {"title": "test", "value": 42}


@pytest.mark.usefixtures("_versions")
def test_mixin_to_internal_value_applies_forward_transform():
    """Incoming data from older version should be transformed forwards."""
    serializer_path = f"{SampleSerializer.__module__}.{SampleSerializer.__qualname__}"

    class RenameTransform(Transform):
        version = "v2"
        description = "Rename title to name"
        serializer = serializer_path

        def to_internal_value(self, data, request):  # noqa: ARG002
            if "title" in data:
                data["name"] = data.pop("title")
            return data

    request = _make_request("v1")
    context = {"request": request}
    serializer = SampleSerializer(data={"title": "test", "value": 42}, context=context)

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["name"] == "test"


@pytest.mark.usefixtures("_versions")
def test_mixin_no_request_context():
    """Without a request in context, mixin should be a no-op."""
    serializer = SampleSerializer(context={})

    instance = SimpleNamespace(name="test", value=42)
    data = serializer.to_representation(instance)
    assert data == {"name": "test", "value": 42}


@pytest.mark.usefixtures("_versions")
def test_mixin_request_without_version():
    """With a request that has no version, mixin should be a no-op."""
    request = SimpleNamespace()
    serializer = SampleSerializer(context={"request": request})

    instance = SimpleNamespace(name="test", value=42)
    data = serializer.to_representation(instance)
    assert data == {"name": "test", "value": 42}


@pytest.mark.usefixtures("_versions")
def test_transform_dict_backwards_applies_transforms():
    """transform_dict_backwards should apply transforms to a raw dict."""
    serializer_path = f"{SampleSerializer.__module__}.{SampleSerializer.__qualname__}"

    class RenameTransform(Transform):
        version = "v2"
        description = "Rename name to title"
        serializer = serializer_path

        def to_representation(self, data, request, instance):  # noqa: ARG002
            if "name" in data:
                data["title"] = data.pop("name")
            return data

    request = _make_request("v1")
    data = {"name": "test", "value": 42}
    result = transform_dict_backwards(data, SampleSerializer, request)
    assert result == {"title": "test", "value": 42}


@pytest.mark.usefixtures("_versions")
def test_transform_dict_backwards_no_op_for_latest():
    """transform_dict_backwards should not transform at latest version."""
    request = _make_request("v2")
    data = {"name": "test", "value": 42}
    result = transform_dict_backwards(data, SampleSerializer, request)
    assert result == {"name": "test", "value": 42}


def test_transform_dict_backwards_no_request():
    """transform_dict_backwards should be a no-op with no request."""
    data = {"name": "test"}
    result = transform_dict_backwards(data, SampleSerializer, None)
    assert result == {"name": "test"}


@pytest.mark.usefixtures("_versions")
def test_transform_dict_backwards_recursive():
    """recursive=True should apply transforms to nested serializer fields."""

    class ChildSerializer(VersionedSerializerMixin, serializers.Serializer):
        """Child serializer with a field that gets transformed."""

        color = serializers.CharField()

    child_path = f"{ChildSerializer.__module__}.{ChildSerializer.__qualname__}"

    class ParentSerializer(serializers.Serializer):
        """Parent serializer with a nested child."""

        label = serializers.CharField()
        child = ChildSerializer()

    class RenameColorTransform(Transform):
        version = "v2"
        description = "Rename color to colour"
        serializer = child_path

        def to_representation(self, data, request, instance):  # noqa: ARG002
            if "color" in data:
                data["colour"] = data.pop("color")
            return data

    request = _make_request("v1")
    data = {"label": "test", "child": {"color": "red"}}
    result = transform_dict_backwards(data, ParentSerializer, request, recursive=True)
    assert result["child"] == {"colour": "red"}
    assert result["label"] == "test"


@pytest.mark.usefixtures("_versions")
def test_transform_dict_backwards_recursive_many():
    """recursive=True should handle many=True nested serializer fields."""

    class ItemSerializer(VersionedSerializerMixin, serializers.Serializer):
        """Item serializer."""

        name = serializers.CharField()

    item_path = f"{ItemSerializer.__module__}.{ItemSerializer.__qualname__}"

    class ContainerSerializer(serializers.Serializer):
        """Container with many nested items."""

        title = serializers.CharField()
        items = ItemSerializer(many=True)

    class AddFieldTransform(Transform):
        version = "v2"
        description = "Add score field"
        serializer = item_path

        def to_representation(self, data, request, instance):  # noqa: ARG002
            data.pop("score", None)
            return data

    request = _make_request("v1")
    data = {
        "title": "container",
        "items": [
            {"name": "a", "score": 10},
            {"name": "b", "score": 20},
        ],
    }
    result = transform_dict_backwards(
        data, ContainerSerializer, request, recursive=True
    )
    assert result["items"] == [{"name": "a"}, {"name": "b"}]


@pytest.mark.usefixtures("_versions")
def test_transform_dict_backwards_recursive_no_nested_transforms():
    """recursive=True with no child transforms should be a no-op."""
    request = _make_request("v1")
    data = {"name": "test", "value": 42}
    result = transform_dict_backwards(data, SampleSerializer, request, recursive=True)
    # SampleSerializer has no nested serializer fields, so no change
    assert result == {"name": "test", "value": 42}


@pytest.mark.usefixtures("_versions")
def test_transform_dict_backwards_recursive_deep_nesting():
    """recursive=True should apply transforms to deeply nested serializer fields."""

    class GrandchildSerializer(VersionedSerializerMixin, serializers.Serializer):
        color = serializers.CharField()

    grandchild_path = (
        f"{GrandchildSerializer.__module__}.{GrandchildSerializer.__qualname__}"
    )

    class ChildSerializer(VersionedSerializerMixin, serializers.Serializer):
        label = serializers.CharField()
        grandchild = GrandchildSerializer()

    class ParentSerializer(serializers.Serializer):
        title = serializers.CharField()
        child = ChildSerializer()

    class RenameColorTransform(Transform):
        version = "v2"
        description = "Rename color to colour"
        serializer = grandchild_path

        def to_representation(self, data, request, instance):  # noqa: ARG002
            if "color" in data:
                data["colour"] = data.pop("color")
            return data

    request = _make_request("v1")
    data = {
        "title": "top",
        "child": {
            "label": "mid",
            "grandchild": {"color": "red"},
        },
    }
    result = transform_dict_backwards(data, ParentSerializer, request, recursive=True)
    assert result["child"]["grandchild"] == {"colour": "red"}
    assert result["child"]["label"] == "mid"
    assert result["title"] == "top"

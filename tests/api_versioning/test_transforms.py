"""Tests for the Transform base class and auto-registration."""

import pytest
from mitol.api_versioning.transforms import Transform
from mitol.api_versioning.versions import (
    _transform_registry,
    get_transforms_for_version,
)

SERIALIZER_PATH = "myapp.serializers.MySerializer"


def test_transform_base_defaults():
    """Base Transform methods should return data unchanged."""
    t = Transform()
    data = {"field": "value"}
    assert t.to_representation(data, None, None) == data
    assert t.to_internal_value(data, None) == data
    assert t.transform_schema({"properties": {}}) == {"properties": {}}


@pytest.mark.usefixtures("_versions")
def test_metaclass_auto_registration():
    """Defining a Transform subclass with a version should auto-register it."""

    class MyTransform(Transform):
        version = "v2"
        description = "Test transform"
        serializer = SERIALIZER_PATH

    assert MyTransform in get_transforms_for_version("v2")


@pytest.mark.parametrize(
    ("version", "serializer", "match"),
    [
        ("v2", None, "must define a 'serializer'"),
        ("v2", "NotADottedPath", "not a dotted path"),
        ("", SERIALIZER_PATH, "invalid version"),
    ],
    ids=["missing_serializer", "non_dotted_serializer", "empty_version"],
)
def test_metaclass_validation_rejects_bad_config(version, serializer, match):
    """Metaclass validation rejects misconfigured Transform subclasses."""
    attrs = {"version": version, "description": "bad"}
    if serializer is not None:
        attrs["serializer"] = serializer

    with pytest.raises(TypeError, match=match):
        type("BadTransform", (Transform,), attrs)


@pytest.mark.parametrize("_versions", [["v0", "v1"]], indirect=True)
def test_metaclass_no_registration_without_version(_versions):
    """A Transform subclass without a version should not be registered."""

    class AbstractTransform(Transform):
        description = "Not a real transform"

    for transforms in _transform_registry.values():
        assert AbstractTransform not in transforms


@pytest.mark.usefixtures("_versions")
def test_concrete_transform_field_rename():
    """Test a concrete transform that renames a field."""

    class RenameFieldTransform(Transform):
        version = "v2"
        description = "Rename 'old_name' to 'new_name'"
        serializer = SERIALIZER_PATH

        def to_representation(self, data, request, instance):  # noqa: ARG002
            if "new_name" in data:
                data["old_name"] = data.pop("new_name")
            return data

        def to_internal_value(self, data, request):  # noqa: ARG002
            if "old_name" in data:
                data["new_name"] = data.pop("old_name")
            return data

        def transform_schema(self, schema):
            props = schema.get("properties", {})
            if "new_name" in props:
                props["old_name"] = props.pop("new_name")
            return schema

    t = RenameFieldTransform()

    data = {"new_name": "value", "other": "keep"}
    result = t.to_representation(data, None, None)
    assert result == {"old_name": "value", "other": "keep"}

    data = {"old_name": "value"}
    result = t.to_internal_value(data, None)
    assert result == {"new_name": "value"}

    schema = {
        "properties": {
            "new_name": {"type": "string"},
            "other": {"type": "int"},
        }
    }
    result = t.transform_schema(schema)
    assert "old_name" in result["properties"]
    assert "new_name" not in result["properties"]


@pytest.mark.usefixtures("_versions")
def test_concrete_transform_field_added():
    """Test a transform for a field added in a new version."""

    class AddFieldTransform(Transform):
        version = "v2"
        description = "Add 'new_field' in v2"
        serializer = SERIALIZER_PATH

        def to_representation(self, data, request, instance):  # noqa: ARG002
            data.pop("new_field", None)
            return data

        def transform_schema(self, schema):
            schema.get("properties", {}).pop("new_field", None)
            required = schema.get("required", [])
            if "new_field" in required:
                required.remove("new_field")
            return schema

    t = AddFieldTransform()

    data = {"existing": "value", "new_field": "added"}
    result = t.to_representation(data, None, None)
    assert result == {"existing": "value"}

    schema = {
        "properties": {
            "existing": {"type": "string"},
            "new_field": {"type": "string"},
        },
        "required": ["existing", "new_field"],
    }
    result = t.transform_schema(schema)
    assert "new_field" not in result["properties"]
    assert "new_field" not in result["required"]


@pytest.mark.usefixtures("_versions")
def test_concrete_transform_field_removed():
    """Test a transform for a field removed in a new version."""

    class RemoveFieldTransform(Transform):
        version = "v2"
        description = "Remove 'legacy_field' in v2"
        serializer = SERIALIZER_PATH

        def to_representation(self, data, request, instance):  # noqa: ARG002
            data["legacy_field"] = getattr(instance, "legacy_field", None)
            return data

        def to_internal_value(self, data, request):  # noqa: ARG002
            data.pop("legacy_field", None)
            return data

        def transform_schema(self, schema):
            schema.setdefault("properties", {})["legacy_field"] = {"type": "string"}
            return schema

    t = RemoveFieldTransform()

    instance = type("Obj", (), {"legacy_field": "old_value"})()
    data = {"current_field": "value"}
    result = t.to_representation(data, None, instance)
    assert result == {
        "current_field": "value",
        "legacy_field": "old_value",
    }

    data = {"current_field": "value", "legacy_field": "old_value"}
    result = t.to_internal_value(data, None)
    assert result == {"current_field": "value"}


@pytest.mark.usefixtures("_versions")
def test_concrete_transform_type_change():
    """Test a transform for a field whose type/structure changed."""

    class TypeChangeTransform(Transform):
        version = "v2"
        description = "Change 'topics' from list of strings to list of objects"
        serializer = SERIALIZER_PATH

        def to_representation(self, data, request, instance):  # noqa: ARG002
            if "topics" in data and isinstance(data["topics"], list):
                data["topics"] = [
                    t["name"] if isinstance(t, dict) else t for t in data["topics"]
                ]
            return data

        def to_internal_value(self, data, request):  # noqa: ARG002
            if "topics" in data and isinstance(data["topics"], list):
                data["topics"] = [
                    {"name": t} if isinstance(t, str) else t for t in data["topics"]
                ]
            return data

    t = TypeChangeTransform()

    data = {
        "topics": [
            {"id": 1, "name": "Math"},
            {"id": 2, "name": "Physics"},
        ]
    }
    result = t.to_representation(data, None, None)
    assert result == {"topics": ["Math", "Physics"]}

    data = {"topics": ["Math", "Physics"]}
    result = t.to_internal_value(data, None)
    assert result == {"topics": [{"name": "Math"}, {"name": "Physics"}]}

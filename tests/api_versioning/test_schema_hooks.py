"""Tests for the drf-spectacular schema postprocessing hook."""

from types import SimpleNamespace

import pytest
from mitol.api_versioning.schema_hooks import (
    _get_all_schema_variants,
    _resolve_schema_name,
    postprocess_versioned_schema,
)
from mitol.api_versioning.transforms import Transform
from mitol.api_versioning.versions import register_transform


class TestResolveSchemaName:
    """Tests for _resolve_schema_name."""

    class CourseSerializer:
        pass

    class Course:
        pass

    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("myapp.serializers.LearningResourceSerializer", "LearningResource"),
            ("myapp.serializers.LearningResource", "LearningResource"),
            ("CourseSerializer", "Course"),
            (CourseSerializer, "Course"),
            (Course, "Course"),
        ],
        ids=[
            "dotted_with_suffix",
            "dotted_without_suffix",
            "simple_with_suffix",
            "class_with_suffix",
            "class_without_suffix",
        ],
    )
    def test_resolves(self, name, expected):
        assert _resolve_schema_name(name) == expected


class TestGetAllSchemaVariants:
    """Tests for _get_all_schema_variants."""

    def test_finds_base_and_variants(self):
        """Test finding all expected variants."""
        schemas = {
            "LearningResource": {},
            "LearningResourceRequest": {},
            "PatchedLearningResource": {},
            "PatchedLearningResourceRequest": {},
            "Course": {},
        }
        result = _get_all_schema_variants("LearningResource", schemas)
        assert set(result) == {
            "LearningResource",
            "LearningResourceRequest",
            "PatchedLearningResource",
            "PatchedLearningResourceRequest",
        }

    def test_no_matches(self):
        """Test with no matching schemas."""
        schemas = {"Course": {}, "Program": {}}
        assert _get_all_schema_variants("LearningResource", schemas) == []

    def test_does_not_over_match_similar_names(self):
        """'Course' should NOT match 'CourseRun' or 'CourseFeature'."""
        schemas = {
            "Course": {},
            "CourseRequest": {},
            "CourseRun": {},
            "CourseRunRequest": {},
            "CourseFeature": {},
            "PatchedCourse": {},
            "PatchedCourseRequest": {},
            "PatchedCourseRun": {},
        }
        result = _get_all_schema_variants("Course", schemas)
        assert set(result) == {
            "Course",
            "CourseRequest",
            "PatchedCourse",
            "PatchedCourseRequest",
        }


class TestPostprocessVersionedSchema:
    """Tests for the drf-spectacular postprocessing hook."""

    @pytest.mark.usefixtures("_versions")
    def test_no_op_for_latest_version(self):
        """Hook should return schema unchanged for latest version."""
        generator = SimpleNamespace(api_version="v2")
        schema = {
            "components": {
                "schemas": {
                    "Course": {"properties": {"name": {"type": "string"}}},
                }
            }
        }
        result = postprocess_versioned_schema(schema, generator, None, public=False)
        assert result == schema

    @pytest.mark.usefixtures("_versions")
    def test_applies_transform_for_older_version(self):
        """Hook should apply schema transforms for older versions."""

        class RenameFieldTransform(Transform):
            version = "v2"
            description = "Rename name to title"
            serializer = "myapp.serializers.CourseSerializer"

            def transform_schema(self, schema):
                props = schema.get("properties", {})
                if "name" in props:
                    props["title"] = props.pop("name")
                return schema

        generator = SimpleNamespace(api_version="v1")
        schema = {
            "components": {
                "schemas": {
                    "Course": {
                        "properties": {
                            "name": {"type": "string"},
                            "id": {"type": "integer"},
                        }
                    },
                }
            }
        }
        result = postprocess_versioned_schema(schema, generator, None, public=False)
        props = result["components"]["schemas"]["Course"]["properties"]
        assert "title" in props
        assert "name" not in props
        assert "id" in props

    @pytest.mark.usefixtures("_versions")
    def test_applies_transform_to_variants(self):
        """Hook should apply transforms to Request/Patched variants too."""

        class AddFieldTransform(Transform):
            version = "v2"
            description = "Add extra_field in v2"
            serializer = "myapp.serializers.CourseSerializer"

            def transform_schema(self, schema):
                schema.get("properties", {}).pop("extra_field", None)
                return schema

        generator = SimpleNamespace(api_version="v1")
        schema = {
            "components": {
                "schemas": {
                    "Course": {
                        "properties": {
                            "name": {"type": "string"},
                            "extra_field": {"type": "string"},
                        }
                    },
                    "CourseRequest": {
                        "properties": {
                            "name": {"type": "string"},
                            "extra_field": {"type": "string"},
                        }
                    },
                }
            }
        }
        result = postprocess_versioned_schema(schema, generator, None, public=False)

        course = result["components"]["schemas"]["Course"]["properties"]
        assert "extra_field" not in course
        req = result["components"]["schemas"]["CourseRequest"]["properties"]
        assert "extra_field" not in req

    @pytest.mark.parametrize(
        ("_versions", "schema"),
        [
            (
                ["v0", "v1", "v2"],
                {
                    "components": {
                        "schemas": {
                            "Course": {"properties": {"name": {"type": "string"}}},
                        }
                    }
                },
            ),
            (["v0", "v1", "v2"], {"info": {"title": "API"}}),
            ([], {"components": {"schemas": {}}}),
        ],
        ids=[
            "no_transforms_registered",
            "schema_without_components",
            "no_versions_configured",
        ],
        indirect=["_versions"],
    )
    def test_returns_unchanged(self, _versions, schema):
        """Hook returns schema unchanged when there is nothing to transform."""
        generator = SimpleNamespace(api_version="v1")
        result = postprocess_versioned_schema(schema, generator, None, public=False)
        assert result == schema

    @pytest.mark.usefixtures("_versions")
    def test_component_name_override(self):
        """Transform with explicit component_name should target that name."""

        class CustomNameTransform(Transform):
            version = "v2"
            description = "Uses custom component name"
            serializer = "myapp.serializers.WeirdlyNamedSerializer"
            component_name = "Course"

            def transform_schema(self, schema):
                props = schema.get("properties", {})
                if "new_field" in props:
                    del props["new_field"]
                return schema

        generator = SimpleNamespace(api_version="v1")
        schema = {
            "components": {
                "schemas": {
                    "Course": {
                        "properties": {
                            "name": {"type": "string"},
                            "new_field": {"type": "string"},
                        }
                    },
                    "WeirdlyNamed": {
                        "properties": {
                            "name": {"type": "string"},
                            "new_field": {"type": "string"},
                        }
                    },
                }
            }
        }
        result = postprocess_versioned_schema(schema, generator, None, public=False)
        # Should target "Course" (component_name), not "WeirdlyNamed" (derived)
        assert (
            "new_field" not in result["components"]["schemas"]["Course"]["properties"]
        )
        assert (
            "new_field" in result["components"]["schemas"]["WeirdlyNamed"]["properties"]
        )

    @pytest.mark.usefixtures("_versions")
    def test_class_based_serializer_reference(self):
        """Transform with a class object as serializer should work in schema hook."""

        class MySerializer:
            pass

        class ClassRefTransform(Transform):
            description = "Uses class ref"
            serializer = "myapp.serializers.MySerializer"

            def transform_schema(self, schema):
                schema.get("properties", {}).pop("added", None)
                return schema

        # Register with class ref for serializer matching,
        # but use string for this test's schema targeting
        ClassRefTransform.version = "v2"
        ClassRefTransform.serializer = MySerializer
        register_transform(ClassRefTransform)

        generator = SimpleNamespace(api_version="v1")
        schema = {
            "components": {
                "schemas": {
                    "My": {
                        "properties": {
                            "name": {"type": "string"},
                            "added": {"type": "string"},
                        }
                    },
                }
            }
        }
        result = postprocess_versioned_schema(schema, generator, None, public=False)
        assert "added" not in result["components"]["schemas"]["My"]["properties"]

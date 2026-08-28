"""Tests for Rule ORM003: accessing a query-performing model property."""

from __future__ import annotations

from mitol.drf_lint.checker import check_source

_SERIALIZER = """
from rest_framework import serializers

from myapp.models import Course


class CourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = ["id"]

    def get_thing(self, {receiver}):
        return {expression}
"""


def _rules(project, expression, receiver="instance"):
    project.with_models()
    path = project.serializer(
        _SERIALIZER.format(expression=expression, receiver=receiver)
    )
    return project.rules(path)


# ------------------------------------------------------------------ #
# Positive cases - should flag
# ------------------------------------------------------------------ #


def test_orm003_query_property_access(project):
    """`instance.run_count` runs a query on attribute access."""
    assert _rules(project, "instance.run_count") == ["ORM003"]


def test_orm003_transitive_property(project):
    """A property that only reaches a query two calls away still counts."""
    assert _rules(project, "instance.summary") == ["ORM003"]


def test_orm003_inherited_property(project):
    """A querying property from an abstract base counts on the subclass."""
    assert _rules(project, "instance.revision_count") == ["ORM003"]


def test_orm003_cached_property(project):
    """`@cached_property` caches per instance, so a list response still N+1s."""
    assert _rules(project, "instance.cached_runs") == ["ORM003"]


def test_orm003_receiver_named_anything(project):
    """The second parameter of a get_* method is the instance, whatever its name."""
    assert _rules(project, "obj.run_count", receiver="obj") == ["ORM003"]


def test_orm003_self_instance(project):
    """`self.instance` is DRF's own attribute and is unambiguous."""
    assert _rules(project, "self.instance.run_count") == ["ORM003"]


def test_orm003_single_assignment_alias(project):
    """An alias of the instance is still the instance."""
    project.with_models()
    path = project.serializer(
        """
        from rest_framework import serializers

        from myapp.models import Course


        class CourseSerializer(serializers.ModelSerializer):
            class Meta:
                model = Course
                fields = ["id"]

            def get_thing(self, instance):
                alias = instance
                return alias.run_count
        """
    )
    assert project.rules(path) == ["ORM003"]


def test_orm003_message_names_the_chain(project):
    """A transitive hit reports the path it took to reach the database."""
    project.with_models()
    path = project.serializer(
        _SERIALIZER.format(expression="instance.summary", receiver="instance")
    )
    (violation,) = project.check(path)
    assert "Course.summary → Course.get_price → compute_stats" in violation.message


# ------------------------------------------------------------------ #
# Negative cases - should NOT flag
# ------------------------------------------------------------------ #


def test_orm003_clean_property_not_flagged(project):
    """A property that touches only plain attributes is free."""
    assert _rules(project, "instance.plain_name") == []


def test_orm003_plain_field_not_flagged(project):
    """A concrete model field is not a property."""
    assert _rules(project, "instance.name") == []


def test_orm003_shadowed_property_not_flagged(project):
    """Track overrides run_count with a clean property."""
    project.with_models()
    path = project.serializer(
        _SERIALIZER.replace("Course", "Track").format(
            expression="instance.run_count", receiver="instance"
        )
    )
    assert project.rules(path) == []


def test_orm003_same_name_on_an_unrelated_model_not_flagged(project):
    """Strict resolution ties the name to this serializer's own model."""
    project.write(
        "otherapp/models.py",
        """
        class Unrelated:
            @property
            def gadget_count(self):
                return self.gadgets.count()
        """,
    )
    assert _rules(project, "instance.gadget_count") == []


def test_orm003_unknown_receiver_not_flagged(project):
    """A local of unknown type is not assumed to be the model."""
    project.with_models()
    path = project.serializer(
        """
        from rest_framework import serializers

        from myapp.models import Course


        class CourseSerializer(serializers.ModelSerializer):
            class Meta:
                model = Course
                fields = ["id"]

            def get_thing(self, instance):
                other = fetch_something()
                return other.run_count
        """
    )
    assert project.rules(path) == []


def test_orm003_serializer_context_not_flagged(project):
    """`self.context[...]` is not the model instance."""
    assert _rules(project, 'self.context["request"].user.run_count') == []


def test_orm003_reassigned_alias_is_dropped(project):
    """An alias rebound to something else stops being the instance."""
    project.with_models()
    path = project.serializer(
        """
        from rest_framework import serializers

        from myapp.models import Course


        class CourseSerializer(serializers.ModelSerializer):
            class Meta:
                model = Course
                fields = ["id"]

            def get_thing(self, instance):
                alias = instance
                alias = fetch_something()
                return alias.run_count
        """
    )
    assert project.rules(path) == []


def test_orm003_exempt_write_path_method(project):
    """The existing write-path exemption still applies with an index."""
    project.with_models()
    path = project.serializer(
        """
        from rest_framework import serializers

        from myapp.models import Course


        class CourseSerializer(serializers.ModelSerializer):
            class Meta:
                model = Course
                fields = ["id"]

            def validate_name(self, value):
                return self.instance.run_count
        """
    )
    assert project.rules(path) == []


def test_orm003_needs_an_index(project):
    """Without a context there is no index, so nothing cross-file fires."""
    project.with_models()
    source = (
        project.root
        / project.serializer(
            _SERIALIZER.format(expression="instance.run_count", receiver="instance")
        )
    ).read_text()
    assert check_source(source) == []


def test_orm003_unresolvable_model_not_flagged(project):
    """A Meta.model the index cannot place produces nothing."""
    project.with_models()
    path = project.serializer(
        """
        from rest_framework import serializers


        class CourseSerializer(serializers.ModelSerializer):
            class Meta:
                model = SomethingUnknown
                fields = ["id"]

            def get_thing(self, instance):
                return instance.run_count
        """
    )
    assert project.rules(path) == []


# ------------------------------------------------------------------ #
# Suppression and precedence
# ------------------------------------------------------------------ #


def test_orm003_noqa_specific_code(project):
    """`# noqa: ORM003` suppresses the violation on that line."""
    assert _rules(project, "instance.run_count  # noqa: ORM003") == []


def test_orm003_yields_to_orm004_when_called(project):
    """`instance.get_price()` is one ORM004, never also an ORM003."""
    assert _rules(project, "instance.get_price()") == ["ORM004"]


def test_orm003_yields_to_orm002_on_a_queryset_call(project):
    """A literal queryset call stays ORM002 and is not double-reported."""
    assert _rules(project, "instance.runs.all()") == ["ORM002"]

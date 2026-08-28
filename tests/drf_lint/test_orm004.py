"""Tests for Rule ORM004: calling something that reaches the database."""

from __future__ import annotations

_SERIALIZER = """
from rest_framework import serializers

from myapp.models import Course
from myapp.utils import compute_stats, pure_helper


class CourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = ["id"]

    def get_thing(self, instance):
        return {expression}
"""


def _rules(project, expression):
    project.with_models()
    return project.rules(project.serializer(_SERIALIZER.format(expression=expression)))


# ------------------------------------------------------------------ #
# Positive cases - should flag
# ------------------------------------------------------------------ #


def test_orm004_imported_function(project):
    """A helper imported from another module."""
    assert _rules(project, "compute_stats(instance)") == ["ORM004"]


def test_orm004_model_method(project):
    """A method on the resolved model."""
    assert _rules(project, "instance.get_price()") == ["ORM004"]


def test_orm004_serializer_own_method(project):
    """`self.<helper>()` resolves against the serializer class itself.

    Both the call and the queryset inside the helper are reported, in source
    order: the call site first, then the literal query it leads to.
    """
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
                return self._lookup(instance)

            def _lookup(self, instance):
                return instance.runs.all()
        """
    )
    assert project.rules(path) == ["ORM004", "ORM002"]


def test_orm004_classmethod_on_a_model(project):
    """A querying classmethod reached through the class name."""
    project.write(
        "myapp/models.py",
        """
        class Registry:
            @classmethod
            def lookup(cls):
                return cls.objects.all()
        """,
    )
    path = project.serializer(
        """
        from rest_framework import serializers

        from myapp.models import Registry


        class RegistrySerializer(serializers.ModelSerializer):
            class Meta:
                model = Registry
                fields = ["id"]

            def get_thing(self, instance):
                return Registry.lookup()
        """
    )
    assert project.rules(path) == ["ORM004"]


def test_orm004_message_names_the_chain(project):
    """The message explains how the callee reaches the database."""
    project.with_models()
    path = project.serializer(_SERIALIZER.format(expression="instance.summary()"))
    (violation,) = project.check(path)
    assert "Course.get_price" in violation.message


# ------------------------------------------------------------------ #
# Negative cases - should NOT flag
# ------------------------------------------------------------------ #


def test_orm004_pure_helper_not_flagged(project):
    """A helper that touches nothing is free."""
    assert _rules(project, "pure_helper(instance.name)") == []


def test_orm004_clean_model_method_not_flagged(project):
    """A model method that does no work is free."""
    assert _rules(project, "instance.cheap()") == []


def test_orm004_unknown_callable_not_flagged(project):
    """A name the index cannot resolve produces nothing."""
    assert _rules(project, "mystery_function(instance)") == []


def test_orm004_super_call_not_flagged(project):
    """`super().to_representation(...)` has no resolvable receiver."""
    assert _rules(project, "super().to_representation(instance)") == []


def test_orm004_locally_shadowed_name_not_flagged(project):
    """A local definition wins over the import of the same name."""
    project.with_models()
    path = project.serializer(
        """
        from rest_framework import serializers

        from myapp.models import Course


        def compute_stats(obj):
            return 1


        class CourseSerializer(serializers.ModelSerializer):
            class Meta:
                model = Course
                fields = ["id"]

            def get_thing(self, instance):
                return compute_stats(instance)
        """
    )
    assert project.rules(path) == []


def test_orm004_does_not_double_report_a_queryset_call(project):
    """`instance.runs.all()` is exactly one ORM002."""
    assert _rules(project, "instance.runs.all()") == ["ORM002"]


def test_orm004_exempt_write_path_method(project):
    """Write-path methods stay exempt."""
    project.with_models()
    path = project.serializer(
        """
        from rest_framework import serializers

        from myapp.models import Course
        from myapp.utils import compute_stats


        class CourseSerializer(serializers.ModelSerializer):
            class Meta:
                model = Course
                fields = ["id"]

            def create(self, validated_data):
                return compute_stats(validated_data)
        """
    )
    assert project.rules(path) == []


def test_orm004_noqa(project):
    """`# noqa: ORM004` suppresses the violation."""
    assert _rules(project, "compute_stats(instance)  # noqa: ORM004") == []

"""Tests for Rule ORM006: traversing an unfetched foreign key."""

from __future__ import annotations

_SERIALIZER = """
from rest_framework import serializers

from myapp.models import Course


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


def test_orm006_foreign_key_traversal(project):
    """`instance.author.name` fetches the related row."""
    assert _rules(project, "instance.author.name") == ["ORM006"]


def test_orm006_message_names_the_relation(project):
    """The message says which relation needs select_related."""
    project.with_models()
    path = project.serializer(_SERIALIZER.format(expression="instance.author.name"))
    (violation,) = project.check(path)
    assert "Course.author" in violation.message


def test_orm006_many_to_many_access_is_free(project):
    """Touching a m2m manager returns it without querying."""
    assert _rules(project, "instance.topics") == []


def test_orm006_many_to_many_call_is_orm002(project):
    """Evaluating the m2m manager is the existing related-manager rule."""
    assert _rules(project, "instance.topics.all()") == ["ORM002"]


def test_orm006_plain_field_not_flagged(project):
    """A concrete field is not a relation."""
    assert _rules(project, "instance.name") == []


def test_orm006_noqa(project):
    """`# noqa: ORM006` suppresses the violation."""
    assert _rules(project, "instance.author.name  # noqa: ORM006") == []


def test_orm006_can_be_disabled(project):
    """ORM006 is the noisiest rule, so it must be individually disableable."""
    project.with_models()
    path = project.serializer(_SERIALIZER.format(expression="instance.author.name"))
    from mitol.drf_lint.checker import ALL_RULES  # noqa: PLC0415

    assert project.rules(path, enabled_rules=ALL_RULES - {"ORM006"}) == []

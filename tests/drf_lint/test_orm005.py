"""Tests for Rule ORM005: a field backed by a query-performing model member."""

from __future__ import annotations

_SERIALIZER = """
from rest_framework import serializers

from myapp.models import Course


class CourseSerializer(serializers.ModelSerializer):
{body}
    class Meta:
        model = Course
        {meta}
"""


def _check(project, meta, body=""):
    project.with_models()
    return project.check(project.serializer(_SERIALIZER.format(meta=meta, body=body)))


def _rules(project, meta, body=""):
    return [v.rule for v in _check(project, meta, body)]


# ------------------------------------------------------------------ #
# Positive cases - should flag
# ------------------------------------------------------------------ #


def test_orm005_query_property_in_fields(project):
    """A property named in `fields` becomes a ReadOnlyField that queries."""
    assert _rules(project, 'fields = ["id", "run_count"]') == ["ORM005"]


def test_orm005_transitive_property_in_fields(project):
    """A property that reaches a query indirectly counts too."""
    assert _rules(project, 'fields = ["summary"]') == ["ORM005"]


def test_orm005_reports_the_element_position(project):
    """The violation lands on the offending string, not the whole list."""
    (violation,) = _check(project, 'fields = ["id", "run_count"]')
    source = (project.root / "myapp/serializers.py").read_text().splitlines()
    line = source[violation.line - 1]
    assert line[violation.col :].startswith('"run_count"')


def test_orm005_multiline_list_position(project):
    """Each element carries its own line, so per-element noqa works."""
    (violation,) = _check(
        project,
        'fields = [\n            "id",\n            "run_count",\n        ]',
    )
    source = (project.root / "myapp/serializers.py").read_text().splitlines()
    assert '"run_count"' in source[violation.line - 1]


def test_orm005_declared_field_with_source(project):
    """`source="run_count"` is reported at the source string."""
    rules = _rules(
        project,
        'fields = ["total"]',
        body='    total = serializers.IntegerField(source="run_count")\n',
    )
    assert rules == ["ORM005"]


def test_orm005_declared_field_bound_by_name(project):
    """A declared field with no source binds to the model member of that name."""
    rules = _rules(
        project,
        'fields = ["run_count"]',
        body="    run_count = serializers.IntegerField()\n",
    )
    assert rules == ["ORM005"]


def test_orm005_concatenated_fields_list(project):
    """`BASE + [...]` is analysed for the literal part."""
    assert _rules(project, 'fields = BASE_FIELDS + ["run_count"]') == ["ORM005"]


# ------------------------------------------------------------------ #
# Negative cases - should NOT flag
# ------------------------------------------------------------------ #


def test_orm005_all_fields_cannot_pull_in_a_property(project):
    """DRF expands `__all__` through model._meta, which has no properties."""
    assert _rules(project, 'fields = "__all__"') == []


def test_orm005_clean_property_in_fields(project):
    """A property that does no query is fine to serialize."""
    assert _rules(project, 'fields = ["id", "plain_name"]') == []


def test_orm005_concrete_field_in_fields(project):
    """A plain model field is not a query."""
    assert _rules(project, 'fields = ["id", "name"]') == []


def test_orm005_method_field_is_left_to_orm003(project):
    """`SerializerMethodField` gets its value from get_*, checked elsewhere."""
    rules = _rules(
        project,
        'fields = ["run_count"]',
        body="    run_count = serializers.SerializerMethodField()\n",
    )
    assert rules == []


def test_orm005_dynamic_fields_list_is_skipped(project):
    """An opaque constant produces nothing rather than a crash."""
    assert _rules(project, "fields = SOME_CONSTANT") == []


def test_orm005_read_only_fields_is_not_a_report_site(project):
    """Names must also appear in `fields`, so reporting twice would duplicate."""
    rules = _rules(
        project,
        'fields = ["run_count"]\n        read_only_fields = ["run_count"]',
    )
    assert rules == ["ORM005"]


def test_orm005_shadowed_property_not_flagged(project):
    """Track overrides run_count with a clean property."""
    project.with_models()
    path = project.serializer(
        """
        from rest_framework import serializers

        from myapp.models import Track


        class TrackSerializer(serializers.ModelSerializer):
            class Meta:
                model = Track
                fields = ["id", "run_count"]
        """
    )
    assert project.rules(path) == []


def test_orm005_no_meta_model(project):
    """Without a model there is nothing to resolve the name against."""
    project.with_models()
    path = project.serializer(
        """
        from rest_framework import serializers


        class ThingSerializer(serializers.Serializer):
            class Meta:
                fields = ["run_count"]
        """
    )
    assert project.rules(path) == []


def test_orm005_noqa_on_the_element_line(project):
    """A per-element `# noqa: ORM005` inside a multi-line list works."""
    rules = _rules(
        project,
        'fields = [\n            "id",\n'
        '            "run_count",  # noqa: ORM005\n        ]',
    )
    assert rules == []

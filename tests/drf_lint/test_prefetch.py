"""Tests for required_prefetches awareness: ORM007, ORM008, ORM009.

``BaseSerializer`` promises, and ``to_representation`` enforces, that every
name in ``required_prefetches`` was fetched before serialization.  These tests
pin down both halves of using that: staying quiet when the declaration covers
the access, and naming the missing entry when it does not.
"""

from __future__ import annotations

import pytest
from mitol.drf_lint.index.model import QueryHit
from mitol.drf_lint.rules import prefetch

_SERIALIZER = """
from mitol.common.serializers import BaseSerializer

from myapp.models import Course


class CourseSerializer(BaseSerializer):
    required_prefetches = {required}

    class Meta:
        model = Course
        fields = {fields}

    def get_thing(self, instance):
        return {expression}
"""


def _rules(project, required="[]", expression="None", fields='["id"]'):
    project.with_models()
    return project.rules(
        project.serializer(
            _SERIALIZER.format(required=required, expression=expression, fields=fields)
        )
    )


# ------------------------------------------------------------------ #
# The coverage predicate
# ------------------------------------------------------------------ #


@pytest.mark.parametrize(
    ("method", "safe"),
    [
        ("all", True),
        ("filter", False),
        ("exclude", False),
        ("order_by", False),
        ("count", False),
        ("exists", False),
        ("first", False),
        ("last", False),
    ],
)
def test_only_cache_reading_methods_are_covered(method, safe):
    """A prefetch only helps for accesses that read its cache."""
    hit = QueryHit(
        line=1, relation_root="runs", method=method, prefetch_safe=method == "all"
    )
    assert prefetch.is_covered(("runs",), hit) is safe


def test_manager_query_is_never_covered():
    """`Model.objects.filter(...)` hangs off no relation, so nothing covers it."""
    hit = QueryHit(line=1, relation_root=None, method="filter", prefetch_safe=False)
    assert not prefetch.is_covered(("runs",), hit)


def test_undeclared_relation_is_not_covered():
    """A relation absent from the declaration is not covered."""
    hit = QueryHit(line=1, relation_root="topics", method="all", prefetch_safe=True)
    assert not prefetch.is_covered(("runs",), hit)


def test_classify_is_silent_when_everything_is_covered():
    """Fully covered access produces no violation at all."""
    hits = (QueryHit(line=1, relation_root="runs", method="all", prefetch_safe=True),)
    assert prefetch.classify(hits, ("runs",)).silent


def test_classify_suggests_the_missing_prefetch():
    """A fixable gap becomes actionable advice rather than a bare warning."""
    hits = (QueryHit(line=1, relation_root="runs", method="all", prefetch_safe=True),)
    verdict = prefetch.classify(hits, ())
    assert verdict.kind == prefetch.PREFETCH
    assert verdict.relations == ("runs",)


def test_classify_flags_what_no_prefetch_can_fix():
    """`.count()` re-queries regardless, so it is a plain violation."""
    hits = (
        QueryHit(line=1, relation_root="runs", method="count", prefetch_safe=False),
    )
    assert prefetch.classify(hits, ("runs",)).kind == prefetch.FLAG


def test_classify_without_a_contract_always_flags():
    """An ordinary serializer has nothing to check against."""
    hits = (QueryHit(line=1, relation_root="runs", method="all", prefetch_safe=True),)
    assert prefetch.classify(hits, None).kind == prefetch.FLAG


# ------------------------------------------------------------------ #
# Suppression
# ------------------------------------------------------------------ #


def test_declared_relation_silences_a_cache_safe_call(project):
    """`instance.runs.all()` is free once "runs" is declared."""
    assert _rules(project, required='["runs"]', expression="instance.runs.all()") == []


def test_declared_relation_silences_a_foreign_key_traversal(project):
    """A declared foreign key is select_related, so traversal is free."""
    assert (
        _rules(project, required='["author"]', expression="instance.author.name") == []
    )


def test_declared_relation_silences_a_covered_property(project):
    """A property whose only query reads the prefetch cache is free."""
    assert _rules(project, required='["runs"]', fields='["run_list"]') == []


def test_filter_on_a_declared_relation_still_reports(project):
    """`.filter()` builds a fresh queryset even on a prefetched manager."""
    assert _rules(
        project, required='["runs"]', expression="instance.runs.filter(x=1)"
    ) == ["ORM002"]


def test_filter_message_explains_why_the_prefetch_does_not_help(project):
    """The tailored message is what stops this reading as a false positive."""
    project.with_models()
    path = project.serializer(
        _SERIALIZER.format(
            required='["runs"]', fields='["id"]', expression="instance.runs.filter(x=1)"
        )
    )
    (violation,) = project.check(path)
    assert "is prefetched, but .filter() re-queries" in violation.message


def test_count_on_a_declared_relation_still_reports(project):
    """`.count()` issues its own SQL no matter what was prefetched."""
    assert _rules(project, required='["runs"]', fields='["run_count"]') == ["ORM005"]


# ------------------------------------------------------------------ #
# ORM007 - the relation is used but not declared
# ------------------------------------------------------------------ #


def test_orm007_undeclared_relation_in_a_method(project):
    """A cache-safe read of an undeclared relation is fixable advice."""
    assert _rules(project, expression="instance.runs.all()") == ["ORM007"]


def test_orm007_names_the_entry_to_add(project):
    """The message must be actionable, not just a warning."""
    project.with_models()
    path = project.serializer(
        _SERIALIZER.format(
            required="[]", fields='["id"]', expression="instance.runs.all()"
        )
    )
    (violation,) = project.check(path)
    assert '"runs"' in violation.message
    assert "required_prefetches" in violation.message


def test_orm007_undeclared_relation_behind_a_property(project):
    """A property reaching a coverable relation reports the fix, not ORM005."""
    assert _rules(project, fields='["run_list"]') == ["ORM007"]


def test_orm007_undeclared_foreign_key_traversal(project):
    """ORM007 supersedes ORM006 where a declaration exists to fix it."""
    assert _rules(project, expression="instance.author.name") == ["ORM007"]


def test_orm007_relation_serialized_as_a_field(project):
    """Serializing a relation reads it per object, so it needs the prefetch."""
    assert _rules(project, fields='["id", "author"]') == ["ORM007"]


def test_orm007_many_to_many_field_needs_a_prefetch(project):
    """A m2m serialized as a field needs prefetch_related just the same."""
    assert _rules(project, fields='["id", "topics"]') == ["ORM007"]


def test_orm007_declared_relation_field_is_silent(project):
    """Declaring it is exactly what makes the field safe."""
    assert _rules(project, required='["author"]', fields='["id", "author"]') == []


def test_orm007_not_applied_to_plain_serializers(project):
    """An ordinary ModelSerializer carries no contract to check against."""
    project.with_models()
    path = project.serializer(
        """
        from rest_framework import serializers

        from myapp.models import Course


        class CourseSerializer(serializers.ModelSerializer):
            class Meta:
                model = Course
                fields = ["id", "author"]
        """
    )
    assert project.rules(path) == []


def test_orm007_noqa(project):
    """`# noqa: ORM007` suppresses the violation."""
    assert _rules(project, expression="instance.runs.all()  # noqa: ORM007") == []


# ------------------------------------------------------------------ #
# ORM008 - no declaration at all
# ------------------------------------------------------------------ #


def test_orm008_missing_declaration(project):
    """BaseSerializer.__init__ would raise; say so before it is instantiated."""
    project.with_models()
    path = project.serializer(
        """
        from mitol.common.serializers import BaseSerializer

        from myapp.models import Course


        class CourseSerializer(BaseSerializer):
            class Meta:
                model = Course
                fields = ["id"]
        """
    )
    assert project.rules(path) == ["ORM008"]


def test_orm008_empty_declaration_is_enough(project):
    """An explicit empty list satisfies the contract."""
    assert _rules(project, required="[]") == []


def test_orm008_inherited_declaration_is_enough(project):
    """A project-local base may declare it on the subclass's behalf."""
    project.with_models()
    project.write(
        "myapp/base.py",
        """
        from mitol.common.serializers import BaseSerializer


        class AppSerializer(BaseSerializer):
            required_prefetches = []
        """,
    )
    path = project.serializer(
        """
        from myapp.base import AppSerializer
        from myapp.models import Course


        class CourseSerializer(AppSerializer):
            class Meta:
                model = Course
                fields = ["id"]
        """
    )
    assert project.rules(path) == []


def test_orm008_not_applied_to_plain_serializers(project):
    """Only classes carrying the contract are required to declare it."""
    project.with_models()
    path = project.serializer(
        """
        from rest_framework import serializers

        from myapp.models import Course


        class CourseSerializer(serializers.ModelSerializer):
            class Meta:
                model = Course
                fields = ["id"]
        """
    )
    assert project.rules(path) == []


def test_orm008_noqa_for_an_abstract_base(project):
    """An intermediate base that defers the declaration opts out by hand."""
    project.with_models()
    path = project.serializer(
        """
        from mitol.common.serializers import BaseSerializer


        class AppSerializer(BaseSerializer):  # noqa: ORM008
            pass
        """
    )
    assert project.rules(path) == []


# ------------------------------------------------------------------ #
# ORM009 - an entry that can never be satisfied
# ------------------------------------------------------------------ #


def test_orm009_traversal_path_is_unsatisfiable(project):
    """is_prefetched() cannot resolve "author__books", so it always raises."""
    assert _rules(project, required='["author__books"]') == ["ORM009"]


def test_orm009_plain_name_is_allowed(project):
    """django-prefetch populates arbitrary names, so a non-field is not wrong."""
    assert _rules(project, required='["something_custom"]') == []


def test_orm009_predicate():
    """The predicate is scoped to traversal paths only."""
    assert prefetch.is_unsatisfiable("author__books")
    assert not prefetch.is_unsatisfiable("author")


def test_orm009_noqa(project):
    """`# noqa: ORM009` suppresses the violation."""
    assert _rules(project, required='["author__books"]  # noqa: ORM009') == []

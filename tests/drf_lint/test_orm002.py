"""Tests for Rule ORM002: related manager queryset call inside serializer methods."""

from __future__ import annotations

from pathlib import Path

from mitol.drf_lint.checker import check_source

FIXTURES_DIR = Path(__file__).parent / "fixtures"
_MIN_FIXTURE_VIOLATIONS = 2


def _violations(source: str):
    return check_source(source)


def test_orm002_related_manager_all():
    """instance.resource_prices.all() in a serializer method is flagged as ORM002."""
    source = """
from rest_framework import serializers

class LearningPathSerializer(serializers.Serializer):
    def get_prices(self, instance):
        return [p.amount for p in instance.resource_prices.all()]
"""
    violations = _violations(source)
    assert any(v.rule == "ORM002" for v in violations)


def test_orm002_related_manager_filter():
    """instance.runs.filter() inside a serializer method is flagged as ORM002."""
    source = """
from rest_framework import serializers

class CourseSerializer(serializers.Serializer):
    def get_runs(self, instance):
        return instance.runs.filter(published=True)
"""
    violations = _violations(source)
    assert any(v.rule == "ORM002" for v in violations)


def test_orm002_chained_order_by_first():
    """instance.children.order_by().first() triggers ORM002 on the order_by call."""
    source = """
from rest_framework import serializers

class LearningPathSerializer(serializers.Serializer):
    def get_image(self, instance):
        item = instance.children.order_by("position").first()
        return item
"""
    violations = _violations(source)
    assert any(v.rule == "ORM002" for v in violations)


def test_orm002_exists_call():
    """instance.runs.exists() inside a serializer method is flagged as ORM002."""
    source = """
from rest_framework import serializers

class MySerializer(serializers.Serializer):
    def get_has_runs(self, instance):
        return instance.runs.exists()
"""
    violations = _violations(source)
    assert any(v.rule == "ORM002" for v in violations)


def test_orm002_fixture_file():
    """The bad_orm002 fixture triggers ORM002 violations (not ORM001)."""
    source = FIXTURES_DIR.joinpath("bad_orm002.py").read_text()
    violations = _violations(source)
    assert len(violations) >= _MIN_FIXTURE_VIOLATIONS
    assert all(v.rule == "ORM002" for v in violations)


def test_no_violations_in_clean_serializer():
    """A well-written serializer with no ORM calls produces no violations."""
    source = FIXTURES_DIR.joinpath("good_serializer.py").read_text()
    assert not _violations(source)


def test_orm002_no_false_positive_meta_class():
    """ORM calls inside a Meta inner class of a serializer are not flagged."""
    source = """
from rest_framework import serializers

class MySerializer(serializers.ModelSerializer):
    def get_thing(self, instance):
        return instance.related.filter(active=True)

    class Meta:
        model = MyModel
        fields = "__all__"

        def extra_method(self):
            return instance.children.all()
"""
    violations = _violations(source)
    assert len(violations) == 1
    assert violations[0].rule == "ORM002"


def test_orm002_no_false_positive_outside_serializer():
    """Queryset calls outside any serializer class are not flagged."""
    source = """
def build_queryset():
    return SomeModel.objects.all().order_by("name").filter(active=True)
"""
    assert not _violations(source)


def test_orm002_no_false_positive_single_level_attribute():
    """A single-name queryset call (not an attribute chain) is not flagged as ORM002."""
    source = """
from rest_framework import serializers

class MySerializer(serializers.Serializer):
    def get_data(self, instance):
        qs = get_queryset()
        return qs.all()
"""
    assert not _violations(source)


def test_orm002_noqa_specific_code():
    """A line with '# noqa: ORM002' suppresses the ORM002 violation on that line."""
    source = """
from rest_framework import serializers

class MySerializer(serializers.Serializer):
    def get_prices(self, instance):
        return list(instance.resource_prices.all())  # noqa: ORM002
"""
    assert not _violations(source)


def test_orm002_noqa_bare():
    """A bare '# noqa' suppresses all violations on that line."""
    source = """
from rest_framework import serializers

class MySerializer(serializers.Serializer):
    def get_prices(self, instance):
        return list(instance.resource_prices.all())  # noqa
"""
    assert not _violations(source)

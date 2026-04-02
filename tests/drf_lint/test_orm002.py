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


# ------------------------------------------------------------------ #
# Exempt write-path methods — should NOT flag
# ------------------------------------------------------------------ #


def test_orm002_exempt_validate():
    """ORM calls inside `validate` are not flagged (write-path method)."""
    source = """
from rest_framework import serializers

class MySerializer(serializers.Serializer):
    def validate(self, attrs):
        if not instance.related_items.filter(active=True).exists():
            raise serializers.ValidationError("No active items")
        return attrs
"""
    assert not _violations(source)


def test_orm002_exempt_validate_field():
    """ORM calls inside `validate_<field>` methods are not flagged (write-path)."""
    source = """
from rest_framework import serializers

class MySerializer(serializers.Serializer):
    def validate_topic(self, value):
        return value.subtopics.filter(enabled=True).first()
"""
    assert not _violations(source)


def test_orm002_exempt_create():
    """ORM calls inside `create` are not flagged (write-path method)."""
    source = """
from rest_framework import serializers

class MySerializer(serializers.ModelSerializer):
    def create(self, validated_data):
        children = validated_data.pop("children", [])
        obj = super().create(validated_data)
        for child_data in children:
            obj.children.filter(pk=child_data["pk"]).update(**child_data)
        return obj
"""
    assert not _violations(source)


def test_orm002_exempt_update():
    """ORM calls inside `update` are not flagged (write-path method)."""
    source = """
from rest_framework import serializers

class MySerializer(serializers.ModelSerializer):
    def update(self, instance, validated_data):
        instance.tags.filter(active=False).delete()
        return super().update(instance, validated_data)
"""
    assert not _violations(source)


def test_orm002_exempt_to_internal_value():
    """ORM calls inside `to_internal_value` are not flagged (write-path method)."""
    source = """
from rest_framework import serializers

class MySerializer(serializers.Serializer):
    def to_internal_value(self, data):
        result = super().to_internal_value(data)
        result["items"] = instance.items.all()
        return result
"""
    assert not _violations(source)


def test_orm002_non_exempt_method_still_flagged():
    """ORM calls in non-exempt methods (e.g., `get_*`) are still flagged."""
    source = """
from rest_framework import serializers

class MySerializer(serializers.Serializer):
    def get_children(self, instance):
        return list(instance.children.all())
"""
    violations = _violations(source)
    assert any(v.rule == "ORM002" for v in violations)


def test_orm002_nested_helper_inside_exempt_method_not_flagged():
    """A nested helper def inside an exempt method inherits the exempt state."""
    source = """
from rest_framework import serializers

class MySerializer(serializers.Serializer):
    def create(self, validated_data):
        def _sync_children(obj, items):
            return obj.children.filter(active=True).update(data=items)
        instance = super().create(validated_data)
        _sync_children(instance, validated_data.get("children", []))
        return instance
"""
    assert not _violations(source)


def test_orm002_nested_helper_inside_checked_method_is_flagged():
    """A nested helper def inside a non-exempt method is still checked."""
    source = """
from rest_framework import serializers

class MySerializer(serializers.Serializer):
    def get_summary(self, instance):
        def _count():
            return instance.runs.filter(published=True).count()
        return _count()
"""
    violations = _violations(source)
    assert any(v.rule == "ORM002" for v in violations)


def test_orm002_list_serializer_create_is_flagged():
    """create() on a ListSerializer is NOT exempt — bulk writes can have N+1."""
    source = """
from rest_framework import serializers

class MyListSerializer(serializers.ListSerializer):
    def create(self, validated_data):
        for item in validated_data:
            instance.tags.filter(active=True).delete()
"""
    violations = _violations(source)
    assert any(v.rule == "ORM002" for v in violations)


def test_orm002_list_serializer_update_is_flagged():
    """update() on a ListSerializer is NOT exempt — bulk writes can have N+1."""
    source = """
from rest_framework import serializers

class MyListSerializer(serializers.ListSerializer):
    def update(self, instance, validated_data):
        return [obj.children.all() for obj in instance]
"""
    violations = _violations(source)
    assert any(v.rule == "ORM002" for v in violations)

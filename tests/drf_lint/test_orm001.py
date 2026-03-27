"""Tests for Rule ORM001: Django manager access inside serializer methods."""

from __future__ import annotations

from pathlib import Path

from mitol.drf_lint.checker import check_source

FIXTURES_DIR = Path(__file__).parent / "fixtures"
_MIN_FIXTURE_VIOLATIONS = 2


def _violations(source: str):
    return check_source(source)


# ------------------------------------------------------------------ #
# Positive cases — should flag
# ------------------------------------------------------------------ #


def test_orm001_objects_filter():
    """Direct Model.objects.filter() inside a serializer method is flagged as ORM001."""
    source = """
from rest_framework import serializers

class UserSerializer(serializers.Serializer):
    def get_email(self, instance):
        return User.objects.filter(username=instance.username).first()
"""
    violations = _violations(source)
    assert len(violations) == 1
    assert violations[0].rule == "ORM001"


def test_orm001_objects_get():
    """Direct Model.objects.get() inside a serializer method is flagged as ORM001."""
    source = """
from rest_framework import serializers

class MySerializer(serializers.Serializer):
    def get_obj(self, instance):
        return MyModel.objects.get(pk=instance.pk)
"""
    violations = _violations(source)
    assert any(v.rule == "ORM001" for v in violations)


def test_orm001_chained_manager_call():
    """A chained manager call with filter().order_by().first() is flagged as ORM001."""
    source = """
from rest_framework import serializers

class MySerializer(serializers.Serializer):
    def get_data(self, instance):
        return MyModel.objects.filter(active=True).order_by("name").first()
"""
    violations = _violations(source)
    assert any(v.rule == "ORM001" for v in violations)


def test_orm001_fixture_file():
    """The bad_orm001 fixture triggers ORM001 violations (not ORM002)."""
    source = FIXTURES_DIR.joinpath("bad_orm001.py").read_text()
    violations = _violations(source)
    assert len(violations) >= _MIN_FIXTURE_VIOLATIONS
    assert all(v.rule == "ORM001" for v in violations)


# ------------------------------------------------------------------ #
# Negative cases — should NOT flag
# ------------------------------------------------------------------ #


def test_no_violations_in_clean_serializer():
    """A well-written serializer with no ORM calls produces no violations."""
    source = FIXTURES_DIR.joinpath("good_serializer.py").read_text()
    assert not _violations(source)


def test_orm001_no_false_positive_outside_method():
    """Module-level .objects access is not in a serializer method — not flagged."""
    source = """
from rest_framework import serializers

ADMIN_USERS = User.objects.filter(is_staff=True)  # module-level — not flagged

class MySerializer(serializers.Serializer):
    pass
"""
    assert not _violations(source)


def test_orm001_no_false_positive_non_serializer_class():
    """ORM access inside a non-serializer class is not flagged."""
    source = """
class MyView:
    def get(self, request):
        return User.objects.filter(is_staff=True)
"""
    assert not _violations(source)


def test_orm001_no_false_positive_meta_inner_class():
    """ORM access inside a Meta inner class of a serializer is not flagged."""
    source = """
from rest_framework import serializers

class MySerializer(serializers.ModelSerializer):
    class Meta:
        model = MyModel
        fields = "__all__"

        def meta_helper(self):
            return MyModel.objects.all()  # inside Meta — should NOT be flagged
"""
    assert not _violations(source)


# ------------------------------------------------------------------ #
# Suppression
# ------------------------------------------------------------------ #


def test_orm001_noqa_specific_code():
    """A line with '# noqa: ORM001' suppresses the ORM001 violation on that line."""
    source = """
from rest_framework import serializers

class MySerializer(serializers.Serializer):
    def get_obj(self, instance):
        return MyModel.objects.get(pk=instance.pk)  # noqa: ORM001
"""
    assert not _violations(source)


def test_orm001_noqa_bare():
    """A bare '# noqa' suppresses all violations on that line."""
    source = """
from rest_framework import serializers

class MySerializer(serializers.Serializer):
    def get_obj(self, instance):
        return MyModel.objects.get(pk=instance.pk)  # noqa
"""
    assert not _violations(source)


def test_orm001_noqa_different_code_does_not_suppress():
    """A '# noqa: ORM002' does NOT suppress an ORM001 violation on the same line."""
    source = """
from rest_framework import serializers

class MySerializer(serializers.Serializer):
    def get_obj(self, instance):
        return MyModel.objects.get(pk=instance.pk)  # noqa: ORM002
"""
    violations = _violations(source)
    assert any(v.rule == "ORM001" for v in violations)

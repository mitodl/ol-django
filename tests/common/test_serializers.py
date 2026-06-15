import logging

import pytest
from main.models import FirstLevel1, FirstLevel2, SecondLevel1, SecondLevel2
from mitol.common import serializers as serializers_module
from mitol.common.exceptions import (
    RequiredPrefetchesNotDefinedError,
    RequiredPrefetchMissingError,
)
from mitol.common.serializers import THIS_IS_NOT_AN_API, BaseSerializer


class _HasNoPrefetchesSerializer(BaseSerializer): ...


class _SecondLevel1Serializer(BaseSerializer):
    required_prefetches = []

    class Meta:
        model = SecondLevel1
        fields = ["id"]


class _FirstLevel1Serializer(BaseSerializer):
    required_prefetches = ["second_level"]

    second_level = _SecondLevel1Serializer()

    class Meta:
        model = FirstLevel1
        fields = ["id", "second_level"]


class _SecondLevel2Serializer(BaseSerializer):
    required_prefetches = []

    class Meta:
        model = SecondLevel2
        fields = ["id"]


class _FirstLevel2Serializer(BaseSerializer):
    required_prefetches = ["second_levels"]
    second_levels = _SecondLevel2Serializer(many=True)

    class Meta:
        model = FirstLevel2
        fields = ["id", "second_levels"]


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def test_data():
    for _ in range(5):
        second = SecondLevel1.objects.create()
        FirstLevel1.objects.create(second_level=second)
    for _ in range(5):
        first = FirstLevel2.objects.create()
        first.second_levels.set([SecondLevel2.objects.create() for _ in range(5)])


def test_serializer_defines_no_required_prefetches():
    """
    Verify the serializer errors on instantiation if required_prefetches not defined
    """
    with pytest.raises(RequiredPrefetchesNotDefinedError):
        _HasNoPrefetchesSerializer()


def test_serializer_asserts_missing_select_related(django_assert_num_queries):
    """Test that foriegn key prefetches get asserted"""
    with pytest.raises(RequiredPrefetchMissingError):
        _ = _FirstLevel1Serializer(FirstLevel1.objects.all(), many=True).data

    qs = FirstLevel1.objects.select_related("second_level")
    with django_assert_num_queries(1):
        assert _FirstLevel1Serializer(qs, many=True).data == [
            {
                "id": first.id,
                "second_level": {"id": first.second_level.id},
            }
            for first in qs
        ]


def test_serializer_asserts_missing_prefetch_related(django_assert_num_queries):
    """Test that many-to-many prefetches get asserted"""
    with pytest.raises(RequiredPrefetchMissingError):
        _ = _FirstLevel2Serializer(FirstLevel2.objects.all(), many=True).data

    qs = FirstLevel2.objects.prefetch_related("second_levels")
    with django_assert_num_queries(2):
        assert _FirstLevel2Serializer(qs, many=True).data == [
            {
                "id": first.id,
                "second_levels": [
                    {"id": second.id} for second in first.second_levels.all()
                ],
            }
            for first in qs
        ]


@pytest.fixture
def _simulate_production(settings, monkeypatch):
    """
    Make the serializer behave as it would in production: DEBUG off and not under
    a (detected) pytest run, so the prefetch guardrail warns instead of raising.
    """
    settings.DEBUG = False
    monkeypatch.setattr(serializers_module, "_running_under_pytest", lambda: False)


@pytest.mark.usefixtures("_simulate_production")
def test_serializer_warns_instead_of_raising_in_production(caplog):
    """
    Outside of development/CI/tests a missing required prefetch should not crash the
    request. Instead it logs a structured warning and serializes lazily.
    """
    qs = FirstLevel1.objects.all()

    with caplog.at_level(logging.WARNING):
        data = _FirstLevel1Serializer(qs, many=True).data

    assert data == [
        {
            "id": first.id,
            "second_level": {"id": first.second_level.id},
        }
        for first in qs
    ]

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == len(qs)
    assert "RequiredPrefetchMissing" in caplog.text
    assert "serializer=_FirstLevel1Serializer" in caplog.text
    assert "prefetch=second_level" in caplog.text
    assert f"model={FirstLevel1._meta.label}" in caplog.text  # noqa: SLF001


@pytest.mark.usefixtures("_simulate_production")
def test_serializer_prefetched_field_does_not_warn(caplog):
    """A properly prefetched field serializes without warning or raising in prod"""
    qs = FirstLevel1.objects.select_related("second_level")

    with caplog.at_level(logging.WARNING):
        data = _FirstLevel1Serializer(qs, many=True).data

    assert data == [
        {
            "id": first.id,
            "second_level": {"id": first.second_level.id},
        }
        for first in qs
    ]
    assert "RequiredPrefetchMissing" not in caplog.text


def test_serializer_asserts_escape_hatch(django_assert_num_queries):
    """Test that the escape hatch to skip prefetch checks works"""
    qs = FirstLevel2.objects.all()
    with django_assert_num_queries(11):
        assert _FirstLevel2Serializer(
            qs, many=True, context={"skip_prefetch_checks": THIS_IS_NOT_AN_API}
        ).data == [
            {
                "id": first.id,
                "second_levels": [
                    {"id": second.id} for second in first.second_levels.all()
                ],
            }
            for first in qs
        ]

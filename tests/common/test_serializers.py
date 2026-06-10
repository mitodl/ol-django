import pytest
from main.models import FirstLevel1, FirstLevel2, SecondLevel1, SecondLevel2
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

import pytest
from main.models import FirstLevel1, FirstLevel2, SecondLevel1, SecondLevel2
from mitol.common.utils.queryset import is_prefetched

pytestmark = pytest.mark.django_db


def test_is_prefetched_foreign_key():
    """Verify that is_prefetched() returns as expected"""
    FirstLevel1.objects.create(second_level=SecondLevel1.objects.create())

    assert is_prefetched(FirstLevel1.objects.all()[0], "second_level") is False
    assert (
        is_prefetched(
            FirstLevel1.objects.select_related("second_level")[0], "second_level"
        )
        is True
    )
    assert (
        is_prefetched(
            FirstLevel1.objects.prefetch_related("second_level")[0], "second_level"
        )
        is True
    )


def test_is_prefetched_many_to_many():
    """Verify that is_prefetched() returns as expected"""
    first = FirstLevel2.objects.create()
    first.second_levels.add(SecondLevel2.objects.create())

    assert is_prefetched(FirstLevel2.objects.all()[0], "second_levels") is False
    assert (
        is_prefetched(
            FirstLevel2.objects.prefetch_related("second_levels")[0], "second_levels"
        )
        is True
    )

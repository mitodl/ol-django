"""Tests for common models"""
from datetime import datetime, timedelta
from random import choice, randint, sample

import pytest
import pytz
from freezegun import freeze_time
from testapp.models import (
    AuditableTestModel,
    AuditableTestModelAudit,
    FirstLevel1,
    FirstLevel2,
    Root,
    SecondLevel1,
    SecondLevel2,
    Updateable,
)

from mitol.common.factories import UserFactory
from mitol.common.utils.serializers import serialize_model_object

pytestmark = pytest.mark.django_db


def test_prefetch_generic_related(django_assert_num_queries):
    """Test prefetch over a many-to-one relation"""
    second_levels1 = [SecondLevel1.objects.create() for _ in range(5)]
    first_levels1 = [
        FirstLevel1.objects.create(second_level=choice(second_levels1))
        for _ in range(10)
    ]

    second_levels2 = [SecondLevel2.objects.create() for _ in range(5)]
    first_levels2 = []
    for _ in range(10):
        first_level = FirstLevel2.objects.create()
        first_level.second_levels.set(sample(second_levels2, randint(1, 3)))
        first_levels2.append(first_level)

    roots = [
        Root.objects.create(content_object=choice(first_levels1)) for _ in range(5)
    ] + [Root.objects.create(content_object=choice(first_levels2)) for _ in range(5)]

    with django_assert_num_queries(0):
        # verify the prefetch is lazy
        query = Root.objects.prefetch_related(
            "content_type"  # need this to avoid N+1 on this relation
        ).prefetch_generic_related(
            "content_type",
            {
                FirstLevel1: ["content_object__second_level"],
                FirstLevel2: ["content_object__second_levels"],
            },
        )

    # 1 query each for Root, ContentType, FirstLevel1, FirstLevel2, FirstLevel1, and SecondLevel2
    with django_assert_num_queries(6):
        assert len(query) == len(roots)
        for item in query:
            if isinstance(item.content_object, FirstLevel1):
                assert item.content_object.second_level is not None
            else:
                # .all() shouldn't cause a reevaulation
                assert len(item.content_object.second_levels.all()) > 0


@pytest.mark.parametrize("pass_updated_on", [True, False])
def test_timestamped_model(pass_updated_on):
    """Verify that TimestampedModel handles update() calls correctly"""
    initial_frozen_datetime = datetime(2020, 6, 9, 12, 14, 56, tzinfo=pytz.utc)
    second_frozen_datetime = initial_frozen_datetime + timedelta(minutes=5)
    passed_updated_on = initial_frozen_datetime + timedelta(minutes=10)
    expected_updated_on = (
        passed_updated_on if pass_updated_on else second_frozen_datetime
    )

    with freeze_time(initial_frozen_datetime):
        obj = Updateable.objects.create()
    assert obj.updated_on == initial_frozen_datetime
    assert obj.created_on == initial_frozen_datetime

    with freeze_time(second_frozen_datetime):
        Updateable.objects.update(
            **(dict(updated_on=passed_updated_on) if pass_updated_on else {})
        )

    obj.refresh_from_db()

    assert obj.updated_on == expected_updated_on
    assert obj.created_on == initial_frozen_datetime


def test_auditable_model():
    """Verify that AuditableModel to_dict works correctly"""
    auditable_instance = AuditableTestModel.objects.create()
    user = UserFactory.create()
    data = auditable_instance.to_dict()
    assert serialize_model_object(auditable_instance) == data

    # Make sure audit object is created
    assert AuditableTestModelAudit.objects.count() == 0
    # auditable_instance.status = FinancialAidStatus.AUTO_APPROVED
    auditable_instance.save_and_log(user)
    assert AuditableTestModelAudit.objects.count() == 1

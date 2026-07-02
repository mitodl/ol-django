"""Tests for common models"""

from datetime import datetime, timedelta
from random import choice, randint, sample

import pytest
import pytz
from freezegun import freeze_time
from libraries.models import Author, Book, Media
from main.models import (
    AuditableTestModel,
    AuditableTestModelAudit,
    Root,
    Updateable,
)
from mitol.common.factories import UserFactory
from mitol.common.utils.serializers import serialize_model_object

pytestmark = pytest.mark.django_db


def test_prefetch_generic_related(django_assert_num_queries):
    """Test prefetch over a many-to-one relation"""
    authors = [Author.objects.create(name=f"A{i}") for i in range(5)]
    books = [
        Book.objects.create(title=f"B{i}", author=choice(authors))  # noqa: S311
        for i in range(10)
    ]

    author_pool = [Author.objects.create(name=f"MA{i}") for i in range(5)]
    medias = []
    for i in range(10):
        m = Media.objects.create(title=f"M{i}")
        m.authors.set(sample(author_pool, randint(1, 3)))  # noqa: S311
        medias.append(m)

    roots = [
        Root.objects.create(content_object=choice(books))  # noqa: S311
        for _ in range(5)
    ] + [Root.objects.create(content_object=choice(medias)) for _ in range(5)]  # noqa: S311

    with django_assert_num_queries(0):
        # verify the prefetch is lazy
        query = Root.objects.prefetch_related(
            "content_type"  # need this to avoid N+1 on this relation
        ).prefetch_generic_related(
            "content_type",
            {
                Book: ["content_object__author"],
                Media: ["content_object__authors"],
            },
        )

    # 1 query each for Root, ContentType, Book, Author (book.author FK),
    # Media, and Author (media.authors M2M)
    with django_assert_num_queries(6):
        assert len(query) == len(roots)
        for item in query:
            if isinstance(item.content_object, Book):
                assert item.content_object.author is not None
            else:
                # .all() shouldn't cause a re-evaluation
                assert len(item.content_object.authors.all()) > 0


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
            **(dict(updated_on=passed_updated_on) if pass_updated_on else {})  # noqa: C408
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
    # auditable_instance.status = FinancialAidStatus.AUTO_APPROVED  # noqa: ERA001
    auditable_instance.save_and_log(user)
    assert AuditableTestModelAudit.objects.count() == 1

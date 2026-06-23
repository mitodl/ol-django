import logging

import pytest
from libraries.models import Author, Book, Topic
from libraries.serializers import (
    BookWithAuthorSerializer,
    BookWithTopicsSerializer,
)
from mitol.common import serializers as serializers_module
from mitol.common.exceptions import (
    RequiredPrefetchesNotDefinedError,
    RequiredPrefetchMissingError,
)
from mitol.common.serializers import THIS_IS_NOT_AN_API

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def test_data():
    for i in range(5):
        author = Author.objects.create(name=f"Author {i}")
        book = Book.objects.create(title=f"Book {i}", author=author)
        book.topics.set([Topic.objects.create(name=f"Topic {i}-{t}") for t in range(5)])


def test_serializer_get_serializer_tree_path_many_related():
    """
    Verify that get_serializer_tree_path() returns the correct data
    """
    serializer = FirstLevel2Serializer()
    assert serializers_module.get_serializer_tree_path(serializer) == [
        ("FirstLevel2Serializer", None)
    ]
    # Note: `fields` MUST be accessed for this test to pass as that causes
    #       all the fields to get bound
    fields = serializer.fields
    assert serializers_module.get_serializer_tree_path(fields["second_levels"]) == [
        ("FirstLevel2Serializer", "second_levels"),
        ("SecondLevel2Serializer(many=True)", None),
    ]


def test_serializer_get_serializer_tree_path_fk():
    """
    Verify that get_serializer_tree_path() returns the correct data
    """
    serializer = FirstLevel1Serializer()
    assert serializers_module.get_serializer_tree_path(serializer) == [
        ("FirstLevel1Serializer", None)
    ]
    # Note: `fields` MUST be accessed for this test to pass as that causes
    #       all the fields to get bound
    fields = serializer.fields
    assert serializers_module.get_serializer_tree_path(fields["second_level"]) == [
        ("FirstLevel1Serializer", "second_level"),
        ("SecondLevel1Serializer", None),
    ]


def test_serializer_defines_no_required_prefetches():
    """
    Verify the serializer errors on instantiation if required_prefetches not defined
    """
    with pytest.raises(RequiredPrefetchesNotDefinedError):
        HasNoPrefetchesSerializer()


def test_serializer_asserts_missing_select_related(django_assert_num_queries):
    """Test that foreign key prefetches get asserted"""
    with pytest.raises(RequiredPrefetchMissingError):
        _ = BookWithAuthorSerializer(Book.objects.all(), many=True).data

    qs = Book.objects.select_related("author")
    with django_assert_num_queries(1):
        assert BookWithAuthorSerializer(qs, many=True).data == [
            {
                "id": book.id,
                "author": {"id": book.author.id},
            }
            for book in qs
        ]


def test_serializer_asserts_missing_prefetch_related(django_assert_num_queries):
    """Test that many-to-many prefetches get asserted"""
    with pytest.raises(RequiredPrefetchMissingError):
        _ = BookWithTopicsSerializer(Book.objects.all(), many=True).data

    qs = Book.objects.prefetch_related("topics")
    with django_assert_num_queries(2):
        assert BookWithTopicsSerializer(qs, many=True).data == [
            {
                "id": book.id,
                "topics": [{"id": topic.id} for topic in book.topics.all()],
            }
            for book in qs
        ]


@pytest.fixture
def _simulate_production(settings, monkeypatch):
    """
    Make the serializer behave as it would in production: DEBUG off and not under
    a (detected) pytest run, so the prefetch guardrail logs instead of raising.
    """
    settings.DEBUG = False
    monkeypatch.setattr(serializers_module, "_running_under_pytest", lambda: False)


@pytest.mark.usefixtures("_simulate_production")
def test_serializer_logs_error_instead_of_raising_in_production(caplog):
    """
    Outside of development/CI/tests a missing required prefetch should not crash the
    request. Instead it logs a structured error and serializes lazily.
    """
    qs = Book.objects.all()

    with caplog.at_level(logging.ERROR):
        data = BookWithAuthorSerializer(qs, many=True).data

    assert data == [
        {
            "id": book.id,
            "author": {"id": book.author.id},
        }
        for book in qs
    ]

    expected_message = (
        "RequiredPrefetchMissing: serializer=BookWithAuthorSerializer "
        f"prefetch=author model={Book._meta.label}"  # noqa: SLF001
    )
    assert [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR] == [
        expected_message
    ] * len(qs)


@pytest.mark.usefixtures("_simulate_production")
def test_serializer_prefetched_field_does_not_log_error(caplog):
    """A properly prefetched field serializes without logging or raising in prod"""
    qs = Book.objects.select_related("author")

    with caplog.at_level(logging.ERROR):
        data = BookWithAuthorSerializer(qs, many=True).data

    assert data == [
        {
            "id": book.id,
            "author": {"id": book.author.id},
        }
        for book in qs
    ]
    assert "RequiredPrefetchMissing" not in caplog.text


def test_serializer_asserts_escape_hatch(django_assert_num_queries):
    """Test that the escape hatch to skip prefetch checks works"""
    qs = Book.objects.all()
    with django_assert_num_queries(11):
        assert BookWithTopicsSerializer(
            qs, many=True, context={"skip_prefetch_checks": THIS_IS_NOT_AN_API}
        ).data == [
            {
                "id": book.id,
                "topics": [{"id": topic.id} for topic in book.topics.all()],
            }
            for book in qs
        ]

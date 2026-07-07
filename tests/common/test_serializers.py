import ast
import logging

import pytest
from libraries.factories import (
    BookFactory,
    MediaFactory,
    PeriodicalFactory,
    RecommendationFactory,
)
from libraries.models import Author, Book, Media, Periodical, Recommendation, Topic
from libraries.serializers import (
    BookSerializer,
    MediaSerializer,
    PeriodicalSerializer,
    RecommendationSerializer,
)
from mitol.common import serializers as serializers_module
from mitol.common.exceptions import (
    GenericObjectSerializerMissingError,
    RequiredPrefetchesNotDefinedError,
    RequiredPrefetchMissingError,
)
from mitol.common.serializers import (
    THIS_IS_NOT_AN_API,
    BaseSerializer,
    GenericObjectField,
)

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
    serializer = BookSerializer()
    assert serializers_module.get_serializer_tree_path(serializer) == [
        ("BookSerializer", None)
    ]
    # Note: `fields` MUST be accessed for this test to pass as that causes
    #       all the fields to get bound
    fields = serializer.fields
    assert serializers_module.get_serializer_tree_path(fields["topics"]) == [
        ("BookSerializer", "topics"),
        ("TopicSerializer(many=True)", None),
    ]


def test_serializer_get_serializer_tree_path_fk():
    """
    Verify that get_serializer_tree_path() returns the correct data
    """
    serializer = BookSerializer()
    assert serializers_module.get_serializer_tree_path(serializer) == [
        ("BookSerializer", None)
    ]
    # Note: `fields` MUST be accessed for this test to pass as that causes
    #       all the fields to get bound
    fields = serializer.fields
    assert serializers_module.get_serializer_tree_path(fields["author"]) == [
        ("BookSerializer", "author"),
        ("AuthorSerializer", None),
    ]


def test_serializer_defines_no_required_prefetches():
    """
    Verify the serializer errors on instantiation if required_prefetches not defined
    """

    class _MissingPrefetchesSerializer(BaseSerializer): ...

    with pytest.raises(RequiredPrefetchesNotDefinedError):
        _MissingPrefetchesSerializer()


def test_serializer_asserts_missing_select_related(django_assert_num_queries):
    """Test that foreign key prefetches get asserted"""
    with pytest.raises(RequiredPrefetchMissingError):
        _ = BookSerializer(Book.objects.all(), many=True).data

    qs = Book.objects.select_related("author").prefetch_related("topics")
    with django_assert_num_queries(2):
        assert BookSerializer(qs, many=True).data == [
            {
                "id": book.id,
                "title": book.title,
                "author": {"id": book.author.id, "name": book.author.name},
                "topics": [{"id": t.id, "name": t.name} for t in book.topics.all()],
            }
            for book in qs
        ]


def test_serializer_asserts_missing_prefetch_related(django_assert_num_queries):
    """Test that many-to-many prefetches get asserted"""
    with pytest.raises(RequiredPrefetchMissingError):
        _ = BookSerializer(Book.objects.select_related("author"), many=True).data

    qs = Book.objects.select_related("author").prefetch_related("topics")
    with django_assert_num_queries(2):
        assert BookSerializer(qs, many=True).data == [
            {
                "id": book.id,
                "title": book.title,
                "author": {"id": book.author.id, "name": book.author.name},
                "topics": [{"id": t.id, "name": t.name} for t in book.topics.all()],
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
    # author is prefetched via select_related; topics is not — exactly one error per book
    qs = Book.objects.select_related("author")

    with caplog.at_level(logging.ERROR):
        data = BookSerializer(qs, many=True).data

    error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(error_records) == len(list(qs))
    for record in error_records:
        log_data = ast.literal_eval(record.getMessage())
        assert log_data["event"] == "A required prefetch is missing"
        assert log_data["serializers"] == "BookSerializer"
        assert log_data["prefetch"] == "topics"
        assert log_data["model"] == Book._meta.label  # noqa: SLF001

    assert data == [
        {
            "id": book.id,
            "title": book.title,
            "author": {"id": book.author.id, "name": book.author.name},
            "topics": [{"id": t.id, "name": t.name} for t in book.topics.all()],
        }
        for book in qs
    ]


@pytest.mark.usefixtures("_simulate_production")
def test_serializer_prefetched_field_does_not_log_error(caplog):
    """A properly prefetched field serializes without logging or raising in prod"""
    qs = Book.objects.select_related("author").prefetch_related("topics")

    with caplog.at_level(logging.ERROR):
        data = BookSerializer(qs, many=True).data

    assert data == [
        {
            "id": book.id,
            "title": book.title,
            "author": {"id": book.author.id, "name": book.author.name},
            "topics": [{"id": t.id, "name": t.name} for t in book.topics.all()],
        }
        for book in qs
    ]
    assert "A required prefetch is missing" not in caplog.text


def test_serializer_asserts_escape_hatch(django_assert_num_queries):
    """Test that the escape hatch to skip prefetch checks works"""
    qs = Book.objects.all()
    with django_assert_num_queries(11):
        data = BookSerializer(
            qs, many=True, context={"skip_prefetch_checks": THIS_IS_NOT_AN_API}
        ).data
    assert data == [
        {
            "id": book.id,
            "title": book.title,
            "author": {"id": book.author.id, "name": book.author.name},
            "topics": [{"id": t.id, "name": t.name} for t in book.topics.all()],
        }
        for book in qs
    ]


# ---------------------------------------------------------------------------
# GenericObjectField tests
# ---------------------------------------------------------------------------

_SKIP_PREFETCH = {"skip_prefetch_checks": THIS_IS_NOT_AN_API}


def test_generic_object_field_dispatches_book():
    """RecommendationSerializer routes to BookSerializer for a Book content object"""
    book = BookFactory.create()
    rec = RecommendationFactory.create(content_object=book)
    data = RecommendationSerializer(rec, context=_SKIP_PREFETCH).data
    assert data == {
        "id": rec.id,
        "recommended": {
            "id": book.id,
            "title": book.title,
            "author": {"id": book.author.id, "name": book.author.name},
            "topics": [],
        },
    }


def test_generic_object_field_dispatches_media():
    """RecommendationSerializer routes to MediaSerializer for a Media content object"""
    media = MediaFactory.create()
    rec = RecommendationFactory.create(content_object=media)
    data = RecommendationSerializer(rec, context=_SKIP_PREFETCH).data
    assert data == {
        "id": rec.id,
        "recommended": {
            "id": media.id,
            "title": media.title,
            "authors": [],
        },
    }


def test_generic_object_field_dispatches_periodical():
    """RecommendationSerializer routes to PeriodicalSerializer for a Periodical content object"""
    periodical = PeriodicalFactory.create()
    rec = RecommendationFactory.create(content_object=periodical)
    data = RecommendationSerializer(rec, context=_SKIP_PREFETCH).data
    assert data == {
        "id": rec.id,
        "recommended": {
            "id": periodical.id,
            "title": periodical.title,
            "authors": [],
        },
    }


def test_generic_object_field_serializer_mapping_kwarg():
    """serializer_mapping passed as a constructor kwarg is equivalent to the subclass pattern"""

    class InlineRecommendationSerializer(BaseSerializer):
        required_prefetches = ["content_object"]
        recommended = GenericObjectField(
            source="content_object",
            serializer_mapping={
                Book: BookSerializer(read_only=True),
                Media: MediaSerializer(read_only=True),
                Periodical: PeriodicalSerializer(read_only=True),
            },
        )

        class Meta:
            model = Recommendation
            fields = ["id", "recommended"]

    book = BookFactory.create()
    rec = RecommendationFactory.create(content_object=book)
    assert InlineRecommendationSerializer(rec, context=_SKIP_PREFETCH).data == (
        RecommendationSerializer(rec, context=_SKIP_PREFETCH).data
    )


def test_generic_object_field_raises_for_unmapped_type():
    """to_representation raises GenericObjectSerializerMissingError for an unmapped model type"""
    field = GenericObjectField(serializer_mapping={})
    with pytest.raises(GenericObjectSerializerMissingError):
        field.to_representation(BookFactory.create())

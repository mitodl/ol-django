from http import HTTPStatus

import pytest
from django.urls import reverse
from libraries.factories import (
    AuthorFactory,
    BookFactory,
    LibraryFactory,
    MediaFactory,
    RecommendationFactory,
    RecommendationListFactory,
    TopicFactory,
)

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Book API
# ---------------------------------------------------------------------------


def test_book_list(learner_drf_client):
    author = AuthorFactory.create()
    topic = TopicFactory.create()
    book = BookFactory.create(author=author)
    book.topics.set([topic])

    resp = learner_drf_client.get(reverse("book-list"))

    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == [
        {
            "id": book.id,
            "title": book.title,
            "author": {"id": author.id, "name": author.name},
            "topics": [{"id": topic.id, "name": topic.name}],
        }
    ]


def test_book_detail(learner_drf_client):
    author = AuthorFactory.create()
    book = BookFactory.create(author=author)

    resp = learner_drf_client.get(reverse("book-detail", kwargs={"pk": book.pk}))

    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {
        "id": book.id,
        "title": book.title,
        "author": {"id": author.id, "name": author.name},
        "topics": [],
    }


def test_book_detail_not_found(learner_drf_client):
    resp = learner_drf_client.get(reverse("book-detail", kwargs={"pk": 999999}))
    assert resp.status_code == HTTPStatus.NOT_FOUND


# ---------------------------------------------------------------------------
# Library API
# ---------------------------------------------------------------------------


def test_library_list(learner_drf_client):
    library = LibraryFactory.create()

    resp = learner_drf_client.get(reverse("library-list"))

    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == [{"id": library.id, "name": library.name}]


def test_library_detail(learner_drf_client):
    library = LibraryFactory.create()

    resp = learner_drf_client.get(reverse("library-detail", kwargs={"pk": library.pk}))

    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {"id": library.id, "name": library.name}


def test_library_detail_not_found(learner_drf_client):
    resp = learner_drf_client.get(reverse("library-detail", kwargs={"pk": 999999}))
    assert resp.status_code == HTTPStatus.NOT_FOUND


# ---------------------------------------------------------------------------
# RecommendationList API
# ---------------------------------------------------------------------------


def test_recommendation_list_list(learner_drf_client):
    book = BookFactory.create()
    rec = RecommendationFactory.create(content_object=book)
    rec_list = RecommendationListFactory.create()
    rec_list.recommendations.set([rec])

    resp = learner_drf_client.get(reverse("recommendationlist-list"))

    assert resp.status_code == HTTPStatus.OK
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == rec_list.id
    assert data[0]["title"] == rec_list.title
    assert len(data[0]["recommendations"]) == 1
    assert data[0]["recommendations"][0]["id"] == rec.id


def test_recommendation_list_detail(learner_drf_client):
    media = MediaFactory.create()
    rec = RecommendationFactory.create(content_object=media)
    rec_list = RecommendationListFactory.create()
    rec_list.recommendations.set([rec])

    resp = learner_drf_client.get(
        reverse("recommendationlist-detail", kwargs={"pk": rec_list.pk})
    )

    assert resp.status_code == HTTPStatus.OK
    data = resp.json()
    assert data["id"] == rec_list.id
    assert data["title"] == rec_list.title
    assert data["recommendations"][0]["recommended"]["id"] == media.id
    assert data["recommendations"][0]["recommended"]["title"] == media.title


def test_recommendation_list_detail_not_found(learner_drf_client):
    resp = learner_drf_client.get(
        reverse("recommendationlist-detail", kwargs={"pk": 999999})
    )
    assert resp.status_code == HTTPStatus.NOT_FOUND

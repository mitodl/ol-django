import pytest
from django.urls import reverse
from libraries.factories import LibraryFactory


@pytest.mark.django_db
def test_list_view(client, django_assert_max_num_queries):
    libraries = LibraryFactory.create_batch(5)

    with django_assert_max_num_queries(4):
        resp = client.get(reverse("libraries_api-list"))

    assert resp.json() == [
        {
            "name": library.name,
            "books": [
                {
                    "title": book.title,
                    "author": {
                        "name": book.author.name,
                    },
                    "also_the_author": {
                        "name": book.author.name,
                    },
                }
                for book in library.books.order_by("id")
            ],
        }
        for library in libraries
    ]

import pytest
from libraries.models import Author, Book, Topic
from mitol.common.utils.queryset import is_prefetched

pytestmark = pytest.mark.django_db


def test_is_prefetched_foreign_key():
    """Verify that is_prefetched() returns as expected"""
    Book.objects.create(title="B", author=Author.objects.create(name="A"))

    assert is_prefetched(Book.objects.all()[0], "author") is False
    assert is_prefetched(Book.objects.select_related("author")[0], "author") is True
    assert is_prefetched(Book.objects.prefetch_related("author")[0], "author") is True


def test_is_prefetched_many_to_many():
    """Verify that is_prefetched() returns as expected"""
    author = Author.objects.create(name="A")
    book = Book.objects.create(title="B", author=author)
    book.topics.add(Topic.objects.create(name="T"))

    assert is_prefetched(Book.objects.all()[0], "topics") is False
    assert is_prefetched(Book.objects.prefetch_related("topics")[0], "topics") is True

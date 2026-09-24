from mitol.common.serializers import BaseSerializer

from libraries.models import Author, Book, Library, Topic


class AuthorSerializer(BaseSerializer):
    required_prefetches = []

    class Meta:
        model = Author
        fields = ["id"]


class TopicSerializer(BaseSerializer):
    required_prefetches = []

    class Meta:
        model = Topic
        fields = ["id"]


class BookWithAuthorSerializer(BaseSerializer):
    required_prefetches = ["author"]

    author = AuthorSerializer()

    class Meta:
        model = Book
        fields = ["id", "author"]


class BookWithTopicsSerializer(BaseSerializer):
    required_prefetches = ["topics"]

    topics = TopicSerializer(many=True)

    class Meta:
        model = Book
        fields = ["id", "topics"]


class BookSerializer(BaseSerializer):
    """A book with everything the library list endpoint nests under it."""

    required_prefetches = ["author", "topics"]

    author = AuthorSerializer()
    topics = TopicSerializer(many=True)

    class Meta:
        model = Book
        fields = ["id", "title", "author", "topics"]


class LibrarySerializer(BaseSerializer):
    """A library and its books — the shape mitol-django-benchmark exercises."""

    required_prefetches = ["books"]

    books = BookSerializer(many=True)

    class Meta:
        model = Library
        fields = ["id", "name", "books"]

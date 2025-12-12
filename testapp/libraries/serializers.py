from mitol.common.serializers import QuerySetSerializer

from libraries.models import Author, Book, Library


class AuthorSerializer(QuerySetSerializer):
    class Meta:
        fields = ("name",)
        model = Author


class BookSerializer(QuerySetSerializer):
    author = AuthorSerializer()
    also_the_author = AuthorSerializer(source="author")

    class Meta:
        fields = ("title", "author", "also_the_author")
        model = Book


class LibrarySerializer(QuerySetSerializer):
    books = BookSerializer(many=True, queryset=Book.objects.order_by("id"))

    class Meta:
        fields = (
            "name",
            "books",
        )
        model = Library

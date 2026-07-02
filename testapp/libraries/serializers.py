from mitol.common.serializers import BaseSerializer

from libraries.models import Author, Book, Topic


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

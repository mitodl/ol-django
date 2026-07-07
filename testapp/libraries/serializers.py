from mitol.common.serializers import BaseSerializer, GenericObjectField

from libraries.models import (
    Author,
    Book,
    Library,
    Media,
    Periodical,
    Recommendation,
    RecommendationList,
    Topic,
)


class AuthorSerializer(BaseSerializer):
    required_prefetches = []

    class Meta:
        model = Author
        fields = ["id", "name"]


class TopicSerializer(BaseSerializer):
    required_prefetches = []

    class Meta:
        model = Topic
        fields = ["id", "name"]


class BookSerializer(BaseSerializer):
    required_prefetches = ["author", "topics"]

    author = AuthorSerializer()
    topics = TopicSerializer(many=True)

    class Meta:
        model = Book
        fields = ["id", "title", "author", "topics"]


class MediaSerializer(BaseSerializer):
    required_prefetches = ["authors"]

    authors = AuthorSerializer(many=True)

    class Meta:
        model = Media
        fields = ["id", "title", "authors"]


class PeriodicalSerializer(BaseSerializer):
    required_prefetches = ["authors"]

    authors = AuthorSerializer(many=True)

    class Meta:
        model = Periodical
        fields = ["id", "title", "authors"]


class RecommendedObjectField(GenericObjectField):
    serializer_mapping = {
        Book: BookSerializer(read_only=True),
        Media: MediaSerializer(read_only=True),
        Periodical: PeriodicalSerializer(read_only=True),
    }


class RecommendationSerializer(BaseSerializer):
    required_prefetches = ["content_object"]
    recommended = RecommendedObjectField(source="content_object")

    class Meta:
        model = Recommendation
        fields = ["id", "recommended"]


class LibrarySerializer(BaseSerializer):
    required_prefetches = []

    class Meta:
        model = Library
        fields = ["id", "name"]


class RecommendationListSerializer(BaseSerializer):
    required_prefetches = ["recommendations"]

    recommendations = RecommendationSerializer(many=True)

    class Meta:
        model = RecommendationList
        fields = ["id", "title", "recommendations"]

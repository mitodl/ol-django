from mitol.common.serializers import THIS_IS_NOT_AN_API
from rest_framework.viewsets import ReadOnlyModelViewSet

from libraries.models import Book, Library, RecommendationList
from libraries.serializers import (
    BookSerializer,
    LibrarySerializer,
    RecommendationListSerializer,
)


class LibraryViewSet(ReadOnlyModelViewSet):
    serializer_class = LibrarySerializer
    queryset = Library.objects.all()


class BookViewSet(ReadOnlyModelViewSet):
    serializer_class = BookSerializer
    queryset = Book.objects.select_related("author").prefetch_related("topics")


class RecommendationListViewSet(ReadOnlyModelViewSet):
    serializer_class = RecommendationListSerializer
    queryset = RecommendationList.objects.prefetch_related(
        "recommendations",
        "recommendations__content_object",
    )

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        # BookSerializer/MediaSerializer/PeriodicalSerializer inside RecommendedObjectField
        # each declare their own required_prefetches (author, topics, authors).
        # Satisfying those through a GenericForeignKey chain requires complex per-content-type
        # Prefetch objects; for this testapp we bypass the inner check instead.
        ctx["skip_prefetch_checks"] = THIS_IS_NOT_AN_API
        return ctx

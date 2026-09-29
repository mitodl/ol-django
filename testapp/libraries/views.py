"""
A list endpoint with nested collections, for benchmarking against.

The libraries app exists to give the tooling in this repository something
realistically shaped to work on: `mitol-drf-lint` reads its serializers, and
`mitol-django-benchmark` measures this endpoint. A library nests books, and
each book nests an author and a list of topics, so the response has the join
fan-out that makes prefetching decisions matter.
"""

from rest_framework.pagination import PageNumberPagination
from rest_framework.viewsets import ReadOnlyModelViewSet

from libraries.models import Library
from libraries.serializers import LibrarySerializer


class LibraryPagination(PageNumberPagination):
    """Page size the benchmark can vary from the query string."""

    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 500


class LibraryViewSet(ReadOnlyModelViewSet):
    """Read-only libraries, with their books prefetched."""

    serializer_class = LibrarySerializer
    pagination_class = LibraryPagination
    queryset = (
        Library.objects.prefetch_related("books__author", "books__topics")
        .order_by("id")
        .all()
    )

from collections.abc import Callable

from django.db.models import Prefetch, QuerySet
from django.http import HttpRequest
from rest_framework import serializers


class QuerySetSerializer(serializers.ModelSerializer):
    """
    A serializer for serializing QuerySets.

    This provides more functionality over ModelSerializer by implementing functionality
    analogous to ViewSet's queryset and get_queryset. It recursively constructucts a
    QuerySet that has been annotated and prefetched appropriately to fulfill serializers
    without incurring further queries during serialization

    Subclasses can set either queryset or override `get_queryset` if access
    to `request` is needed.

    Optionally when the `QuerySetSerializer` is initialized `queryset` can be passed
    and this will override both `queryset` and `get_queryset`.
    """

    queryset: QuerySet | None = None

    def get_base_queryset(self, request: HttpRequest) -> QuerySet:  # noqa: ARG002
        # critical to compare against None to avoid an evaluation
        return (
            self.queryset
            if self.queryset is not None
            else self.Meta.model.objects.all()
        )

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        """
        Get the queryset for this serializer

        Override this method to customize the queryset used for fetching models
        to be serialized.

        It is *highly* recommended that you call `super().get_queryset(request)` and
        extend the return value.

        If you need to customize the queryset used for a nested serializer field, define
        a `get_{field_name}_queryset` with the following signature:

        `
        def get_books_queryset(
            self,
            queryset: QuerySet,
            request: HttpRequest
        ) -> QuerySet:
            ...
        `

        It is *highly* recommended that you extend the queryset passed in so you get the
        prefetches defined on the nested serializer too. This function is mainly used
        for things like altering the sorting.

        """
        return self.get_base_queryset(request)

    def get_prefetch_for_field(
        self,
        name: str,
        field: serializers.Field,
        serializer: "QuerySetSerializer",
        request: HttpRequest,
    ) -> Prefetch:
        queryset = serializer.get_queryset_tree(request)

        get_serializer_queryset_func = getattr(self, f"get_{name}_queryset", None)

        if get_serializer_queryset_func is not None and isinstance(
            get_serializer_queryset_func,
            Callable,
        ):
            queryset = get_serializer_queryset_func(queryset, request)

        return Prefetch(
            field.source,
            queryset=queryset,
            to_attr=name if name != field.source else None,
        )

    def get_queryset_tree(self, request: HttpRequest) -> QuerySet:
        """Get the queryset required for the serializer"""
        queryset = self.get_queryset(request)

        for name, field in self.fields.items():
            serializer = field

            if isinstance(field, serializers.ListSerializer):
                serializer = field.child

            if isinstance(serializer, QuerySetSerializer):
                queryset = queryset.prefetch_related(
                    self.get_prefetch_for_field(name, field, serializer, request)
                )

        return queryset

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
    _init_queryset: QuerySet | Callable[[HttpRequest], QuerySet] | None = None

    def __init__(
        self,
        *args,
        queryset: QuerySet | Callable[[HttpRequest], QuerySet] | None = None,
        **kwargs,
    ):
        self._init_queryset = queryset

        if queryset is not None and not (isinstance(queryset, Callable | QuerySet)):
            msg = (
                "Expected `queryset` to be a Callable or QuerySet, got: "
                f"{type(queryset)}"
            )
            raise TypeError(msg)

        super().__init__(*args, **kwargs)

    def get_base_queryset(self, request: HttpRequest) -> QuerySet:
        # critical to compare against None to avoid an evaluation
        if self._init_queryset is not None:
            if isinstance(self._init_queryset, Callable):
                return self._init_queryset(request)
            else:
                return self._init_queryset

        # critical to compare against None to avoid an evaluation
        return (
            self.queryset
            if self.queryset is not None
            else self.Meta.model.objects.all()
        )

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return self.get_base_queryset(request)

    def get_prefetch_for_field(
        self,
        name: str,
        field: serializers.Field,
        serializer: "QuerySetSerializer",
        request: HttpRequest,
    ) -> Prefetch:
        return Prefetch(
            field.source,
            queryset=serializer.get_queryset_tree(request),
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

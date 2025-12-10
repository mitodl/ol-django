import logging

from mitol.common.serializers import QuerySetSerializer

log = logging.getLogger()


class PrefetchQuerySetSerializerMixin:
    """
    APIView mixin that derives prefetches from the serializer(s) used to
    render responses.

    This allows for the prefetches to be specific to what we intend to serialize
    to JSON and it also allows this to vary if the serializer_class that is used
    also varies.
    """

    def get_queryset(self):
        """Get the queryset"""
        serializer_class = self.get_serializer_class()

        if not issubclass(serializer_class, QuerySetSerializer):
            log.error(
                "Serializer %s does not subclass QuerySetSerializer, skipping",
                serializer_class,
            )

            return super().get_queryset()

        # `self.queryset` defaults to None
        serializer = serializer_class(queryset=self.queryset)

        return serializer.get_queryset_tree(self.request)

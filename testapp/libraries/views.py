from mitol.common.views import PrefetchQuerySetSerializerMixin
from rest_framework import viewsets

from libraries.models import Library
from libraries.serializers import LibrarySerializer


class LibrariesViewSet(PrefetchQuerySetSerializerMixin, viewsets.ModelViewSet):
    serializer_class = LibrarySerializer
    queryset = Library.objects.all()

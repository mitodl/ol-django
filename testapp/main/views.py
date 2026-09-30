"""Test views"""

from django.http import HttpResponse
from mitol.digitalcredentials.mixins import DigitalCredentialsRequestViewSetMixin
from rest_framework.viewsets import ModelViewSet

from main.models import DemoCourseware


def noop(_request):
    """
    Answer a fixed string, so the retention pass has a view that does nothing.

    `mitol-django-benchmark`'s memory mode has to be able to demonstrate a
    `stable` verdict on an endpoint that cannot possibly retain anything, so
    that what it reports is the endpoint's retention and not the test client's.
    """
    return HttpResponse("ok")


class DemoCoursewareViewSet(ModelViewSet, DigitalCredentialsRequestViewSetMixin):
    """Demo model view"""

    queryset = DemoCourseware.objects.all()

    def get_learner_for_obj(self, credentialed_object: DemoCourseware):
        """Get the learner for a credentials object"""
        return credentialed_object.learner

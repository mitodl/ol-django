"""Test views"""
from rest_framework.viewsets import ModelViewSet

from mitol.digitalcredentials.mixins import DigitalCredentialsRequestViewSetMixin
from testapp.models import DemoCourseware


class DemoCoursewareViewSet(ModelViewSet, DigitalCredentialsRequestViewSetMixin):
    """Demo model view"""

    queryset = DemoCourseware.objects.all()

    def get_learner_for_obj(self, credentialed_object):
        return credentialed_object.learner

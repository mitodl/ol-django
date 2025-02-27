"""Test views"""

from mitol.digitalcredentials.mixins import DigitalCredentialsRequestViewSetMixin
from rest_framework.viewsets import ModelViewSet

from main.models import DemoCourseware


class DemoCoursewareViewSet(ModelViewSet, DigitalCredentialsRequestViewSetMixin):
    """Demo model view"""

    queryset = DemoCourseware.objects.all()

    def get_learner_for_obj(self, credentialed_object: DemoCourseware):
        """Get the learner for a credentials object"""
        return credentialed_object.learner

"""Test factories"""
from factory import SubFactory
from factory.django import DjangoModelFactory

from mitol.common.factories import UserFactory
from mitol.digitalcredentials.factories import (
    DigitalCredentialFactory,
    DigitalCredentialRequestFactory,
)
from testapp.models import DemoCourseware


class DemoCoursewareFactory(DjangoModelFactory):
    """Factory for DemoCourseware"""

    learner = SubFactory(UserFactory)

    class Meta:
        model = DemoCourseware


class DemoCoursewareDigitalCredentialFactory(DigitalCredentialFactory):
    """Factory for a DigitalCredential of DemoCourseware"""

    credentialed_object = SubFactory(DemoCoursewareFactory)


class DemoCoursewareDigitalCredentialRequestFactory(DigitalCredentialRequestFactory):
    """Factory for a DigitalCredentialRequest of DemoCourseware"""

    credentialed_object = SubFactory(DemoCoursewareFactory)

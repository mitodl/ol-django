"""Testapp model tests"""
import pytest

from mitol.digitalcredentials.factories import (
    DigitalCredentialFactory,
    DigitalCredentialRequestFactory,
    LearnerDIDFactory,
)
from testapp.factories import (
    DemoCoursewareDigitalCredentialFactory,
    DemoCoursewareDigitalCredentialRequestFactory,
)


pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "factory",
    [
        DemoCoursewareDigitalCredentialFactory,
        DemoCoursewareDigitalCredentialRequestFactory,
        LearnerDIDFactory,
    ],
)
def test_model_str(factory):
    """Verify model __str__ methods don't raise exceptions"""
    instance = factory.create()
    str(instance)  # shouldn't throw an exception

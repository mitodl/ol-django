"""Models tests"""

from hashlib import sha256

import pytest
from main.factories import (
    DemoCoursewareDigitalCredentialFactory,
    DemoCoursewareDigitalCredentialRequestFactory,
)
from mitol.digitalcredentials.factories import LearnerDIDFactory

pytestmark = pytest.mark.django_db


def test_learner_did_hash():
    """Test that the DID gets hashed on save()"""
    learner_did = LearnerDIDFactory.create()

    assert learner_did.did_sha256 == sha256(learner_did.did.encode("ascii")).hexdigest()


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

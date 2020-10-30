"""Models tests"""
# Models require an installed app, so most of the tests are instead in:
#   mitol-django-digitalcredentials/testapp/models_test.py
from hashlib import sha256

import pytest

from mitol.digitalcredentials.factories import LearnerDIDFactory


pytestmark = pytest.mark.django_db


def test_learner_did_hash():
    """Test that the DID gets hashed on save()"""
    learner_did = LearnerDIDFactory.create()

    assert learner_did.did_sha256 == sha256(learner_did.did.encode("ascii")).hexdigest()

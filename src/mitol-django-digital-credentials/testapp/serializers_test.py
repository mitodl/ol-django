"""Digital Credentials serializers"""
import json

import pytest
import responses

from mitol.common.factories import UserFactory
from mitol.digitalcredentials.factories import LearnerDIDFactory
from mitol.digitalcredentials.models import DigitalCredential, LearnerDID
from mitol.digitalcredentials.serializers import DigitalCredentialRequestSerializer
from testapp.factories import DemoCoursewareDigitalCredentialRequestFactory


pytestmark = pytest.mark.django_db


@responses.activate
@pytest.mark.parametrize("learner_did_exists", [True, False])
def test_digital_credential_request_serializer(learner_did_exists):
    """Verify that the serializer updates successfully"""
    did = "did:example:12345"
    learner = UserFactory.create()
    request = DemoCoursewareDigitalCredentialRequestFactory.create(learner=learner)

    if learner_did_exists:
        LearnerDID.objects.create(learner=learner, did=did)

    response_json = {"result": True}
    responses.add(
        responses.POST,
        "http://localhost:5000/verify/presentations",
        json={},
        status=200,
    )
    responses.add(
        responses.POST,
        "http://localhost:5000/issue/credentials",
        json=response_json,
        status=200,
    )

    serializer = DigitalCredentialRequestSerializer(request, data={"id": did,})
    serializer.is_valid(raise_exception=True)

    result = serializer.save()

    learner_did = LearnerDID.objects.get(learner=learner, did=did)

    assert isinstance(result, DigitalCredential)
    assert result.courseware_object == request.courseware_object
    assert result.learner == learner
    assert result.learner_did == learner_did
    assert json.loads(result.credential_json) == response_json

    request.refresh_from_db()
    assert request.consumed is True


@responses.activate
def test_digital_credential_request_serializer_other_user_did():
    learner = UserFactory.create()
    learner_did = LearnerDIDFactory.create()
    request = DemoCoursewareDigitalCredentialRequestFactory.create(learner=learner)

    responses.add(
        responses.POST,
        "http://localhost:5000/verify/presentations",
        json={},
        status=200,
    )
    serializer = DigitalCredentialRequestSerializer(
        request, data={"id": learner_did.did,}
    )
    assert serializer.is_valid() is False
    assert serializer.errors == {"id": ["DID is associated with someone else"]}


@responses.activate
def test_digital_credential_request_serializer_presentation_verify_failed():
    learner_did = LearnerDIDFactory.create()
    request = DemoCoursewareDigitalCredentialRequestFactory.create(
        learner=learner_did.learner
    )

    responses.add(
        responses.POST,
        "http://localhost:5000/verify/presentations",
        json={},
        status=400,
    )
    serializer = DigitalCredentialRequestSerializer(
        request, data={"id": learner_did.did,}
    )
    assert serializer.is_valid() is False
    assert serializer.errors == {
        "non_field_errors": ["Unable to verify digital credential presentation"]
    }


@responses.activate
def test_digital_credential_request_serializer_error():
    """Verify that the serializer doesn't modify state if there's an upstream error"""
    learner = UserFactory.create()
    learner_did = LearnerDIDFactory.create(learner=learner)
    request = DemoCoursewareDigitalCredentialRequestFactory.create(learner=learner)

    responses.add(
        responses.POST,
        "http://localhost:5000/verify/presentations",
        json={},
        status=200,
    )
    responses.add(
        responses.POST, "http://localhost:5000/issue/credentials", json={}, status=500,
    )

    serializer = DigitalCredentialRequestSerializer(
        request, data={"id": learner_did.did,}
    )
    serializer.is_valid(raise_exception=True)

    with pytest.raises(Exception):
        serializer.save()

    request.refresh_from_db()
    assert request.consumed is False
    assert DigitalCredential.objects.count() == 0

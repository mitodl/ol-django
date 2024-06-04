"""Digital Credentials serializers"""

import json

import pytest
import responses
from django.contrib.contenttypes.models import ContentType
from mitol.digitalcredentials.factories import LearnerDIDFactory
from mitol.digitalcredentials.models import (
    DigitalCredential,
    DigitalCredentialRequest,
    LearnerDID,
)
from mitol.digitalcredentials.serializers import (
    DigitalCredentialIssueSerializer,
    DigitalCredentialRequestSerializer,
)
from testapp.factories import (
    DemoCoursewareDigitalCredentialFactory,
    DemoCoursewareDigitalCredentialRequestFactory,
)

pytestmark = pytest.mark.django_db


@responses.activate
@pytest.mark.parametrize("learner_did_exists", [True, False])
def test_digital_credential_issue_serializer(learner, learner_did_exists):
    """Verify that the serializer updates successfully"""
    did = "did:example:12345"
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

    serializer = DigitalCredentialIssueSerializer(
        request,
        data={
            "holder": did,
        },
    )
    serializer.is_valid(raise_exception=True)

    result = serializer.save()

    learner_did = LearnerDID.objects.get(learner=learner, did=did)

    assert isinstance(result, DigitalCredential)
    assert result.credentialed_object == request.credentialed_object
    assert result.learner == learner
    assert result.learner_did == learner_did
    assert json.loads(result.credential_json) == response_json

    request.refresh_from_db()
    assert request.consumed is True


@responses.activate
def test_digital_credential_issue_serializer_other_user_did(learner):
    """Verify DigitalCredentialIssueSerializer errors if the DID is already associated with another user"""
    learner_did = LearnerDIDFactory.create()
    request = DemoCoursewareDigitalCredentialRequestFactory.create(learner=learner)

    responses.add(
        responses.POST,
        "http://localhost:5000/verify/presentations",
        json={},
        status=200,
    )
    serializer = DigitalCredentialIssueSerializer(
        request,
        data={
            "holder": learner_did.did,
        },
    )
    assert serializer.is_valid() is False
    assert serializer.errors == {"holder": ["DID is associated with someone else"]}


@responses.activate
def test_digital_credential_issue_serializer_presentation_verify_failed():
    """Verify DigitalCredentialIssueSerializer errors if the presentation fails to validate"""
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
    serializer = DigitalCredentialIssueSerializer(
        request,
        data={
            "holder": learner_did.did,
        },
    )
    assert serializer.is_valid() is False
    assert serializer.errors == {
        "non_field_errors": ["Unable to verify digital credential presentation"]
    }


@responses.activate
def test_digital_credential_issue_serializer_error(learner):
    """Verify that the serializer doesn't modify state if there's an upstream error"""
    learner_did = LearnerDIDFactory.create(learner=learner)
    request = DemoCoursewareDigitalCredentialRequestFactory.create(learner=learner)

    responses.add(
        responses.POST,
        "http://localhost:5000/verify/presentations",
        json={},
        status=200,
    )
    responses.add(
        responses.POST,
        "http://localhost:5000/issue/credentials",
        json={},
        status=500,
    )

    serializer = DigitalCredentialIssueSerializer(
        request,
        data={
            "holder": learner_did.did,
        },
    )
    serializer.is_valid(raise_exception=True)

    with pytest.raises(Exception):
        serializer.save()

    request.refresh_from_db()
    assert request.consumed is False
    assert DigitalCredential.objects.count() == 0


@pytest.mark.parametrize("request_exists", [True, False])
def test_digital_credential_request_serializer(learner, request_exists):
    """Test DigitalCredentialRequestSerializer"""
    if request_exists:
        DemoCoursewareDigitalCredentialRequestFactory.create(learner=learner)
    assert DigitalCredentialRequest.objects.filter(learner=learner).count() == (
        1 if request_exists else 0
    )

    credentialed_object = DemoCoursewareDigitalCredentialFactory.create(learner=learner)
    serializer = DigitalCredentialRequestSerializer(
        data={
            "learner_id": learner.id,
            "credentialed_object_id": credentialed_object.id,
            "credentialed_content_type_id": ContentType.objects.get_for_model(
                credentialed_object
            ).id,
        }
    )
    serializer.is_valid(raise_exception=True)
    result = serializer.save()

    assert DigitalCredentialRequest.objects.filter(learner=learner).count() == (
        2 if request_exists else 1
    )
    assert isinstance(result, DigitalCredentialRequest)
    assert result.learner == learner
    assert result.credentialed_object == credentialed_object
    assert result.consumed is False

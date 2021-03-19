"""Views tests"""
from http import HTTPStatus

import pytest
import responses
from django.urls import reverse
from rest_framework.test import APIClient

from mitol.digitalcredentials.backend import create_deep_link_url
from mitol.digitalcredentials.models import DigitalCredentialRequest
from testapp.factories import (
    DemoCoursewareDigitalCredentialRequestFactory,
    DemoCoursewareFactory,
)


pytestmark = pytest.mark.django_db


@responses.activate
def test_issue_credential(learner_and_oauth2):
    """Verify that a learner can request a credential"""
    client = APIClient()
    credential_request = DemoCoursewareDigitalCredentialRequestFactory.create(
        learner=learner_and_oauth2.learner
    )
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
    response = client.post(
        reverse(
            "digital-credentials:credentials-issue",
            kwargs={"uuid": credential_request.uuid},
        ),
        {"id": "did:example:abc"},
        HTTP_AUTHORIZATION=f"Bearer {learner_and_oauth2.access_token.token}",
    )

    assert response.status_code == HTTPStatus.OK, f"Response error: {response.json()}"
    assert response.json() == response_json


@responses.activate
def test_issue_credential_anonymous():
    """Verify that the API requires oauth authentication"""
    client = APIClient()
    credential_request = DemoCoursewareDigitalCredentialRequestFactory.create()
    response = client.post(
        reverse(
            "digital-credentials:credentials-issue",
            kwargs={"uuid": credential_request.uuid},
        ),
        {"id": "did:example:abc"},
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED


@responses.activate
def test_issue_credential_wrong_learner(learner_and_oauth2):
    """Verify that the API returns a 404 if the wrong user is authenticated"""
    client = APIClient()
    credential_request = DemoCoursewareDigitalCredentialRequestFactory.create()
    response = client.post(
        reverse(
            "digital-credentials:credentials-issue",
            kwargs={"uuid": credential_request.uuid},
        ),
        {"id": "did:example:abc"},
        HTTP_AUTHORIZATION=f"Bearer {learner_and_oauth2.access_token.token}",
    )
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_request_credential(learner, learner_drf_client):
    """Test requesting a credential"""
    credentialed_object = DemoCoursewareFactory.create(learner=learner)

    assert DigitalCredentialRequest.objects.count() == 0

    resp = learner_drf_client.post(
        reverse(
            "democourseware-request_digital_credentials",
            kwargs={"pk": credentialed_object.id},
        )
    )

    assert DigitalCredentialRequest.objects.count() == 1

    credential_request = DigitalCredentialRequest.objects.first()
    assert resp.json() == {
        "deep_link_url": create_deep_link_url(credential_request),
        "uuid": str(credential_request.uuid),
    }

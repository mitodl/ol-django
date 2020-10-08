"""Views tests"""
from http import HTTPStatus

import pytest
import responses
from django.urls import reverse
from rest_framework.test import APIClient

from testapp.factories import DemoCoursewareDigitalCredentialRequestFactory


pytestmark = pytest.mark.django_db


@responses.activate
def test_request_credential(learner_and_oauth2):
    """Verify that a learner can request a credential"""
    client = APIClient()
    credential_request = DemoCoursewareDigitalCredentialRequestFactory.create(
        learner=learner_and_oauth2.learner
    )
    response_json = {"result": True}
    responses.add(
        responses.POST,
        "http://localhost:5000/issue/credentials",
        json=response_json,
        status=200,
    )
    response = client.post(
        reverse(
            "digital-credentials:credentials-request",
            kwargs={"uuid": credential_request.uuid},
        ),
        {"learnerDid": "did:example:abc"},
        HTTP_AUTHORIZATION=f"Bearer {learner_and_oauth2.access_token.token}",
    )

    assert response.status_code == HTTPStatus.OK, f"Response error: {response.json()}"
    assert response.json() == response_json


@responses.activate
def test_request_credential_anonymous():
    """Verify that the API requires oauth authentication"""
    client = APIClient()
    credential_request = DemoCoursewareDigitalCredentialRequestFactory.create()
    response = client.post(
        reverse(
            "digital-credentials:credentials-request",
            kwargs={"uuid": credential_request.uuid},
        ),
        {"learnerDid": "did:example:abc"},
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED


@responses.activate
def test_request_credential_wrong_learner(learner_and_oauth2):
    """Verify that the API returns a 404 if the wrong user is authenticated"""
    client = APIClient()
    credential_request = DemoCoursewareDigitalCredentialRequestFactory.create()
    response = client.post(
        reverse(
            "digital-credentials:credentials-request",
            kwargs={"uuid": credential_request.uuid},
        ),
        {"learnerDid": "did:example:abc"},
        HTTP_AUTHORIZATION=f"Bearer {learner_and_oauth2.access_token.token}",
    )
    assert response.status_code == HTTPStatus.NOT_FOUND

"""Integration tests"""
import json

import pytest
import responses
from django.core.exceptions import ImproperlyConfigured

from mitol.digitalcredentials.backend import (
    build_api_url,
    build_credential,
    issue_credential,
    verify_presentations,
)


def test_build_api_url():
    """Test build_api_url with a valid setting"""
    assert build_api_url("/path") == "http://localhost:5000/path"


def test_build_api_url_invalid(settings):
    """Test build_api_url with an invalid setting"""
    settings.MITOL_DIGITAL_CREDENTIALS_VERIFY_SERVICE_BASE_URL = None

    with pytest.raises(ImproperlyConfigured):
        build_api_url("/path")


@responses.activate
@pytest.mark.parametrize(
    "value, expected_value",
    [({"id": "verify:abc"}, "verify:abc"), ("verify:abc", "verify:abc"), (None, "")],
)
@pytest.mark.parametrize(
    "verification_method, matches",
    [
        ("verificationMethod", True),
        ("https://w3id.org/security#verificationMethod", True),
        ("invalidKey", False),
    ],
)
def test_verify_presentations(
    mocker, value, expected_value, verification_method, matches
):
    """Test verify_presentations"""
    responses.add(
        responses.POST,
        "http://localhost:5000/verify/presentations",
        json={},
        status=200,
    )
    presentation = {
        "id": "did:example:123",
        "proof": {verification_method: value},
    }
    credential_request = mocker.Mock(uuid="1234567890")
    response = verify_presentations(credential_request, presentation)

    assert (
        responses.calls[0].request.url == "http://localhost:5000/verify/presentations"
    )
    assert json.loads(responses.calls[0].request.body) == {
        "verifiablePresentation": presentation,
        "options": {
            "verificationMethod": expected_value if matches else "",
            "challenge": str(credential_request.uuid),
        },
    }
    assert response == responses.calls[0].response


def test_build_credential(mocker, settings):
    """Test build_credential calls the configured function"""
    mock_import_string = mocker.patch("mitol.digitalcredentials.backend.import_string")
    configured_func = mock_import_string.return_value

    mock_courseware = mocker.Mock()
    mock_learner_did = mocker.Mock()

    build_credential(mock_courseware, mock_learner_did)

    mock_import_string.assert_called_once_with(
        settings.MITOL_DIGITAL_CREDENTIALS_BUILD_CREDENTIAL_FUNC
    )
    configured_func.assert_called_once_with(mock_courseware, mock_learner_did)


def test_build_credential_not_set(mocker, settings):
    """Test build_credential calls the configured function"""
    settings.MITOL_DIGITAL_CREDENTIALS_BUILD_CREDENTIAL_FUNC = None

    mock_import_string = mocker.patch("mitol.digitalcredentials.backend.import_string")

    with pytest.raises(ImproperlyConfigured):
        build_credential(mocker.Mock(), mocker.Mock())

    mock_import_string.assert_not_called()


@responses.activate
@pytest.mark.parametrize("use_hmac", [True, False])
def test_issue_credential(settings, use_hmac):
    """Tests issue_credential"""
    settings.MITOL_DIGITAL_CREDENTIALS_HMAC_SECRET = "abc123" if use_hmac else None
    response_json = {"status": True}
    credential = {"credential": 123}
    responses.add(
        responses.POST,
        "http://localhost:5000/issue/credentials",
        json=response_json,
        status=200,
    )

    assert issue_credential(credential) == response_json

    assert len(responses.calls) == 1
    request = responses.calls[0].request
    assert request.url == "http://localhost:5000/issue/credentials"
    assert "Digest" in request.headers
    if use_hmac:
        assert "Signature" in request.headers
    else:
        assert "Signature" not in request.headers
    assert json.loads(request.body) == credential

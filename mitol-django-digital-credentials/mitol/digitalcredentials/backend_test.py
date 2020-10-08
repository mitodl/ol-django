"""Integration tests"""
import json

import pytest
import responses
from django.core.exceptions import ImproperlyConfigured

from mitol.digitalcredentials.backend import (
    build_api_url,
    build_credential,
    issue_credential,
)


def test_build_api_url():
    """Test build_api_url with a valid setting"""
    assert build_api_url("/path") == f"http://localhost:5000/path"


def test_build_api_url_invalid(settings):
    """Test build_api_url with an invalid setting"""
    settings.MITOL_DIGITAL_CREDENTIALS_VERIFY_SERVICE_BASE_URL = None

    with pytest.raises(ImproperlyConfigured):
        build_api_url("/path")


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
def test_issue_credential():
    """Tests issue_credential"""
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
    assert responses.calls[0].request.url == "http://localhost:5000/issue/credentials"
    assert json.loads(responses.calls[0].request.body) == credential

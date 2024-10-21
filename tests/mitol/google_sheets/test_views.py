"""Tests for sheets app views"""

import pytest
from django.test.client import RequestFactory
from django.urls import reverse
from mitol.google_sheets.factories import GoogleApiAuthFactory
from mitol.google_sheets.models import GoogleApiAuth
from mitol.google_sheets.views import complete_google_auth
from pytest_lazy_fixtures import lf as lazy_fixture
from rest_framework import status
from testapp.utils import set_request_session

lazy = lazy_fixture


@pytest.fixture
def google_api_auth(learner):
    """Fixture that creates a google auth object"""
    return GoogleApiAuthFactory.create(requesting_user=learner)


def test_request_auth(mocker, settings, staff_client):
    """
    View that starts Google auth should set session variables and redirect to the
    expected Google auth page
    """
    settings.SITE_BASE_URL = "http://example.com"
    settings.MITOL_GOOGLE_SHEETS_DRIVE_CLIENT_ID = "client_id"
    settings.MITOL_GOOGLE_SHEETS_DRIVE_CLIENT_SECRET = "some-secret"  # noqa: S105
    settings.MITOL_GOOGLE_SHEETS_DRIVE_API_PROJECT_ID = "some-project-id"
    settings.SITE_BASE_URL = "http://example.com"
    fake_redirect_url = "/"
    fake_state = "some-state"
    fake_code_verifier = "some-code-verifier"
    flow_mock = mocker.Mock(
        authorization_url=mocker.Mock(return_value=(fake_redirect_url, fake_state)),
        code_verifier=fake_code_verifier,
    )
    patched_flow = mocker.patch(
        "mitol.google_sheets.views.Flow",
        from_client_config=mocker.Mock(return_value=flow_mock),
    )

    resp = staff_client.get(reverse("google-sheets:request-google-auth"), follow=False)
    patched_flow.from_client_config.assert_called_once()
    flow_mock.authorization_url.assert_called_once_with(
        access_type="offline", include_granted_scopes="true", prompt="consent"
    )
    assert resp.status_code == status.HTTP_302_FOUND
    assert resp.url == fake_redirect_url
    assert staff_client.session["state"] == fake_state
    assert staff_client.session["code_verifier"] == fake_code_verifier


@pytest.mark.parametrize("existing_auth", [lazy("google_api_auth"), None])
@pytest.mark.django_db
def test_complete_auth(mocker, settings, learner, existing_auth):  # noqa: ARG001
    """
    View that handles Google auth completion should fetch a token and save/update a
    GoogleApiAuth object
    """
    settings.SITE_BASE_URL = "http://example.com"
    settings.MITOL_GOOGLE_SHEETS_DRIVE_CLIENT_ID = "client_id"
    settings.MITOL_GOOGLE_SHEETS_DRIVE_CLIENT_SECRET = "some-secret"  # noqa: S105
    settings.MITOL_GOOGLE_SHEETS_DRIVE_API_PROJECT_ID = "some-project-id"
    settings.SITE_BASE_URL = "http://example.com"
    access_token = "access-token-123"  # noqa: S105
    refresh_token = "refresh-token-123"  # noqa: S105
    code = "auth-code"
    flow_mock = mocker.Mock(
        credentials=mocker.Mock(token=access_token, refresh_token=refresh_token)
    )
    patched_flow = mocker.patch(
        "mitol.google_sheets.views.Flow",
        from_client_config=mocker.Mock(return_value=flow_mock),
    )
    auth_complete_url = "{}?code={}".format(
        reverse("google-sheets:complete-google-auth"), code
    )
    # There was an issue with setting session variables in a normal Django test client,
    # so RequestFactory is being used to test the view directly.
    request = set_request_session(
        RequestFactory().get(auth_complete_url),
        session_dict={"state": "some-state", "code_verifier": "some-verifier"},
    )
    request.user = learner

    response = complete_google_auth(request)
    patched_flow.from_client_config.assert_called_once()
    patched_flow_obj = patched_flow.from_client_config.return_value
    assert (
        patched_flow_obj.redirect_uri == "http://example.com/api/sheets/auth-complete/"
    )
    assert patched_flow_obj.code_verifier == "some-verifier"
    patched_flow_obj.fetch_token.assert_called_once_with(code=code)
    assert GoogleApiAuth.objects.count() == 1
    assert (
        GoogleApiAuth.objects.filter(
            requesting_user=learner,
            access_token=access_token,
            refresh_token=refresh_token,
        ).exists()
        is True
    )
    assert response.status_code == status.HTTP_302_FOUND
    assert response.url.startswith(reverse("google-sheets:sheets-admin-view"))

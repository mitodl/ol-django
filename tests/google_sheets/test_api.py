"""Sheets API tests"""

import pytest
from django.core.exceptions import ImproperlyConfigured
from google.oauth2.credentials import Credentials
from mitol.google_sheets.api import get_credentials
from mitol.google_sheets.constants import REQUIRED_GOOGLE_API_SCOPES
from mitol.google_sheets.factories import GoogleApiAuthFactory


@pytest.mark.django_db
def test_get_credentials_service_account(mocker, settings):
    """
    get_credentials should construct a valid Credentials object from app settings using Service Account auth
    """  # noqa: E501
    patched_svc_account_creds = mocker.patch(
        "mitol.google_sheets.api.ServiceAccountCredentials"
    )
    settings.MITOL_GOOGLE_SHEETS_DRIVE_SERVICE_ACCOUNT_CREDS = '{"credentials": "json"}'
    settings.MITOL_GOOGLE_SHEETS_ADMIN_EMAILS = ["abc@example.com"]
    settings.MITOL_GOOGLE_SHEETS_GOOGLE_ACCOUNT_EMAIL_DOMAIN = "iam.gserviceaccount.com"
    # An exception should be raised if service account auth is being used, but no service account email  # noqa: E501
    # is included in the list of emails to share spreadsheets with.
    with pytest.raises(ImproperlyConfigured):
        get_credentials()

    settings.MITOL_GOOGLE_SHEETS_ADMIN_EMAILS.append(
        f"service-account@mitol.{settings.MITOL_GOOGLE_SHEETS_GOOGLE_ACCOUNT_EMAIL_DOMAIN}"
    )
    creds = get_credentials()

    patched_svc_account_creds.from_service_account_info.assert_called_once_with(
        {"credentials": "json"}, scopes=REQUIRED_GOOGLE_API_SCOPES
    )
    assert creds == patched_svc_account_creds.from_service_account_info.return_value


@pytest.mark.django_db
def test_get_credentials_personal_auth(settings):
    """
    get_credentials should construct a valid Credentials object from data and app settings using personal
    OAuth credentials if Service Account auth is not being used
    """  # noqa: E501
    settings.MITOL_GOOGLE_SHEETS_DRIVE_SERVICE_ACCOUNT_CREDS = None
    settings.MITOL_GOOGLE_SHEETS_DRIVE_CLIENT_ID = "client-id"
    settings.MITOL_GOOGLE_SHEETS_DRIVE_CLIENT_SECRET = "client-secret"  # noqa: S105
    settings.ENVIRONMENT = "prod"
    with pytest.raises(ImproperlyConfigured):
        get_credentials()

    google_api_auth = GoogleApiAuthFactory.create()
    credentials = get_credentials()
    assert isinstance(credentials, Credentials)
    assert credentials.token == google_api_auth.access_token
    assert credentials.refresh_token == google_api_auth.refresh_token

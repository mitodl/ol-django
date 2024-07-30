"""Sheets app util function tests"""

from mitol.google_sheets.constants import (
    GOOGLE_AUTH_PROVIDER_X509_CERT_URL,
    GOOGLE_AUTH_URI,
    GOOGLE_TOKEN_URI,
)
from mitol.google_sheets.utils import generate_google_client_config, get_data_rows
from pygsheets.worksheet import Worksheet


def test_generate_google_client_config(settings):
    """generate_google_client_config should return a dict with expected values"""
    settings.MITOL_GOOGLE_SHEETS_DRIVE_CLIENT_ID = "some-id"
    settings.MITOL_GOOGLE_SHEETS_DRIVE_CLIENT_SECRET = "some-secret"  # noqa: S105
    settings.MITOL_GOOGLE_SHEETS_DRIVE_API_PROJECT_ID = "some-project-id"
    settings.SITE_BASE_URL = "http://example.com"
    assert generate_google_client_config() == {
        "web": {
            "client_id": "some-id",
            "client_secret": "some-secret",
            "project_id": "some-project-id",
            "redirect_uris": ["http://example.com/api/sheets/auth-complete/"],
            "auth_uri": GOOGLE_AUTH_URI,
            "token_uri": GOOGLE_TOKEN_URI,
            "auth_provider_x509_cert_url": GOOGLE_AUTH_PROVIDER_X509_CERT_URL,
        }
    }


def test_get_data_rows(mocker):
    """get_data_rows should return each row of a worksheet data after the first row (i.e.: the header row)"""  # noqa: E501
    non_header_rows = [
        ["row 1 - column 1", "row 1 - column 2"],
        ["row 2 - column 1", "row 2 - column 2"],
    ]
    sheet_rows = [["HEADER 1", "HEADER 2"]] + non_header_rows  # noqa: RUF005
    mocked_worksheet = mocker.MagicMock(
        spec=Worksheet, get_all_values=mocker.Mock(return_value=sheet_rows)
    )
    data_rows = list(get_data_rows(mocked_worksheet))
    assert data_rows == non_header_rows

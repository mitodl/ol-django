"""Deferral request API tests"""

import os
from types import SimpleNamespace

import pytest
from mitol.google_sheets.factories import GoogleApiAuthFactory
from mitol.google_sheets.utils import ResultType
from mitol.google_sheets_deferrals.api import DeferralRequestHandler
from pygsheets import Spreadsheet, Worksheet
from pygsheets.client import Client as PygsheetsClient
from pygsheets.drive import DriveAPIWrapper
from pygsheets.sheet import SheetAPIWrapper
from pytest_lazy_fixtures import lf as lazy_fixture


@pytest.fixture
def request_csv_rows(settings):
    """Fake deferral request spreadsheet data rows (loaded from CSV)"""
    fake_request_csv_filepath = os.path.join(  # noqa: PTH118
        settings.BASE_DIR, "data/google_sheets_deferrals/deferral_requests.csv"
    )
    with open(fake_request_csv_filepath) as f:  # noqa: PTH123
        # Return all rows except for the header
        return [line.split(",") for i, line in enumerate(f.readlines()) if i > 0]


@pytest.fixture
def pygsheets_fixtures(mocker, db, request_csv_rows):  # noqa: ARG001
    """Patched functions for pygsheets client functionality"""
    Mock = mocker.Mock
    MagicMock = mocker.MagicMock
    google_api_auth = GoogleApiAuthFactory.create()
    patched_get_data_rows = mocker.patch(
        "mitol.google_sheets.sheet_handler_api.get_data_rows_after_start",
        return_value=request_csv_rows,
    )
    mocked_worksheet = MagicMock(spec=Worksheet, get_all_values=Mock(return_value=[]))
    mocked_spreadsheet = MagicMock(
        spec=Spreadsheet, sheet1=mocked_worksheet, id="abc123"
    )
    mocked_pygsheets_client = MagicMock(
        spec=PygsheetsClient,
        oauth=Mock(),
        open_by_key=Mock(return_value=mocked_spreadsheet),
        drive=MagicMock(spec=DriveAPIWrapper),
        sheet=MagicMock(spec=SheetAPIWrapper),
        create=Mock(return_value=mocked_spreadsheet),
    )
    mocker.patch(
        "mitol.google_sheets.sheet_handler_api.get_authorized_pygsheets_client",
        return_value=mocked_pygsheets_client,
    )
    return SimpleNamespace(
        client=mocked_pygsheets_client,
        spreadsheet=mocked_spreadsheet,
        worksheet=mocked_worksheet,
        google_api_auth=google_api_auth,
        patched_get_data_rows=patched_get_data_rows,
    )


@pytest.fixture
def google_sheets_deferral_settings(settings):
    settings.MITOL_GOOGLE_SHEETS_DEFERRALS_REQUEST_WORKSHEET_ID = "1"
    settings.MITOL_GOOGLE_SHEETS_DEFERRALS_PLUGINS = "app.plugins.DeferralPlugin"
    return settings


@pytest.mark.parametrize(
    "has_sheets_settings", [lazy_fixture("google_sheets_base_settings"), False]
)
@pytest.mark.parametrize(
    "has_service_creds_settings",
    [lazy_fixture("google_sheets_service_creds_settings"), False],
)
@pytest.mark.parametrize(
    "has_client_creds_settings",
    [lazy_fixture("google_sheets_client_creds_settings"), False],
)
@pytest.mark.parametrize(
    "has_deferral_settings, ", [lazy_fixture("google_sheets_deferral_settings"), False]
)
def test_is_configured(  # noqa: PLR0913
    db,  # noqa: ARG001
    settings,  # noqa: ARG001
    mocker,
    pygsheets_fixtures,  # noqa: ARG001
    has_sheets_settings,
    has_service_creds_settings,
    has_client_creds_settings,
    has_deferral_settings,
):
    """
    is_configured makes sure all config variables are set
    """
    mocked_plugin_manager = mocker.Mock(
        hook=mocker.Mock(
            deferrals_process_request=mocker.Mock(
                return_value=(ResultType.PROCESSED, "message")
            )
        )
    )

    mock_get_plugin_manager = mocker.patch(
        "mitol.google_sheets_deferrals.api.get_plugin_manager",
        return_value=mocked_plugin_manager,
    )
    handler = DeferralRequestHandler()
    mock_get_plugin_manager.assert_called_once()

    assert handler.is_configured() is (
        has_sheets_settings
        and has_deferral_settings
        and any(
            # one needs to be configured
            [has_service_creds_settings, has_client_creds_settings]
        )
        and not all(
            # but not more than one
            [has_service_creds_settings, has_client_creds_settings]
        )
    )


def test_full_sheet_process(db, settings, mocker, pygsheets_fixtures, request_csv_rows):  # noqa: ARG001
    """
    DeferralRequestHandler.process_sheet should parse rows, create relevant objects in the database, and report
    on results
    """  # noqa: E501
    settings.MITOL_GOOGLE_SHEETS_ENROLLMENT_CHANGE_SHEET_ID = "1"
    mocked_plugin_manager = mocker.Mock(
        hook=mocker.Mock(
            deferrals_process_request=mocker.Mock(
                return_value=[(ResultType.PROCESSED, "message")]
            )
        )
    )

    mock_get_plugin_manager = mocker.patch(
        "mitol.google_sheets_deferrals.api.get_plugin_manager",
        return_value=mocked_plugin_manager,
    )

    handler = DeferralRequestHandler()

    mock_get_plugin_manager.assert_called_once()

    result = handler.process_sheet()
    expected_processed_rows = {7, 8}
    expected_failed_rows = {9}
    assert ResultType.PROCESSED.value in result
    assert set(result[ResultType.PROCESSED.value]) == expected_processed_rows, (
        "Rows %s as defined in deferral_requests.csv should be processed"  # noqa: UP031
        % str(expected_processed_rows)
    )
    assert ResultType.FAILED.value in result
    assert set(result[ResultType.FAILED.value]) == expected_failed_rows, (
        "Rows %s as defined in deferral_requests.csv should fail"  # noqa: UP031
        % str(expected_failed_rows)
    )

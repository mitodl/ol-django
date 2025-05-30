"""Refund request API tests"""

from types import SimpleNamespace

import pytest
from mitol.google_sheets.factories import GoogleApiAuthFactory
from mitol.google_sheets.utils import ResultType
from mitol.google_sheets_refunds.api import RefundRequestHandler
from pygsheets import Spreadsheet, Worksheet
from pygsheets.client import Client as PygsheetsClient
from pygsheets.drive import DriveAPIWrapper
from pygsheets.sheet import SheetAPIWrapper
from pytest_lazy_fixtures import lf as lazy_fixture


@pytest.fixture
def request_csv_rows(open_data_fixture_file):
    """Fake refund request spreadsheet data rows (loaded from CSV)"""
    with open_data_fixture_file("google_sheets_refunds/refund_requests.csv") as f:
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
def google_sheets_refunds_settings(settings):
    settings.MITOL_GOOGLE_SHEETS_REFUNDS_REQUEST_WORKSHEET_ID = "1"
    settings.MITOL_GOOGLE_SHEETS_REFUNDS_PLUGINS = "app.plugins.RefundPlugin"
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
    "has_refunds_settings, ", [lazy_fixture("google_sheets_refunds_settings"), False]
)
def test_is_configured(  # noqa: PLR0913
    db,  # noqa: ARG001
    settings,  # noqa: ARG001
    mocker,
    pygsheets_fixtures,  # noqa: ARG001
    has_sheets_settings,
    has_service_creds_settings,
    has_client_creds_settings,
    has_refunds_settings,
):
    """
    is_configured makes sure all config variables are set
    """
    mocked_plugin_manager = mocker.Mock(
        hook=mocker.Mock(
            refunds_process_request=mocker.Mock(
                return_value=(ResultType.PROCESSED, "message")
            )
        )
    )

    mock_get_plugin_manager = mocker.patch(
        "mitol.google_sheets_refunds.api.get_plugin_manager",
        return_value=mocked_plugin_manager,
    )
    handler = RefundRequestHandler()
    mock_get_plugin_manager.assert_called_once()

    assert handler.is_configured() is (
        has_sheets_settings
        and has_refunds_settings
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
    RefundRequestHandler.process_sheet should parse rows, create relevant objects in the database, and report
    on results
    """  # noqa: E501
    settings.MITOL_GOOGLE_SHEETS_ENROLLMENT_CHANGE_SHEET_ID = "1"
    mocked_plugin_manager = mocker.Mock(
        hook=mocker.Mock(
            refunds_process_request=mocker.Mock(
                return_value=[(ResultType.PROCESSED, "message")]
            )
        )
    )

    mock_get_plugin_manager = mocker.patch(
        "mitol.google_sheets_refunds.api.get_plugin_manager",
        return_value=mocked_plugin_manager,
    )

    handler = RefundRequestHandler()

    mock_get_plugin_manager.assert_called_once()

    result = handler.process_sheet()
    expected_processed_rows = {5, 10, 11}
    expected_failed_rows = {6}
    expected_oos_rows = {7}
    assert ResultType.PROCESSED.value in result
    assert set(result[ResultType.PROCESSED.value]) == expected_processed_rows, (
        "Rows %s as defined in refund_requests.csv should be processed"  # noqa: UP031
        % str(expected_processed_rows)
    )
    assert ResultType.OUT_OF_SYNC.value in result
    assert set(result[ResultType.OUT_OF_SYNC.value]) == expected_oos_rows, (
        "Rows %s as defined in refund_requests.csv should be out of sync"  # noqa: UP031
        % str(expected_oos_rows)
    )
    assert ResultType.FAILED.value in result
    assert set(result[ResultType.FAILED.value]) == expected_failed_rows, (
        "Rows %s as defined in refund_requests.csv should fail"  # noqa: UP031
        % str(expected_failed_rows)
    )

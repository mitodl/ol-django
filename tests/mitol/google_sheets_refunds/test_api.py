"""Refund request API tests"""

import os
from types import SimpleNamespace

import pytest
from pygsheets import Spreadsheet, Worksheet
from pygsheets.client import Client as PygsheetsClient
from pygsheets.drive import DriveAPIWrapper
from pygsheets.sheet import SheetAPIWrapper

from mitol.google_sheets.factories import GoogleApiAuthFactory
from mitol.google_sheets.utils import ResultType
from mitol.google_sheets_refunds.api import RefundRequestHandler, RefundRequestRow
from mitol.google_sheets_refunds.models import RefundRequest


@pytest.fixture
def request_csv_rows(settings):
    """Fake refund request spreadsheet data rows (loaded from CSV)"""
    fake_request_csv_filepath = os.path.join(
        settings.BASE_DIR, "mitol/google_sheets_refunds/resources/refund_requests.csv"
    )
    with open(fake_request_csv_filepath) as f:
        # Return all rows except for the header
        return [line.split(",") for i, line in enumerate(f.readlines()) if i > 0]


@pytest.fixture
def pygsheets_fixtures(mocker, db, request_csv_rows):
    """Patched functions for pygsheets client functionality"""
    Mock = mocker.Mock
    MagicMock = mocker.MagicMock
    google_api_auth = GoogleApiAuthFactory.create()
    patched_get_data_rows = mocker.patch(
        "sheets.sheet_handler_api.get_data_rows", return_value=request_csv_rows
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
        "sheets.coupon_request_api.get_authorized_pygsheets_client",
        return_value=mocked_pygsheets_client,
    )
    return SimpleNamespace(
        client=mocked_pygsheets_client,
        spreadsheet=mocked_spreadsheet,
        worksheet=mocked_worksheet,
        google_api_auth=google_api_auth,
        patched_get_data_rows=patched_get_data_rows,
    )


def test_full_sheet_process(db, settings, pygsheets_fixtures, request_csv_rows):
    """
    RefundRequestHandler.process_sheet should parse rows, create relevant objects in the database, and report
    on results
    """
    handler = RefundRequestHandler()
    result = handler.process_sheet()
    expected_processed_rows = {6, 8}
    expected_failed_rows = {5, 7}
    assert ResultType.PROCESSED.value in result
    assert (
        set(result[ResultType.PROCESSED.value]) == expected_processed_rows
    ), "Rows %s as defined in refund_requests.csv should be processed" % str(
        expected_processed_rows
    )
    assert ResultType.FAILED.value in result
    assert (
        set(result[ResultType.FAILED.value]) == expected_failed_rows
    ), "Rows %s as defined in refund_requests.csv should fail" % str(
        expected_failed_rows
    )
    # A RefundRequest should be created for each row that wasn't ignored and did not fail full sheet
    # validation (CSV has 1 row that should fail validation, hence the 1)
    assert RefundRequest.objects.all().count() == (
        len(expected_processed_rows) + len(expected_failed_rows) - 1
    )

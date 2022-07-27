"""Enrollment refund API"""
import logging

from django.conf import settings
from django.contrib.auth import get_user_model

from mitol.common.utils.datetime import now_in_utc
from mitol.google_sheets.exceptions import SheetRowParsingException
from mitol.google_sheets.sheet_handler_api import GoogleSheetsChangeRequestHandler
from mitol.google_sheets.utils import ResultType, RowResult
from mitol.google_sheets_refunds.hooks import get_plugin_manager
from mitol.google_sheets_refunds.models import RefundRequest
from mitol.google_sheets_refunds.utils import RefundRequestRow, refund_sheet_config

log = logging.getLogger(__name__)
User = get_user_model()


class RefundRequestHandler(GoogleSheetsChangeRequestHandler):
    """Manages the processing of refund requests from a spreadsheet"""

    def __init__(self):
        self.pm = get_plugin_manager()
        self.hook = self.pm.hook
        super().__init__(
            spreadsheet_id=settings.MITOL_GOOGLE_SHEETS_ENROLLMENT_CHANGE_SHEET_ID,
            worksheet_id=settings.MITOL_GOOGLE_SHEETS_REFUNDS_REQUEST_WORKSHEET_ID,
            start_row=settings.MITOL_GOOGLE_SHEETS_REFUNDS_FIRST_ROW,
            sheet_metadata=refund_sheet_config,
            request_model_cls=RefundRequest,
        )

    def process_row(self, row_index, row_data):
        """
        Ensures that the given spreadsheet row is correctly represented in the database,
        attempts to parse it, reverses/refunds the given enrollment if appropriate, and returns the
        result of processing the row.

        Args:
            row_index (int): The row index according to the spreadsheet
            row_data (list of str): The raw data of the given spreadsheet row

        Returns:
            RowResult or None: An object representing the results of processing the row, or None if
                nothing needs to be done with this row.
        """
        refund_request, request_created, request_updated = self.get_or_create_request(
            row_data
        )
        try:
            refund_req_row = RefundRequestRow.parse_raw_data(row_index, row_data)
        except SheetRowParsingException as exc:
            log.error("Parsing failure: {}".format(str(exc)))
            return RowResult(
                row_index=row_index,
                row_db_record=refund_request,
                row_object=None,
                result_type=ResultType.FAILED,
                message="Parsing failure: {}".format(str(exc)),
            )
        is_unchanged_error_row = (
            refund_req_row.errors and not request_created and not request_updated
        )
        if is_unchanged_error_row:
            return RowResult(
                row_index=row_index,
                row_db_record=refund_request,
                row_object=None,
                result_type=ResultType.IGNORED,
                message=None,
            )
        elif (
            refund_request.date_completed
            and refund_req_row.refund_complete_date is None
        ):
            return RowResult(
                row_index=row_index,
                row_db_record=refund_request,
                row_object=None,
                result_type=ResultType.OUT_OF_SYNC,
                message=None,
            )
        result_type, message = self.hook.refunds_process_request(
            refund_request_row=refund_req_row
        )
        if result_type == ResultType.PROCESSED:
            refund_request.date_completed = now_in_utc()
            refund_request.save()

        return RowResult(
            row_index=row_index,
            row_db_record=refund_request,
            row_object=refund_req_row,
            result_type=result_type,
            message=message,
        )

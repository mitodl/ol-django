"""Enrollment deferral API"""
import logging

from django.conf import settings
from django.contrib.auth import get_user_model

from mitol.common.utils.collections import item_at_index_or_none
from mitol.common.utils.config import get_missing_settings
from mitol.common.utils.datetime import now_in_utc
from mitol.google_sheets.constants import GOOGLE_API_TRUE_VAL
from mitol.google_sheets.exceptions import SheetRowParsingException
from mitol.google_sheets.sheet_handler_api import GoogleSheetsChangeRequestHandler
from mitol.google_sheets.utils import ResultType, RowResult
from mitol.google_sheets_deferrals.constants import (
    REQUIRED_GOOGLE_SHEETS_DEFERRALS_SETTINGS,
)
from mitol.google_sheets_deferrals.hooks import get_plugin_manager
from mitol.google_sheets_deferrals.models import DeferralRequest
from mitol.google_sheets_deferrals.utils import (
    DeferralRequestRow,
    deferral_sheet_config,
)

log = logging.getLogger(__name__)
User = get_user_model()


class DeferralRequestHandler(GoogleSheetsChangeRequestHandler):
    """Manages the processing of enrollment deferral requests from a spreadsheet"""

    def __init__(self):
        self.pm = get_plugin_manager()
        self.hook = self.pm.hook
        super().__init__(
            spreadsheet_id=settings.MITOL_GOOGLE_SHEETS_ENROLLMENT_CHANGE_SHEET_ID,
            worksheet_id=settings.MITOL_GOOGLE_SHEETS_DEFERRALS_REQUEST_WORKSHEET_ID,
            start_row=settings.MITOL_GOOGLE_SHEETS_DEFERRALS_FIRST_ROW,
            sheet_metadata=deferral_sheet_config,
            request_model_cls=DeferralRequest,
        )

    def is_configured(self):
        """
        Checks for required settings.

        Returns:
            bool: false if required settings are missing
        """

        return super().is_configured() and not get_missing_settings(
            REQUIRED_GOOGLE_SHEETS_DEFERRALS_SETTINGS
        )

    def process_row(
        self, row_index, row_data
    ):  # pylint: disable=too-many-return-statements
        """
        Ensures that the given spreadsheet row is correctly represented in the database,
        attempts to parse it, defers the given enrollment if appropriate, and returns the
        result of processing the row.

        Args:
            row_index (int): The row index according to the spreadsheet
            row_data (list of str): The raw data of the given spreadsheet row

        Returns:
            RowResult or None: An object representing the results of processing the row, or None if
                nothing needs to be done with this row.
        """
        deferral_request, request_created, request_updated = self.get_or_create_request(
            row_data
        )
        try:
            deferral_req_row = DeferralRequestRow.parse_raw_data(row_index, row_data)
        except SheetRowParsingException as exc:
            return RowResult(
                row_index=row_index,
                row_db_record=deferral_request,
                row_object=None,
                result_type=ResultType.FAILED,
                message="Parsing failure: {}".format(str(exc)),
            )
        is_unchanged_error_row = (
            deferral_req_row.errors and not request_created and not request_updated
        )
        if is_unchanged_error_row:
            return RowResult(
                row_index=row_index,
                row_db_record=deferral_request,
                row_object=None,
                result_type=ResultType.IGNORED,
                message=None,
            )
        elif (
            deferral_request.date_completed
            and deferral_req_row.deferral_complete_date is None
        ):
            return RowResult(
                row_index=row_index,
                row_db_record=deferral_request,
                row_object=None,
                result_type=ResultType.OUT_OF_SYNC,
                message=None,
            )

        if deferral_req_row.from_courseware_id == deferral_req_row.to_courseware_id:
            return RowResult(
                row_index=row_index,
                row_db_record=deferral_request,
                row_object=None,
                result_type=ResultType.FAILED,
                message="'from' and 'to' ids are identical",
            )
        results = self.hook.deferrals_process_request(
            deferral_request_row=deferral_req_row
        )

        failed = False
        result_type = None
        message = None

        # walk all the results, if any did not succeed bail and we will return that result
        for result_type, message in results:
            if result_type != ResultType.PROCESSED:
                failed = True
                break

        # if nothing failed, mark the completion date
        if not failed:
            deferral_request.date_completed = now_in_utc()
            deferral_request.save()
        return RowResult(
            row_index=row_index,
            row_db_record=deferral_request,
            row_object=deferral_req_row,
            result_type=result_type,
            message=message,
        )

    def filter_ignored_rows(self, enumerated_rows):
        """
        Takes an iterable of enumerated rows, and returns an iterable of those rows without the ones that should be
        ignored. The row is ignored if Deferral Complete Date is entered or Ignore? column has TRUE

        Args:
            enumerated_rows (Iterable[Tuple[int, List[str]]]): Row indices paired with a list of strings
                representing the data in each row

        Returns:
            Iterable[Tuple[int, List[str]]]: Iterable of data rows without the ones that should be ignored.
        """
        for row_index, row_data in enumerated_rows:
            if item_at_index_or_none(
                row_data, self.sheet_metadata.SKIP_ROW_COL
            ).strip() == GOOGLE_API_TRUE_VAL or item_at_index_or_none(
                row_data, self.sheet_metadata.COMPLETED_DATE_COL
            ):
                continue

            yield row_index, row_data

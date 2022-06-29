"""Enrollment refund API"""
import logging

from django.conf import settings
from django.contrib.auth import get_user_model

from mitol.common.utils.datetime import now_in_utc
from mitol.google_sheets.constants import GOOGLE_API_TRUE_VAL
from mitol.google_sheets.exceptions import SheetRowParsingException
from mitol.google_sheets.sheet_handler_api import EnrollmentChangeRequestHandler
from mitol.google_sheets.utils import (
    ResultType,
    RowResult,
    clean_sheet_value,
    parse_sheet_date_only_str,
)
from mitol.google_sheets_refunds.hooks import get_plugin_manager
from mitol.google_sheets_refunds.models import RefundRequest
from mitol.google_sheets_refunds.utils import refund_sheet_config

log = logging.getLogger(__name__)
User = get_user_model()


class RefundRequestRow:  # pylint: disable=too-many-instance-attributes
    """Represents a row of the refund request sheet"""

    def __init__(
        self,
        row_index,
        response_id,
        request_date,
        learner_email,
        zendesk_ticket_no,
        requester_email,
        product_id,
        order_id,
        order_type,
        finance_email,
        finance_approve_date,
        finance_notes,
        refund_processor,
        refund_complete_date,
        errors,
        skip_row,
    ):  # pylint: disable=too-many-arguments,too-many-locals
        self.row_index = row_index
        self.response_id = response_id
        self.request_date = request_date
        self.learner_email = learner_email
        self.zendesk_ticket_no = zendesk_ticket_no
        self.requester_email = requester_email
        self.product_id = product_id
        self.order_id = order_id
        self.order_type = order_type
        self.finance_email = finance_email
        self.finance_approve_date = finance_approve_date
        self.finance_notes = finance_notes
        self.refund_processor = refund_processor
        self.refund_complete_date = refund_complete_date
        self.errors = errors
        self.skip_row = skip_row

    @classmethod
    def parse_raw_data(cls, row_index, raw_row_data):
        """
        Parses raw row data

        Args:
            row_index (int): The row index according to the spreadsheet (not zero-based)
            raw_row_data (list of str): The raw row data

        Raises:
            SheetRowParsingException: Raised if the row could not be parsed
        """
        raw_row_data = list(map(clean_sheet_value, raw_row_data))
        try:
            return cls(
                row_index=row_index,
                response_id=int(raw_row_data[refund_sheet_config.FORM_RESPONSE_ID_COL]),
                request_date=raw_row_data[1],
                learner_email=raw_row_data[2],
                zendesk_ticket_no=raw_row_data[3],
                requester_email=raw_row_data[4],
                product_id=raw_row_data[5],
                order_id=int(raw_row_data[6]),
                order_type=raw_row_data[7],
                finance_email=raw_row_data[8],
                finance_approve_date=parse_sheet_date_only_str(raw_row_data[9]),
                finance_notes=raw_row_data[10],
                refund_processor=raw_row_data[refund_sheet_config.PROCESSOR_COL],
                refund_complete_date=parse_sheet_date_only_str(
                    raw_row_data[refund_sheet_config.COMPLETED_DATE_COL]
                ),
                errors=raw_row_data[refund_sheet_config.ERROR_COL],
                skip_row=(
                    raw_row_data[refund_sheet_config.SKIP_ROW_COL]
                    == GOOGLE_API_TRUE_VAL
                ),
            )
        except Exception as exc:
            raise SheetRowParsingException(str(exc)) from exc


class RefundRequestHandler(EnrollmentChangeRequestHandler):
    """Manages the processing of refund requests from a spreadsheet"""

    def __init__(self):
        self.pm = get_plugin_manager()
        self.hook = self.pm.hook
        super().__init__(
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

        for result_type, message in self.hook.refunds_process_request(refund_request):
            if result_type != ResultType.PROCESSED:
                # TODO: rollback the surrounding transaction
                return RowResult(
                    row_index=row_index,
                    row_db_record=refund_request,
                    row_object=None,
                    result_type=ResultType.PROCESSED,
                    message=message,
                )

        refund_request.date_completed = now_in_utc()
        refund_request.save()

        return RowResult(
            row_index=row_index,
            row_db_record=refund_request,
            row_object=row_object,
            result_type=result_type,
            message=message,
        )

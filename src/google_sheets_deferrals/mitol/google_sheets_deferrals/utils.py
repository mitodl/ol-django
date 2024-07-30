"""Google Sheets Deferrals app util functions"""
from django.conf import settings

from mitol.google_sheets.constants import GOOGLE_API_TRUE_VAL
from mitol.google_sheets.exceptions import SheetRowParsingException
from mitol.google_sheets.utils import (
    SingletonSheetConfig,
    clean_sheet_value,
    get_column_letter,
    parse_sheet_date_only_str,
)
from mitol.google_sheets_deferrals.constants import (
    SHEET_TYPE_ENROLL_CHANGE,
    WORKSHEET_TYPE_DEFERRAL,
)


class DeferralRequestRow:  # pylint: disable=too-many-instance-attributes
    """Represents a row of the deferral request sheet"""

    def __init__(
        self,
        row_index,
        response_id,
        request_date,
        learner_email,
        zendesk_ticket_no,
        requester_email,
        from_courseware_id,
        to_courseware_id,
        deferral_processor,
        deferral_complete_date,
        errors,
        skip_row,
    ):  # pylint: disable=too-many-arguments,too-many-locals
        self.row_index = row_index
        self.response_id = response_id
        self.request_date = request_date
        self.learner_email = learner_email
        self.zendesk_ticket_no = zendesk_ticket_no
        self.requester_email = requester_email
        self.from_courseware_id = from_courseware_id
        self.to_courseware_id = to_courseware_id
        self.deferral_processor = deferral_processor
        self.deferral_complete_date = deferral_complete_date
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
                response_id=int(
                    raw_row_data[deferral_sheet_config.FORM_RESPONSE_ID_COL]
                ),
                request_date=raw_row_data[1],
                learner_email=raw_row_data[2],
                zendesk_ticket_no=raw_row_data[3],
                requester_email=raw_row_data[4],
                from_courseware_id=raw_row_data[5],
                to_courseware_id=raw_row_data[6],
                deferral_processor=raw_row_data[deferral_sheet_config.PROCESSOR_COL],
                deferral_complete_date=parse_sheet_date_only_str(
                    raw_row_data[deferral_sheet_config.COMPLETED_DATE_COL]
                ),
                errors=raw_row_data[deferral_sheet_config.ERROR_COL],
                skip_row=(
                    raw_row_data[deferral_sheet_config.SKIP_ROW_COL]
                    == GOOGLE_API_TRUE_VAL
                ),
            )
        except Exception as exc:
            raise SheetRowParsingException(str(exc)) from exc


class DeferralRequestSheetConfig(
    SingletonSheetConfig, subclass_type=WORKSHEET_TYPE_DEFERRAL
):
    """Metadata for the refund request spreadsheet"""

    FORM_RESPONSE_ID_COL = 0

    PROCESSOR_COL = settings.MITOL_GOOGLE_SHEETS_DEFERRALS_PROCESSOR_COL
    COMPLETED_DATE_COL = settings.MITOL_GOOGLE_SHEETS_DEFERRALS_COMPLETED_DATE_COL
    ERROR_COL = settings.MITOL_GOOGLE_SHEETS_DEFERRALS_ERROR_COL
    SKIP_ROW_COL = settings.MITOL_GOOGLE_SHEETS_DEFERRALS_SKIP_ROW_COL

    def __init__(self):
        self.sheet_type = SHEET_TYPE_ENROLL_CHANGE
        self.sheet_name = "Enrollment Change Request sheet"
        self.worksheet_type = WORKSHEET_TYPE_DEFERRAL
        self.worksheet_name = "Deferrals"
        self.first_data_row = settings.MITOL_GOOGLE_SHEETS_DEFERRALS_FIRST_ROW
        self.num_columns = self.SKIP_ROW_COL + 1
        self.non_input_column_indices = set(
            # Response ID column
            [self.FORM_RESPONSE_ID_COL]
            + list(  # Every column from the finance columns to the end of the row
                range(8, self.num_columns)
            )
        )
        self.sheet_file_id = settings.MITOL_GOOGLE_SHEETS_ENROLLMENT_CHANGE_SHEET_ID

        self.PROCESSOR_COL_LETTER = get_column_letter(self.PROCESSOR_COL)
        self.ERROR_COL_LETTER = get_column_letter(self.ERROR_COL)


deferral_sheet_config = DeferralRequestSheetConfig()

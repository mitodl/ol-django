"""Google Sheets Refunds app util functions"""
from mitol.google_sheets.utils import SingletonSheetConfig, get_column_letter
from mitol.google_sheets_refunds.contants import (
    SHEET_TYPE_ENROLL_CHANGE,
    WORKSHEET_TYPE_REFUND,
)


class RefundRequestSheetConfig(
    SingletonSheetConfig, subclass_type=WORKSHEET_TYPE_REFUND
):
    """Metadata for the refund request spreadsheet"""

    FORM_RESPONSE_ID_COL = 0

    PROCESSOR_COL = settings.MITOL_GOOGLE_SHEETS_REFUNDS_PROCESSOR_COL
    COMPLETED_DATE_COL = settings.MITOL_GOOGLE_SHEETS_REFUNDS_COMPLETED_DATE_COL
    ERROR_COL = settings.MITOL_GOOGLE_SHEETS_REFUNDS_ERROR_COL
    SKIP_ROW_COL = settings.MITOL_GOOGLE_SHEETS_REFUNDS_SKIP_ROW_COL

    def __init__(self):
        self.sheet_type = SHEET_TYPE_ENROLL_CHANGE
        self.sheet_name = "Enrollment Change Request sheet"
        self.worksheet_type = WORKSHEET_TYPE_REFUND
        self.worksheet_name = "Refunds"
        self.first_data_row = settings.MITOL_GOOGLE_SHEETS_REFUNDS_FIRST_ROW
        self.num_columns = self.SKIP_ROW_COL + 1
        self.non_input_column_indices = set(
            # Response ID column
            [self.FORM_RESPONSE_ID_COL]
            +
            # Every column from the finance columns to the end of the row
            list(range(8, self.num_columns))
        )
        self.sheet_file_id = settings.MITOL_GOOGLE_SHEETS_ENROLLMENT_CHANGE_SHEET_ID

        self.PROCESSOR_COL_LETTER = get_column_letter(self.PROCESSOR_COL)
        self.ERROR_COL_LETTER = get_column_letter(self.ERROR_COL)


refund_sheet_config = RefundRequestSheetConfig()

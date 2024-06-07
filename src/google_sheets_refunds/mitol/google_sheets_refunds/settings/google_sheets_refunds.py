"""google sheets refunds settings """
from mitol.common.envs import get_int, get_string

MITOL_GOOGLE_SHEETS_REFUNDS_REQUEST_WORKSHEET_ID = get_string(
    name="MITOL_GOOGLE_SHEETS_REFUNDS_REQUEST_WORKSHEET_ID",
    description=(
        "ID of the worksheet within the enrollment change request spreadsheet that contains enrollment refund requests"
    ),
)
MITOL_GOOGLE_SHEETS_REFUNDS_PROCESSOR_COL = get_int(
    name="MITOL_GOOGLE_SHEETS_REFUNDS_PROCESSOR_COL",
    default=11,
    description=(
        "The zero-based index of the enrollment change sheet column that contains the user that processed the row"
    ),
)
MITOL_GOOGLE_SHEETS_REFUNDS_COMPLETED_DATE_COL = get_int(
    name="MITOL_GOOGLE_SHEETS_REFUNDS_COMPLETED_DATE_COL",
    default=13,
    description=(
        "The zero-based index of the enrollment change sheet column that contains the row completion date"
    ),
)
MITOL_GOOGLE_SHEETS_REFUNDS_ERROR_COL = get_int(
    name="MITOL_GOOGLE_SHEETS_REFUNDS_ERROR_COL",
    default=14,
    description=(
        "The zero-based index of the enrollment change sheet column that contains row processing error messages"
    ),
)
MITOL_GOOGLE_SHEETS_REFUNDS_SKIP_ROW_COL = get_int(
    name="MITOL_GOOGLE_SHEETS_REFUNDS_SKIP_ROW_COL",
    default=15,
    description=(
        "The zero-based index of the enrollment change sheet column that indicates whether the row should be skipped"
    ),
)
MITOL_GOOGLE_SHEETS_REFUNDS_FIRST_ROW = get_int(
    name="MITOL_GOOGLE_SHEETS_REFUNDS_FIRST_ROW",
    default=4,
    description=(
        "The first row (as it appears in the spreadsheet) of data that our scripts should consider "
        "processing in the refund request spreadsheet"
    ),
)

MITOL_GOOGLE_SHEETS_REFUNDS_PLUGINS = get_string(
    name="MITOL_GOOGLE_SHEETS_REFUNDS_PLUGINS",
    description="The path to your refund plugin, example: app.plugins.RefundPlugin",
)

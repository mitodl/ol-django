"""google sheets deferrals settings """
from mitol.common.envs import get_int, get_string

MITOL_GOOGLE_SHEETS_DEFERRALS_REQUEST_WORKSHEET_ID = get_string(
    name="MITOL_GOOGLE_SHEETS_DEFERRALS_REQUEST_WORKSHEET_ID",
    description=(
        "ID of the worksheet within the enrollment change request spreadsheet that contains "
        "enrollment deferral requests"
    ),
)
MITOL_GOOGLE_SHEETS_DEFERRALS_FIRST_ROW = get_int(
    name="MITOL_GOOGLE_SHEETS_DEFERRALS_FIRST_ROW",
    default=5,
    description=(
        "The first row (as it appears in the spreadsheet) of data that our scripts should consider "
        "processing in the deferral request spreadsheet"
    ),
)

MITOL_GOOGLE_SHEETS_DEFERRALS_PLUGINS = get_string(
    name="MITOL_GOOGLE_SHEETS_DEFERRALS_PLUGINS",
    description="The path to your deferral plugin, example: app.plugins.DeferralPlugin",
)
MITOL_GOOGLE_SHEETS_DEFERRALS_PROCESSOR_COL = get_int(
    name="MITOL_GOOGLE_SHEETS_DEFERRALS_PROCESSOR_COL",
    default=7,
    description=(
        "The zero-based index of the enrollment change sheet column that contains the user that processed the row"
    ),
)
MITOL_GOOGLE_SHEETS_DEFERRALS_COMPLETED_DATE_COL = get_int(
    name="MITOL_GOOGLE_SHEETS_DEFERRALS_COMPLETED_DATE_COL",
    default=8,
    description=(
        "The zero-based index of the enrollment change sheet column that contains the row completion date"
    ),
)
MITOL_GOOGLE_SHEETS_DEFERRALS_ERROR_COL = get_int(
    name="MITOL_GOOGLE_SHEETS_DEFERRALS_ERROR_COL",
    default=9,
    description=(
        "The zero-based index of the enrollment change sheet column that contains row processing error messages"
    ),
)
MITOL_GOOGLE_SHEETS_DEFERRALS_SKIP_ROW_COL = get_int(
    name="MITOL_GOOGLE_SHEETS_DEFERRALS_SKIP_ROW_COL",
    default=10,
    description=(
        "The zero-based index of the enrollment change sheet column that indicates whether the row should be skipped"
    ),
)

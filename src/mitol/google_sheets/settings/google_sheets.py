"""google sheets settings """
import pytz

from mitol.common.envs import get_string

MITOL_GOOGLE_SHEETS_PROCESSOR_APP_NAME = get_string(
    name="MITOL_GOOGLE_SHEETS_PROCESSOR_APP_NAME",
    description="Name of the app processing the request",
    required=False,
)
MITOL_GOOGLE_SHEETS_GOOGLE_ACCOUNT_EMAIL_DOMAIN = get_string(
    name="MITOL_GOOGLE_SHEETS_GOOGLE_ACCOUNT_EMAIL_DOMAIN",
    description="Email domain of the google service account",
    default="iam.gserviceaccount.com",
    required=False,
)

MITOL_GOOGLE_SHEETS_DRIVE_SERVICE_ACCOUNT_CREDS = get_string(
    name="MITOL_GOOGLE_SHEETS_DRIVE_SERVICE_ACCOUNT_CREDS",
    default=None,
    description="The contents of the Service Account credentials JSON to use for Google API auth",
)
MITOL_GOOGLE_SHEETS_DRIVE_CLIENT_ID = get_string(
    name="MITOL_GOOGLE_SHEETS_DRIVE_CLIENT_ID",
    default=None,
    description="Client ID from Google API credentials",
)
MITOL_GOOGLE_SHEETS_DRIVE_CLIENT_SECRET = get_string(
    name="MITOL_GOOGLE_SHEETS_DRIVE_CLIENT_SECRET",
    default=None,
    description="Client secret from Google API credentials",
)
MITOL_GOOGLE_SHEETS_DRIVE_API_PROJECT_ID = get_string(
    name="MITOL_GOOGLE_SHEETS_DRIVE_API_PROJECT_ID",
    default=None,
    description="ID for the Google API project where the credentials were created",
)
MITOL_GOOGLE_SHEETS_DRIVE_SHARED_ID = get_string(
    name="MITOL_GOOGLE_SHEETS_DRIVE_SHARED_ID",
    default=None,
    description="ID of the Shared Drive (a.k.a. Team Drive). This is equal to the top-level folder ID.",
)
MITOL_GOOGLE_SHEETS_ENROLLMENT_CHANGE_SHEET_ID = get_string(
    name="MITOL_GOOGLE_SHEETS_ENROLLMENT_CHANGE_SHEET_ID",
    default=None,
    description=(
        "ID of the Google Sheet that contains the enrollment change request worksheets (refunds, transfers, etc)"
    ),
)
MITOL_GOOGLE_SHEETS_DATE_FORMAT = get_string(
    name="MITOL_GOOGLE_SHEETS_DATE_FORMAT",
    default="%m/%d/%Y",
    description="Python strptime format for date columns (no time) in enrollment management spreadsheets",
)
_sheets_date_timezone = get_string(
    name="MITOL_GOOGLE_SHEETS_DATE_TIMEZONE",
    default="UTC",
    description=(
        "The name of the timezone that should be assumed for date/time values in spreadsheets. "
        "Choose from a value in the TZ database (https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)."
    ),
)
MITOL_GOOGLE_SHEETS_DATE_TIMEZONE = pytz.timezone(_sheets_date_timezone)

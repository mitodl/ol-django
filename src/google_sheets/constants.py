"""Sheets app constants"""

REQUIRED_GOOGLE_API_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
DEFAULT_GOOGLE_EXPIRE_TIMEDELTA = dict(minutes=60)

SHEETS_VALUE_REQUEST_PAGE_SIZE = 50

# The index of the first row of a spreadsheet according to Google
GOOGLE_SHEET_FIRST_ROW = 1
GOOGLE_AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
GOOGLE_AUTH_PROVIDER_X509_CERT_URL = "https://www.googleapis.com/oauth2/v1/certs"
GOOGLE_DATE_TIME_FORMAT = "DATE_TIME"
GOOGLE_API_NOTIFICATION_TYPE = "webhook"
GOOGLE_API_FILE_WATCH_KIND = "api#channel"
GOOGLE_API_TRUE_VAL = "TRUE"

REQUIRED_GOOGLE_SHEETS_SETTINGS = [
    "MITOL_GOOGLE_SHEETS_PROCESSOR_APP_NAME",
    "MITOL_GOOGLE_SHEETS_DRIVE_API_PROJECT_ID",
]

REQUIRED_GOOGLE_SHEETS_SERVICE_ACCOUNT_SETTINGS = [
    "MITOL_GOOGLE_SHEETS_DRIVE_SERVICE_ACCOUNT_CREDS",
]

REQUIRED_GOOGLE_SHEETS_CLIENT_SETTINGS = [
    "MITOL_GOOGLE_SHEETS_DRIVE_CLIENT_ID",
    "MITOL_GOOGLE_SHEETS_DRIVE_CLIENT_SECRET",
]

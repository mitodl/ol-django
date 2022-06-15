"""Sheets app constants"""

REQUIRED_GOOGLE_API_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
DEFAULT_GOOGLE_EXPIRE_TIMEDELTA = dict(minutes=60)

SHEETS_VALUE_REQUEST_PAGE_SIZE = 50
SHEET_TYPE_COUPON_REQUEST = "enrollrequest"
SHEET_TYPE_COUPON_ASSIGN = "enrollassign"
SHEET_TYPE_ENROLL_CHANGE = "enrollchange"
VALID_SHEET_TYPES = [
    SHEET_TYPE_COUPON_REQUEST,
    SHEET_TYPE_COUPON_ASSIGN,
    SHEET_TYPE_ENROLL_CHANGE,
]
WORKSHEET_TYPE_REFUND = "refund"
WORKSHEET_TYPE_DEFERRAL = "defer"
SHEET_RENEWAL_RECORD_LIMIT = 20

# The index of the first row of a spreadsheet according to Google
GOOGLE_SHEET_FIRST_ROW = 1
GOOGLE_AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
GOOGLE_AUTH_PROVIDER_X509_CERT_URL = "https://www.googleapis.com/oauth2/v1/certs"
GOOGLE_DATE_TIME_FORMAT = "DATE_TIME"
GOOGLE_SERVICE_ACCOUNT_EMAIL_DOMAIN = "iam.gserviceaccount.com"
GOOGLE_API_NOTIFICATION_TYPE = "webhook"
GOOGLE_API_FILE_WATCH_KIND = "api#channel"
GOOGLE_API_TRUE_VAL = "TRUE"

ASSIGNMENT_MESSAGES_COMPLETED_KEY = "assignmentsCompleted"
ASSIGNMENT_MESSAGES_COMPLETED_DATE_KEY = "assignmentsCompletedDate"
ASSIGNMENT_SHEET_PREFIX = "Enrollment Codes"
ASSIGNMENT_SHEET_ASSIGNED_STATUS = "assigned"
ASSIGNMENT_SHEET_ENROLLED_STATUS = "enrolled"
ASSIGNMENT_SHEET_INVALID_STATUS = "invalid"

ASSIGNMENT_SHEET_MAX_AGE_DAYS = 15
ASSIGNMENT_SHEET_EMAIL_RETRY_MINUTES = 10

GOOGLE_SHEET_PROCESSOR_APP_NAME = "MITx Online app"
REFUND_SHEET_ORDER_TYPE_FULL_COUPON = "Enrollment Code"
REFUND_SHEET_ORDER_TYPE_PAID = "Paid via Cybersource"

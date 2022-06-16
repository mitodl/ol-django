"""google sheets settings """
from mitol.common.envs import get_string

MITOL_GOOGLE_SHEET_PROCESSOR_APP_NAME = get_string(
    name="MITOL_GOOGLE_SHEET_PROCESSOR_APP_NAME",
    description="Name of the app processing the request",
    required=False,
)
MITOL_GOOGLE_SHEETS_GOOGLE_ACCOUNT_EMAIL_DOMAIN = get_string(
    name="MITOL_GOOGLE_SHEETS_GOOGLE_ACCOUNT_EMAIL_DOMAIN",
    description="Email domain of the google service account",
    default="iam.gserviceaccount.com",
    required=False,
)

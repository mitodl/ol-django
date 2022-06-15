"""google sheets settings """
from mitol.common.envs import get_string

MITOL_GOOGLE_SHEET_PROCESSOR_APP_NAME = get_string(
    name="MITOL_GOOGLE_SHEET_PROCESSOR_APP_NAME",
    description="Name of the app processing the request",
    required=False,
)

"""Google Sheets app AppConfigs"""

import os

from mitol.common.apps import BaseApp


class GoogleSheetsDeferralsApp(BaseApp):
    """Default configuration for the Google Sheets Deferrals app"""

    name = "mitol.google_sheets_deferrals"
    label = "google_sheets_deferrals"
    verbose_name = "Google Sheets Deferrals"
    default_auto_field = "django.db.models.BigAutoField"

    required_settings = []  # noqa: RUF012

    # necessary because this is a namespaced app
    path = os.path.dirname(os.path.abspath(__file__))  # noqa: PTH100, PTH120

"""Google Sheets app AppConfigs"""

import os

from mitol.common.apps import BaseApp


class GoogleSheetsRefundsApp(BaseApp):
    """Default configuration for the Google Sheets Refunds app"""

    # Explicitly set default auto field type to avoid migrations in Django 3.2+
    default_auto_field = "django.db.models.BigAutoField"
    name = "mitol.google_sheets_refunds"
    label = "google_sheets_refunds"
    verbose_name = "Google Sheets Refunds"

    required_settings = []

    # necessary because this is a namespaced app
    path = os.path.dirname(os.path.abspath(__file__))  # noqa: PTH100, PTH120

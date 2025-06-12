"""Google Sheets app AppConfigs"""

import os

from mitol.common.apps import BaseApp


class GoogleSheetsApp(BaseApp):
    """Default configuration for the Google Sheets app"""

    # Explicitly set default auto field type to avoid migrations in Django 3.2+
    default_auto_field = "django.db.models.BigAutoField"

    name = "mitol.google_sheets"
    label = "google_sheets"
    verbose_name = "Google Sheets"

    required_settings = []

    # necessary because this is a namespaced app
    path = os.path.dirname(os.path.abspath(__file__))  # noqa: PTH100, PTH120

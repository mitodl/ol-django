"""Google Sheets app AppConfigs"""
import os

from mitol.common.apps import BaseApp


class GoogleSheetsApp(BaseApp):
    """Default configuration for the Google Sheets app"""

    name = "mitol.google_sheets"
    label = "google_sheets"
    verbose_name = "Google Sheets"

    required_settings = []

    # necessary because this is a namespaced app
    path = os.path.dirname(os.path.abspath(__file__))

"""Google Sheets app AppConfigs"""
import os

from mitol.common.apps import BaseApp


class GoogleSheetsRefundsApp(BaseApp):
    """Default configuration for the Google Sheets Refunds app"""

    name = "mitol.google_sheets_refunds"
    label = "google_sheets_refunds"
    verbose_name = "Google Sheets Refunds"

    required_settings = []

    # necessary because this is a namespaced app
    path = os.path.dirname(os.path.abspath(__file__))

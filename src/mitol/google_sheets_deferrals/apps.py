"""Google Sheets app AppConfigs"""
import os

from mitol.common.apps import BaseApp


class GoogleSheetsDeferralsApp(BaseApp):
    """Default configuration for the Google Sheets Deferrals app"""

    name = "mitol.google_sheets_deferrals"
    label = "google_sheets_deferrals"
    verbose_name = "Google Sheets Deferrals"

    required_settings = []

    # necessary because this is a namespaced app
    path = os.path.dirname(os.path.abspath(__file__))

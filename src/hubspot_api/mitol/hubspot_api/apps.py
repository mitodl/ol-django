"""Hubspot app AppConfigs"""
import os

from mitol.common.apps import BaseApp


class HubspotApiApp(BaseApp):
    """Default configuration for the payment gateway app"""

    name = "mitol.hubspot_api"
    label = "hubspot_api"
    verbose_name = "Hubspot OL Integration"

    required_settings = []

    # necessary because this is a namespaced app
    path = os.path.dirname(os.path.abspath(__file__))

"""Hubspot app AppConfigs"""

import os

from mitol.common.apps import BaseApp


class HubspotApiApp(BaseApp):
    """Default configuration for the payment gateway app"""

    name = "mitol.hubspot_api"
    label = "hubspot_api"
    verbose_name = "Hubspot OL Integration"

    required_settings = []  # noqa: RUF012

    # necessary because this is a namespaced app
    path = os.path.dirname(os.path.abspath(__file__))  # noqa: PTH100, PTH120

"""GeoIP app AppConfigs"""
import os

from mitol.common.apps import BaseApp


class GeoIPApp(BaseApp):
    """Default configuration for the GeoIP app"""

    name = "mitol.geoip"
    label = "geoip"
    verbose_name = "GeoIP"

    required_settings = []

    # necessary because this is a namespaced app
    path = os.path.dirname(os.path.abspath(__file__))

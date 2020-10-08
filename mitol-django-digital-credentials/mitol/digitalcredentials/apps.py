"""Digital credentials app AppConfigs"""
import os

from django.apps import AppConfig


class DigitalCredentialsApp(AppConfig):
    """Default configuration for the digital credentials app"""

    name = "mitol.digitalcredentials"
    label = "digitalcredentials"
    verbose_name = "Digital Credentials"

    # necessary because this is a namespaced app
    path = os.path.dirname(os.path.abspath(__file__))

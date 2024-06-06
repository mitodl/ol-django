"""Common app AppConfigs"""
import os

from mitol.common.apps import AppConfig


class OAuthToolkitExtensionsApp(AppConfig):
    """Default configuration for the oauth toolkit extentions app"""

    name = "mitol.oauth_toolkit_extensions"
    label = "oauth_toolkit_extensions"
    verbose_name = "oauth_toolkit_extensions"

    # necessary because this is a namespaced app
    path = os.path.dirname(os.path.abspath(__file__))

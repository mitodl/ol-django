"""Common app AppConfigs"""
import os

from django.apps import AppConfig


class CommonApp(AppConfig):
    """Default configuration for the common app"""

    name = "mitol.common"
    label = "common"
    verbose_name = "Common"

    # necessary because this is a namespaced app
    path = os.path.dirname(os.path.abspath(__file__))

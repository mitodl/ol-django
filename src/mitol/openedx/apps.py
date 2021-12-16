"""Openedx app AppConfig"""
import os
from django.apps import AppConfig


class OpenedxApp(AppConfig):
    """Default configuration for the openedx app"""

    name = "mitol.openedx"
    label = "openedx"
    verbose_name = "Openedx"

    path = os.path.dirname(os.path.abspath(__file__))

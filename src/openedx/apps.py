"""Openedx app AppConfig"""
import os

from django.apps import AppConfig


class OpenedxApp(AppConfig):
    """Default configuration for the openedx app"""

    name = "mitol.openedx"
    label = "openedx"
    verbose_name = "Openedx"

    # necessary because this is a namespaced app
    path = os.path.dirname(os.path.abspath(__file__))


class TransitionalOpenedxApp(AppConfig):
    """Openedx AppConfig for transitioning a project with an existing 'openedx' app"""

    name = "mitol.openedx"
    label = "transitional_openedx"
    verbose_name = "Openedx"

    # necessary because this is a namespaced app
    path = os.path.dirname(os.path.abspath(__file__))

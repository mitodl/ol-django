"""Uvtestapp app AppConfig"""

import os

from django.apps import AppConfig


class UvtestappApp(AppConfig):
    """Default configuration for the uvtestapp app"""

    name = "mitol.uvtestapp"
    label = "uvtestapp"
    verbose_name = "Uvtestapp"

    # necessary because this is a namespaced app
    path = os.path.dirname(os.path.abspath(__file__))  # noqa: PTH100, PTH120


class TransitionalUvtestappApp(AppConfig):
    """AppConfig for transitioning a project with an existing 'uvtestapp' app"""

    name = "mitol.uvtestapp"
    label = "transitional_uvtestapp"
    verbose_name = "Uvtestapp"

    # necessary because this is a namespaced app
    path = os.path.dirname(os.path.abspath(__file__))  # noqa: PTH100, PTH120

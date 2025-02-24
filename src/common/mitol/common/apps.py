"""Common app AppConfigs"""

import os

from django.apps import AppConfig
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class BaseApp(AppConfig):
    """Base application class"""

    required_settings: list[str] = []

    def validate_required_settings(self):
        """
        Verify that the required settings have been set.

        This allows verifying settings that an application requires, but
        aren't necessarily covered by a call to `mitol.common.envs` functions.
        """
        missing_settings = []

        for setting_name in self.required_settings:
            if not hasattr(settings, setting_name):
                missing_settings.append(setting_name)  # noqa: PERF401

        if missing_settings:
            raise ImproperlyConfigured(
                "The following settings are missing: {}. You need to add these environment variables in .env file.".format(  # noqa: EM103, E501
                    ", ".join(missing_settings)
                )
            )

    def ready(self):
        """The application is ready"""  # noqa: D401
        self.validate_required_settings()


class CommonApp(AppConfig):
    """Default configuration for the common app"""

    name = "mitol.common"
    label = "common"
    verbose_name = "Common"

    # necessary because this is a namespaced app
    path = os.path.dirname(os.path.abspath(__file__))  # noqa: PTH100, PTH120

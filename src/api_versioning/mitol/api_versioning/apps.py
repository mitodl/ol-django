"""ApiVersioning app AppConfig."""

import importlib
import os

from django.apps import AppConfig, apps
from django.utils.module_loading import module_has_submodule

from . import checks  # noqa: F401  (registers Django system checks on import)


class ApiVersioningApp(AppConfig):
    """Default configuration for the api_versioning app."""

    name = "mitol.api_versioning"
    label = "api_versioning"
    verbose_name = "API Versioning"

    # necessary because this is a namespaced app
    path = os.path.dirname(os.path.abspath(__file__))  # noqa: PTH100, PTH120

    def ready(self):
        """Auto-discover transforms modules in all installed apps.

        Looks for a `transforms` submodule in each installed app
        (e.g., `learning_resources.transforms`). Importing the module
        triggers the Transform metaclass, which auto-registers each
        Transform subclass with the version registry.

        Only attempts to import `transforms` if the submodule actually
        exists, so real ImportErrors inside the module are not suppressed.
        """
        for app_config in apps.get_app_configs():
            if module_has_submodule(app_config.module, "transforms"):
                module_name = f"{app_config.name}.transforms"
                importlib.import_module(module_name)


class TransitionalApiVersioningApp(AppConfig):
    """AppConfig for transitioning a project with an existing app."""

    name = "mitol.api_versioning"
    label = "transitional_api_versioning"
    verbose_name = "API Versioning"

    # necessary because this is a namespaced app
    path = os.path.dirname(os.path.abspath(__file__))  # noqa: PTH100, PTH120

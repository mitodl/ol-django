"""Common app AppConfigs"""

import os

from django.apps import AppConfig


class KeycloakApp(AppConfig):
    """Default configuration for the keycloakapp"""

    name = "mitol.keycloak"
    label = "keycloak"
    verbose_name = "Keycloak"

    # necessary because this is a namespaced app
    path = os.path.dirname(os.path.abspath(__file__))  # noqa: PTH100, PTH120

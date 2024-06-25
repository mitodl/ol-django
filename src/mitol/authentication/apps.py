"""Authentication Apps"""

import os

from django.apps import AppConfig


class AuthenticationApp(AppConfig):
    """Authentication AppConfig"""

    name = "mitol.authentication"
    label = "authentication"
    verbose_name = "authentication"

    # necessary because this is a namespaced app
    path = os.path.dirname(os.path.abspath(__file__))  # noqa: PTH100, PTH120


class TransitionalAuthenticationApp(AppConfig):
    """Authentication AppConfig for transitioning a project with an existing 'authentication' app"""  # noqa: E501

    name = "mitol.authentication"
    label = "transitional_authentication"
    verbose_name = "authentication"

    # necessary because this is a namespaced app
    path = os.path.dirname(os.path.abspath(__file__))  # noqa: PTH100, PTH120

"""Authentication Apps"""
from django.apps import AppConfig


class AuthenticationConfig(AppConfig):
    """Authentication AppConfig"""

    name = "authentication"


class TransitionalAuthenticationConfig(AppConfig):
    """Authentication AppConfig for transitioning a project with an existing 'authentication' app"""

    name = "transitional_authentication"

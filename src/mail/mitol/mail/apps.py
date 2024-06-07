"""Mail app AppConfigs"""
import os

from django.apps import AppConfig


class MailApp(AppConfig):
    """Default configuration for the mail app"""

    name = "mitol.mail"
    label = "mail"
    verbose_name = "Mail"

    # necessary because this is a namespaced app
    path = os.path.dirname(os.path.abspath(__file__))

import os

from django.apps import AppConfig


class ScimApp(AppConfig):
    name = "mitol.scim"
    label = "scim"
    verbose_name = "SCIM"

    required_settings = []

    # necessary because this is a namespaced app
    path = os.path.dirname(os.path.abspath(__file__))  # noqa: PTH100, PTH120

import os

from django.apps import AppConfig


class ScimApp(AppConfig):
    name = "mitol.scim"
    label = "scim"
    verbose_name = "SCIM"

    required_settings = []

    default_auto_field = "django.db.models.BigAutoField"

    # necessary because this is a namespaced app
    path = os.path.dirname(os.path.abspath(__file__))  # noqa: PTH100, PTH120

    def ready(self) -> None:
        pass

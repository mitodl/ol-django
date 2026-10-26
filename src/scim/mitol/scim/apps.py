import os

from django.apps import AppConfig
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import FieldDoesNotExist, ImproperlyConfigured


class ScimApp(AppConfig):
    name = "mitol.scim"
    label = "scim"
    verbose_name = "SCIM"

    required_settings = []

    default_auto_field = "django.db.models.BigAutoField"

    # necessary because this is a namespaced app
    path = os.path.dirname(os.path.abspath(__file__))  # noqa: PTH100, PTH120

    def ready(self) -> None:
        validate_username_filter_fields()


def validate_username_filter_fields() -> None:
    """
    Check that each MITOL_SCIM_USERNAME_FILTER_FIELDS entry is a user column.

    The fields are only queried when a client filters on userName, so a typo
    would otherwise surface as a FieldError, and a 500 to the client, on the
    first lookup rather than at startup.

    :raises ImproperlyConfigured: if an entry isn't a concrete, non-relational
        field on the user model
    """
    user_model = get_user_model()
    for field_name in settings.MITOL_SCIM_USERNAME_FILTER_FIELDS:
        if not field_name:
            continue
        try:
            field = user_model._meta.get_field(field_name)  # noqa: SLF001
        except FieldDoesNotExist as exc:
            msg = (
                f"MITOL_SCIM_USERNAME_FILTER_FIELDS: {user_model.__name__} "
                f"has no field {field_name!r}"
            )
            raise ImproperlyConfigured(msg) from exc
        if not field.concrete or field.is_relation:
            msg = (
                f"MITOL_SCIM_USERNAME_FILTER_FIELDS: {field_name!r} must be a "
                f"column on {user_model.__name__}, not a relation"
            )
            raise ImproperlyConfigured(msg)

"""Common factories"""

from django.conf import settings
from django.utils.module_loading import import_string

UserFactory = import_string(
    getattr(
        settings,
        "MITOL_COMMON_USER_FACTORY",
        "mitol.common.factories.defaults.UserFactory",
    )
)

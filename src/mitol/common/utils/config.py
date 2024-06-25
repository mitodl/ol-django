from typing import List  # noqa: D100

from django.conf import settings


def get_missing_settings(required_settings: List[str]) -> List[str]:  # noqa: FA100
    """Return a list of settings that are missing"""
    return [
        variable
        for variable in required_settings
        if getattr(settings, variable, None) is None
    ]

from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def get_missing_settings(required_settings: list[str]) -> list[str]:
    """Return a list of settings that are missing"""
    return [
        variable
        for variable in required_settings
        if getattr(settings, variable, None) is None
    ]


class SettingsRef:
    """
    Class attribute that reads a Django setting on access

    Use this instead of reading a setting into a class attribute at import time
    or into an instance attribute in __init__. Both of those freeze the value,
    so override_settings can't reach an object that already exists - which, for
    a module-level singleton, means it can never reach it at all.

    This is a non-data descriptor, so an instance attribute shadows it by the
    normal attribute lookup rules. Wherever the instance has a __dict__,
    assigning works, as does deleting to fall back to the setting, as does
    mock.patch.object on an instance.

    Do not give this class __set__. That would make it a data descriptor, which
    takes precedence over the instance __dict__ and so has to reimplement
    assignment by hand. Without a matching __delete__, del and
    mock.patch.object's teardown both raise AttributeError.

    Two shapes this does not support, both because a non-data descriptor is
    shadowed by anything already in the instance __dict__:

        - a dataclass field, which takes the descriptor object itself as the
          field default and writes it to every instance, so the setting is
          never read and nothing raises to say so
        - instances with no __dict__ at all, which takes the class and every
          base between it and object defining __slots__ without including
          "__dict__"; there assignment raises AttributeError

    An unconfigured setting raises ImproperlyConfigured rather than
    AttributeError, so it can't be mistaken for a missing attribute. That is
    deliberate, and it means the error escapes callers that swallow
    AttributeError specifically - a Django template rendering {{ obj.attr }}
    and DRF's Field.get_attribute both raise through instead of falling back.

    Usage:
        class SheetConfig:
            first_row = SettingsRef("MITOL_GOOGLE_SHEETS_FIRST_ROW")
    """

    def __init__(self, setting_name: str):
        """
        Refer to a Django setting by name

        Args:
            setting_name (str): the name of the setting to read
        """
        self.setting_name = setting_name

    def __repr__(self):
        """
        Name the setting this refers to

        Returns:
            str: a representation including the setting name
        """
        return f"{type(self).__name__}({self.setting_name!r})"

    def __get__(self, instance, owner=None) -> Any:
        """
        Read the setting, unless the instance has a value of its own

        Args:
            instance (object): the instance being read from, None on class access
            owner (type): the class the attribute was looked up on

        Returns:
            Any: the setting's value, which is whatever type the setting
                holds, or this descriptor on class access

        Raises:
            ImproperlyConfigured:
                If the setting is not configured
        """
        if instance is None:
            return self

        try:
            return getattr(settings, self.setting_name)
        except AttributeError as exc:
            # Letting the AttributeError out would be indistinguishable from
            # this attribute not existing, so hasattr() would report False and
            # getattr(obj, name, default) would quietly hand back the default.
            raise ImproperlyConfigured(  # noqa: TRY003
                f"{type(self).__name__} refers to {self.setting_name}, which is not a configured setting"  # noqa: EM102, E501
            ) from exc

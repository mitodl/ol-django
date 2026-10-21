from django.conf import settings


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
    normal attribute lookup rules. Assigning works, as does deleting to fall
    back to the setting, as does mock.patch.object on an instance.

    Do not give this class __set__ or __set_name__. That would make it a data
    descriptor, which takes precedence over the instance __dict__ and so has to
    reimplement assignment by hand. Without a matching __delete__, del and
    mock.patch.object's teardown both raise AttributeError.

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

    def __get__(self, instance, owner=None):
        """
        Read the setting, unless the instance has a value of its own

        Args:
            instance (object): the instance being read from, None on class access
            owner (type): the class the attribute was looked up on

        Returns:
            object: the setting's value, or this descriptor on class access
        """
        if instance is None:
            return self
        return getattr(settings, self.setting_name)

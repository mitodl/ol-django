"""Config utils tests"""

from unittest import mock

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings
from mitol.common.utils.config import SettingsRef, get_missing_settings

SETTING = "MITOL_COMMON_TEST_SETTING"


class Configurable:
    """Stand-in for a class that configures itself from a setting"""

    value = SettingsRef(SETTING)


# Built at import time, like the sheet config singletons this class is for.
MODULE_LEVEL = Configurable()


@pytest.fixture
def configured(settings):
    """Set the test setting and return an instance reading it"""
    setattr(settings, SETTING, "from_settings")
    return Configurable()


def test_get_missing_settings(settings):
    """Only settings that are absent or None are reported missing"""
    setattr(settings, SETTING, "set")

    assert get_missing_settings([SETTING]) == []
    assert get_missing_settings([SETTING, "MITOL_COMMON_ABSENT"]) == [
        "MITOL_COMMON_ABSENT"
    ]


def test_reads_the_setting(configured):
    """The attribute resolves to the setting's value"""
    assert configured.value == "from_settings"


def test_follows_a_later_change(settings, configured):
    """An instance that already exists sees a setting changed afterwards"""
    setattr(settings, SETTING, "changed")

    assert configured.value == "changed"


def test_class_access_returns_the_descriptor():
    """Accessing it on the class gives the descriptor, not a setting lookup"""
    assert isinstance(Configurable.value, SettingsRef)
    assert repr(Configurable.value) == f"SettingsRef('{SETTING}')"


def test_instance_assignment_shadows_the_setting(configured):
    """Assigning on an instance overrides the setting for that instance only"""
    other = Configurable()

    configured.value = "assigned"

    assert configured.value == "assigned"
    assert other.value == "from_settings"


def test_assignment_survives_a_setting_change(settings, configured):
    """An assigned value isn't clobbered when the setting moves"""
    configured.value = "assigned"

    setattr(settings, SETTING, "changed")

    assert configured.value == "assigned"


def test_delete_falls_back_to_the_setting(configured):
    """Deleting an assigned value restores the setting-backed one"""
    configured.value = "assigned"

    del configured.value

    assert configured.value == "from_settings"
    assert "value" not in vars(configured)


def test_patch_object_roundtrips(configured):
    """
    mock.patch.object on an instance restores the setting-backed value

    This is what a data descriptor would break: patch.object sees the name is
    absent from the instance __dict__, so its teardown calls delattr, which a
    __set__ without a __delete__ refuses.
    """
    with mock.patch.object(configured, "value", "patched"):
        assert configured.value == "patched"

    assert configured.value == "from_settings"
    assert "value" not in vars(configured)


def test_delete_without_an_assignment_raises(configured):
    """Deleting a value the instance never had raises, as a plain attribute does"""
    with pytest.raises(AttributeError):
        del configured.value


def test_unconfigured_setting_raises(settings):
    """A setting that isn't configured fails loudly rather than reading as absent"""
    delattr(settings, SETTING)
    instance = Configurable()

    with pytest.raises(ImproperlyConfigured, match=SETTING):
        _ = instance.value

    # The error has to be something other than AttributeError, or these two
    # would silently report the attribute as missing instead of propagating.
    with pytest.raises(ImproperlyConfigured):
        hasattr(instance, "value")

    with pytest.raises(ImproperlyConfigured):
        getattr(instance, "value", "default")


def test_override_settings_reaches_a_module_level_instance():
    """
    override_settings reaches an instance built at import time

    This is the case the class exists for, and the one a setting read in
    __init__ or into a class attribute can never satisfy.
    """
    with override_settings(**{SETTING: "overridden"}):
        assert MODULE_LEVEL.value == "overridden"

    with pytest.raises(ImproperlyConfigured):
        _ = MODULE_LEVEL.value


def test_subclass_can_override_with_a_plain_attribute():
    """A subclass setting a plain class attribute shadows the descriptor"""

    class Fixed(Configurable):
        """Subclass that pins the value rather than reading a setting"""

        value = "fixed"

    assert Fixed().value == "fixed"

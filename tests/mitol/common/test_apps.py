"""Tests for apps"""
import pytest
import testapp
from django.core.exceptions import ImproperlyConfigured

from mitol.common.apps import BaseApp


def test_base_app_no_required_settings():
    """Verifies expected behavior of BaseApp when no settings are required"""

    class NoRequiredSettingsApp(BaseApp):
        """Test app that requires no settings"""

    # no error is raised
    app = NoRequiredSettingsApp("test", testapp)
    app.ready()


def test_base_app_required_settings(settings):
    """Verifies expected behavior of BaseApp when settings are required and present"""

    class RequiredSettingsApp(BaseApp):
        """Test app that requires settings"""

        required_settings = ["TEST_SETTING"]

    settings.TEST_SETTING = True

    # no error is raised
    app = RequiredSettingsApp("test", testapp)
    app.ready()


def test_base_app_required_settings_missing(settings):
    """Verifies expected behavior of BaseApp when settings are required and missing"""

    class RequiredSettingsApp(BaseApp):
        """Test app that requires settings"""

        required_settings = ["TEST_SETTING", "TEST_SETTING2"]

    settings.TEST_SETTING = True

    app = RequiredSettingsApp("test", testapp)
    with pytest.raises(ImproperlyConfigured):
        app.ready()

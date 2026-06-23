"""Tests for apps"""

import main
import pytest
from django.core.exceptions import ImproperlyConfigured
from mitol.common.apps import BaseApp


def test_base_app_no_required_settings():
    """Verifies expected behavior of BaseApp when no settings are required"""

    class NoRequiredSettingsApp(BaseApp):
        """Test app that requires no settings"""

    # no error is raised
    app = NoRequiredSettingsApp("test", main)
    app.ready()


def test_base_app_required_settings(settings):
    """Verifies expected behavior of BaseApp when settings are required and present"""

    class RequiredSettingsApp(BaseApp):
        """Test app that requires settings"""

        required_settings = ["TEST_SETTING"]

    settings.TEST_SETTING = True

    # no error is raised
    app = RequiredSettingsApp("test", main)
    app.ready()


def test_base_app_required_settings_missing(settings):
    """Verifies expected behavior of BaseApp when settings are required and missing"""

    class RequiredSettingsApp(BaseApp):
        """Test app that requires settings"""

        required_settings = ["TEST_SETTING", "TEST_SETTING2"]

    settings.TEST_SETTING = True

    app = RequiredSettingsApp("test", main)
    with pytest.raises(ImproperlyConfigured):
        app.ready()


def test_load_drf_schema_without_drf_spectacular(mocker):
    """load_drf_schema does nothing when drf_spectacular is not installed"""

    class TestApp(BaseApp):
        name = "myapp"

    app = TestApp("myapp", main)
    mocker.patch("mitol.common.apps.drf_spectacular", None)
    mock_import = mocker.patch("mitol.common.apps.import_string")
    app.load_drf_schema()
    mock_import.assert_not_called()


def test_load_drf_schema_with_schema_module(mocker):
    """
    load_drf_schema imports <app>.schema when drf_spectacular is
    installed and the module exists
    """

    class TestApp(BaseApp):
        name = "myapp"

    app = TestApp("myapp", main)
    mocker.patch("mitol.common.apps.drf_spectacular", mocker.MagicMock())
    mock_import = mocker.patch("mitol.common.apps.import_string")
    app.load_drf_schema()
    mock_import.assert_called_once_with("myapp.schema")


def test_load_drf_schema_missing_schema_module(mocker):
    """load_drf_schema silently ignores ImportError when the app has no schema module"""

    class TestApp(BaseApp):
        name = "myapp"

    app = TestApp("myapp", main)
    mocker.patch("mitol.common.apps.drf_spectacular", mocker.MagicMock())
    mocker.patch("mitol.common.apps.import_string", side_effect=ImportError)
    app.load_drf_schema()  # should not raise

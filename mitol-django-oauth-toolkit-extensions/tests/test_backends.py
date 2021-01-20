"""Backends tests"""
import pytest
from oauth2_provider.settings import oauth2_settings

from mitol.oauth_toolkit_extensions.backends import ApplicationAccessOrSettingsScopes


@pytest.mark.parametrize(
    "application_exists, is_configured", [(True, False), (True, True), (False, False),]
)
def test_application_access_settings(mocker, application_exists, is_configured):
    """Verify get_available_scopes() uses ApplicationAccess or defaults to settings"""
    application = mocker.Mock() if application_exists else None
    if application is not None and not is_configured:
        application.access = None

    scopes = ApplicationAccessOrSettingsScopes()

    if is_configured:
        assert (
            scopes.get_available_scopes(application=application)
            == application.access.scopes_list
        )
        assert (
            scopes.get_default_scopes(application=application)
            == application.access.scopes_list
        )
    else:
        assert sorted(scopes.get_available_scopes(application=application)) == sorted(
            oauth2_settings.SCOPES.keys()
        )
        assert sorted(scopes.get_default_scopes(application=application)) == sorted(
            oauth2_settings.DEFAULT_SCOPES
        )

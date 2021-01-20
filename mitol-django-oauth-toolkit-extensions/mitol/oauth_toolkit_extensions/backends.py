"""OAuth toolkit backends"""
from django.http import HttpRequest
from oauth2_provider.models import AbstractApplication
from oauth2_provider.scopes import SettingsScopes


class ApplicationAccessOrSettingsScopes(SettingsScopes):
    """Scopes backend that uses ApplicationAccess or defaults to SettingsScopes if not present"""

    def get_available_scopes(
        self,
        application: AbstractApplication = None,
        request: HttpRequest = None,
        *args,
        **kwargs
    ):
        """Return a list of scopes available for the current application/request"""
        if application is not None and getattr(application, "access", None) is not None:
            return application.access.scopes_list
        return super().get_available_scopes(
            application=application, request=request, *args, **kwargs
        )

    def get_default_scopes(
        self,
        application: AbstractApplication = None,
        request: HttpRequest = None,
        *args,
        **kwargs
    ):
        if application is not None and getattr(application, "access", None) is not None:
            return application.access.scopes_list
        return super().get_default_scopes(
            application=application, request=request, *args, **kwargs
        )

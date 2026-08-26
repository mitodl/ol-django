"""Login/logout views for the API Gateway."""

from django.conf import settings
from django.http.request import HttpRequest
from mitol.apigateway.utils import has_gateway_auth
from mitol.authentication.views.auth import LoginRedirectView, LogoutRedirectView


class ApiGatewayLogoutView(LogoutRedirectView):
    """
    Log the user out.

    Logs the user out of the Django app itself. If there is also an APISIX session,
    send them through APISIX's logout process too (which will destroy the APISIX
    session and log them out in SSO/Keycloak). If there's a redirect URL set
    (in cookies or in the query), send the user there; otherwise, use the default
    logout URL.

    If we just send the user through the APISIX logout, they'll get an error
    message if they don't have an APISIX session. (They'll still get sent to
    Keycloak to log out, but they won't have all the necessary data to that, and
    Keycloak will throw an error.)
    """

    def get_next_url_cookie_names(self) -> list[str]:
        """Get the cookie names to check for the redirect URL"""
        return [settings.MITOL_APIGATEWAY_LOGOUT_NEXT_URL_COOKIE_NAME]

    def get_redirect_url(self, request: HttpRequest) -> tuple[str, bool]:
        """Get the redirect url"""
        if has_gateway_auth(request):
            # Still logged in via Apisix/Keycloak, so log out there
            # and use cookies to preserve the next url
            return settings.MITOL_APIGATEWAY_LOGOUT_URL, False
        else:
            return super().get_redirect_url(request)

    def get(
        self,
        request,
        *args,
        **kwargs,
    ):
        """
        GET endpoint reached to logout the user
        """
        response = super().get(request, *args, **kwargs)

        if has_gateway_auth(request):
            # we can only preserve the next url via cookies because APISIX
            # won't accept a post_logout_redirect_url
            next_url, _ = super().get_redirect_url(request)

            response.set_cookie(
                settings.MITOL_APIGATEWAY_LOGOUT_NEXT_URL_COOKIE_NAME,
                value=next_url,
                max_age=settings.MITOL_APIGATEWAY_LOGOUT_NEXT_URL_COOKIE_TTL,
                secure=request.is_secure(),
                samesite="Lax",
                path="/",
            )

        return response


class ApiGatewayLoginView(LoginRedirectView):
    """
    Redirect the user after an API gateway login.

    Reads the next URL from the login cookie the middleware writes, since the
    gateway drops the query string on the login bounce. Subclass and override
    the LoginRedirectView hooks (is_first_login, handle_first_login, etc) for
    onboarding behavior.
    """

    def get_next_url_cookie_names(self) -> list[str]:
        """Get the cookie names to check for the redirect URL"""
        return [settings.MITOL_APIGATEWAY_LOGIN_NEXT_URL_COOKIE_NAME]

"""Custom logout view for the API Gateway."""

import logging

from django.conf import settings
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View

log = logging.getLogger(__name__)


def get_redirect_url(request):
    """
    Get the redirect URL from the request.

    Args:
        request: Django request object

    Returns:
        str: Redirect URL
    """
    log.debug("views.get_redirect_url: Request GET is: %s", request.GET.get("next"))
    log.debug(
        "views.get_redirect_url: Request cookie is: %s", request.COOKIES.get("next")
    )

    next_url = request.GET.get("next") or request.COOKIES.get("next")
    log.debug("views.get_redirect_url: Redirect URL (before valid check): %s", next_url)

    if request.COOKIES.get("next"):
        # Clear the cookie after using it
        log.debug("views.get_redirect_url: Popping the next cookie")

        request.COOKIES.pop("next", None)

    return (
        next_url
        if next_url
        and url_has_allowed_host_and_scheme(
            next_url, allowed_hosts=settings.MITOL_APIGATEWAY_ALLOWED_REDIRECT_HOSTS
        )
        else settings.MITOL_APIGATEWAY_DEFAULT_POST_LOGOUT_DEST
    )


class ApiGatewayLogoutView(View):
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

    def get(
        self,
        request,
        *args,  # noqa: ARG002
        **kwargs,  # noqa: ARG002
    ):
        """
        GET endpoint reached after logging a user out from Keycloak
        """
        user = getattr(request, "user", None)
        user_redirect_url = get_redirect_url(request)
        log.debug(
            "views.ApiGatewayLogoutView.get: User redirect URL: %s", user_redirect_url
        )
        if user and user.is_authenticated:
            logout(request)

        if request.META.get(settings.MITOL_APIGATEWAY_USERINFO_HEADER_NAME):
            # Still logged in via Apisix/Keycloak, so log out there as well
            log.debug("views.ApiGatewayLogoutView.get: Send to APISIX logout URL")
            return redirect(settings.MITOL_APIGATEWAY_LOGOUT_URL)
        else:
            log.debug("views.ApiGatewayLogoutView.get: Send to %s", user_redirect_url)
            return redirect(user_redirect_url)

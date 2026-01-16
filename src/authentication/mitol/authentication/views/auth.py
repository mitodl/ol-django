"""Authentication views"""

import logging

from django.contrib.auth import logout
from django.http.request import HttpRequest
from django.shortcuts import redirect
from django.views import View
from mitol.authentication.utils import get_redirect_url

log = logging.getLogger(__name__)


class AuthRedirectView(View):
    """Base class for auth views that need to do a redirect based on params/cookies"""

    next_url_param_names = ["next"]
    next_url_cookie_names = []

    def get_redirect_url(self, request: HttpRequest) -> tuple[str, bool]:
        """Get the redirect url based on params or cookies"""
        return get_redirect_url(
            request,
            param_names=self.next_url_param_names,
            cookie_names=self.next_url_cookie_names,
        ), True

    def prune_next_url_cookies(self, request: HttpRequest):
        """Prune the next url cookies"""
        for cookie_name in self.next_url_cookie_names:
            request.COOKIES.pop(cookie_name, None)

    def get(
        self,
        request,
        *_args,
        **_kwargs,
    ):
        """
        GET endpoint reached after logging a user out from Keycloak
        """
        redirect_url, prune_cookies = self.get_redirect_url(request)

        if prune_cookies:
            self.prune_next_url_cookies(request)

        return redirect(redirect_url)


class LogoutRedirectView(AuthRedirectView):
    """
    Log out the user from django and redirect
    """

    def get(
        self,
        request,
        *args,
        **kwargs,
    ):
        """
        GET endpoint reached to logout the user
        """
        user = getattr(request, "user", None)

        if user and user.is_authenticated:
            logout(request)

        return super().get(request, *args, **kwargs)

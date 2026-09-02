"""Authentication views"""

import logging
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import logout
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.views import View
from mitol.authentication.utils import get_redirect_url

log = logging.getLogger(__name__)


class AuthRedirectView(View):
    """Base class for auth views that need to do a redirect based on params/cookies"""

    next_url_param_names = ["next"]
    next_url_cookie_names = []
    default_redirect_url = None

    def get_next_url_param_names(self) -> list[str]:
        """Get the GET param names to check for the redirect URL"""
        return self.next_url_param_names

    def get_next_url_cookie_names(self) -> list[str]:
        """Get the cookie names to check for the redirect URL"""
        return self.next_url_cookie_names

    def get_default_redirect_url(self) -> str | None:
        """Get the fallback redirect URL"""
        return self.default_redirect_url

    def get_redirect_url(self, request: HttpRequest) -> tuple[str, bool]:
        """Get the redirect url based on params or cookies"""
        return get_redirect_url(
            request,
            param_names=self.get_next_url_param_names(),
            cookie_names=self.get_next_url_cookie_names(),
            default=self.get_default_redirect_url(),
        ), True

    def prune_next_url_cookies(self, request: HttpRequest, response: HttpResponse):
        """Delete the next url cookies from the response"""
        for cookie_name in self.get_next_url_cookie_names():
            if cookie_name in request.COOKIES:
                request.COOKIES.pop(cookie_name, None)
                response.delete_cookie(cookie_name)

    def get(
        self,
        request,
        *_args,
        **_kwargs,
    ):
        """
        Redirect the user based on the request params/cookies
        """
        redirect_url, prune_cookies = self.get_redirect_url(request)

        response = redirect(redirect_url)

        if prune_cookies:
            self.prune_next_url_cookies(request, response)

        return response


class LoginRedirectView(AuthRedirectView):
    """
    Redirect the user after login, optionally routing first-time logins
    through an onboarding flow.

    Subclasses hook into the onboarding behavior by overriding:

    - is_first_login: whether this user needs first-login handling
      (defaults to False, which makes this a plain redirect view)
    - should_skip_onboarding: whether to bypass the onboarding redirect
    - get_onboarding_url: where the onboarding flow lives
    - handle_first_login: side effects to run once on first login
      (set flags, send welcome emails, etc)
    """

    signup_next_url_param_names = ["signup_next", "next"]
    skip_onboarding_param = "skip_onboarding"

    def is_first_login(self, request: HttpRequest) -> bool:  # noqa: ARG002
        """Return True if this is the user's first login"""
        return False

    def should_skip_onboarding(self, request: HttpRequest) -> bool:
        """Return True if the onboarding redirect should be skipped"""
        return request.GET.get(self.skip_onboarding_param, "0") != "0"

    def get_onboarding_url(self, request: HttpRequest) -> str | None:  # noqa: ARG002
        """Get the URL for the onboarding flow, or None if disabled"""
        return settings.MITOL_NEW_USER_LOGIN_URL or None

    def get_signup_redirect_url(self, request: HttpRequest) -> str:
        """Get the redirect URL to use after the onboarding flow"""
        return get_redirect_url(
            request,
            param_names=self.signup_next_url_param_names,
            cookie_names=self.get_next_url_cookie_names(),
            default=self.get_default_redirect_url(),
        )

    def handle_first_login(self, request: HttpRequest) -> None:
        """Run side effects for a first login"""

    def get(
        self,
        request,
        *_args,
        **_kwargs,
    ):
        """
        Redirect the user after login
        """
        redirect_url, prune_cookies = self.get_redirect_url(request)

        if request.user.is_authenticated and self.is_first_login(request):
            signup_next_url = self.get_signup_redirect_url(request)
            onboarding_url = self.get_onboarding_url(request)

            if onboarding_url and not self.should_skip_onboarding(request):
                params = urlencode({"next": signup_next_url})
                redirect_url = f"{onboarding_url}?{params}"
            else:
                redirect_url = signup_next_url

            self.handle_first_login(request)

        response = redirect(redirect_url)

        if prune_cookies:
            self.prune_next_url_cookies(request, response)

        return response


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

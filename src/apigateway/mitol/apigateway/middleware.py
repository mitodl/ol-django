"""
Middleware to fetch the user out of the headers.
Middleware for channels is in middleware_channels.py.
"""

import logging

from asgiref.sync import iscoroutinefunction, sync_to_async
from django.conf import settings
from django.contrib import auth
from django.contrib.auth.middleware import (
    PersistentRemoteUserMiddleware,
    RemoteUserMiddleware,
)
from mitol.apigateway.api import get_user_id_from_userinfo_header

log = logging.getLogger(__name__)


class ApisixUserMiddleware(RemoteUserMiddleware):
    """Checks for and processes APISIX-specific headers."""

    def __call__(self, request):
        """Run auth processing and set post-logout redirect cookie on response."""
        if settings.MITOL_APIGATEWAY_DISABLE_MIDDLEWARE:
            return self.get_response(request)

        if iscoroutinefunction(self.get_response):
            return self._acall(request)

        response = super().__call__(request)
        return self._set_next_cookie(request, response)

    async def _acall(self, request):
        """Async version of __call__()."""
        response = await super().__acall__(request)
        return self._set_next_cookie(request, response)

    def _set_next_cookie(self, request, response):
        """Copy the next query parameter into a short-lived cookie."""
        next_param = request.GET.get("next") if request.GET else None
        if next_param:
            log.debug(
                "ApisixUserMiddleware.__call__: Setting next cookie to %s",
                next_param,
            )
            response.set_cookie("next", next_param, max_age=30, secure=False)

        log.debug(
            "ApisixUserMiddleware.__call__: Next cookie is %s",
            response.cookies.get("next"),
        )

        return response

    def process_request(self, request):
        """
        Modify the header to contain username, pass off to RemoteUserMiddleware.

        RemoteUserMiddleware only recognizes the session user as the header
        user by comparing on USERNAME_FIELD, while REMOTE_USER holds the value
        of MITOL_APIGATEWAY_USER_LOOKUP_FIELD. Where the two fields differ it
        logs the session out and back in on every request, which flushes the
        session, rotates the session key and CSRF token, and rewrites
        last_login. So when the session user already matches on the lookup
        field, the session is kept. With MITOL_APIGATEWAY_USERINFO_UPDATE on,
        the user is still passed through authenticate() so the backend can
        apply userinfo updates.
        """

        log.debug("ApisixUserMiddleware.process_request: started")

        if settings.MITOL_APIGATEWAY_DISABLE_MIDDLEWARE:
            return

        if request.META.get(settings.MITOL_APIGATEWAY_USERINFO_HEADER_NAME):
            user_id = get_user_id_from_userinfo_header(request)
            request.META["REMOTE_USER"] = user_id

            lookup_field = settings.MITOL_APIGATEWAY_USER_LOOKUP_FIELD
            if (
                user_id
                and request.user.is_authenticated
                and getattr(request.user, lookup_field, None) == user_id
            ):
                if not settings.MITOL_APIGATEWAY_USERINFO_UPDATE:
                    return

                user = auth.authenticate(request, remote_user=user_id)
                if user is not None and user.pk == request.user.pk:
                    request.user = user
                    return
                # The header no longer resolves to the session user (e.g. it
                # was deactivated), so fall through and let
                # RemoteUserMiddleware log the session out.

        super().process_request(request)

    async def aprocess_request(self, request):
        """
        See process_request().

        RemoteUserMiddleware stops calling an overridden process_request()
        from its async path in Django 6.1, so this delegates to it explicitly.
        """
        await sync_to_async(self.process_request, thread_sensitive=True)(request)


class PersistentApisixUserMiddleware(
    PersistentRemoteUserMiddleware, ApisixUserMiddleware
):
    """Persistent version of the ApisixUserMiddleware."""

"""
Middleware to fetch the user out of the headers.
Middleware for channels is in middleware_channels.py.
"""

import logging

from asgiref.sync import sync_to_async
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
        """Run auth processing and set the login next-URL cookie on response."""
        if settings.MITOL_APIGATEWAY_DISABLE_MIDDLEWARE:
            return self.get_response(request)

        response = super().__call__(request)

        next_param = request.GET.get("next") if request.GET else None
        if settings.MITOL_APIGATEWAY_SET_NEXT_COOKIE and next_param:
            # preserve the next URL across the gateway's OIDC login redirect,
            # which drops the query string
            log.debug(
                "ApisixUserMiddleware.__call__: Setting next cookie to %s",
                next_param,
            )
            response.set_cookie(
                settings.MITOL_APIGATEWAY_LOGIN_NEXT_URL_COOKIE_NAME,
                next_param,
                max_age=settings.MITOL_APIGATEWAY_LOGIN_NEXT_URL_COOKIE_TTL,
                secure=request.is_secure(),
            )

        return response

    def process_request(self, request):
        """
        Modify the header to contain username, pass off to RemoteUserMiddleware.

        If the session already belongs to the user in the gateway header, skip
        the stock logout/login cycle: sync the user (dirty-checked) when
        updates are enabled, and otherwise do nothing - so unchanged requests
        don't rotate the session or rewrite last_login.
        """

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
                # resolution changed (deactivated, ambiguous, ...) - let the
                # stock path re-resolve and log out as needed

        super().process_request(request)

    async def aprocess_request(self, request):
        """See process_request()."""
        return await sync_to_async(self.process_request, thread_sensitive=True)(request)


class PersistentApisixUserMiddleware(
    PersistentRemoteUserMiddleware, ApisixUserMiddleware
):
    """Persistent version of the ApisixUserMiddleware."""

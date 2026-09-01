"""
Middleware to fetch the user out of the headers.
Middleware for channels is in middleware_channels.py.
"""

import logging

from django.conf import settings
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

        response = super().__call__(request)

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
        """

        log.debug("ApisixUserMiddleware.process_request: started")

        if settings.MITOL_APIGATEWAY_DISABLE_MIDDLEWARE:
            return

        if request.META.get(settings.MITOL_APIGATEWAY_USERINFO_HEADER_NAME):
            new_header = get_user_id_from_userinfo_header(request)
            request.META["REMOTE_USER"] = new_header

            # RemoteUserMiddleware decides "same user, nothing to do" by
            # comparing REMOTE_USER against USERNAME_FIELD. REMOTE_USER holds
            # the gateway lookup field, so in an app where the two differ that
            # comparison never matches: every request re-authenticates, and the
            # mismatch branch logs the session out first. Compare on the field
            # REMOTE_USER actually holds.
            lookup_field = settings.MITOL_APIGATEWAY_USER_LOOKUP_FIELD
            if (
                new_header
                and request.user.is_authenticated
                and getattr(request.user, lookup_field, None) == new_header
            ):
                log.debug(
                    "ApisixUserMiddleware.process_request: %s already matches %s",
                    lookup_field,
                    new_header,
                )
                return

        super().process_request(request)


class PersistentApisixUserMiddleware(
    PersistentRemoteUserMiddleware, ApisixUserMiddleware
):
    """Persistent version of the ApisixUserMiddleware."""

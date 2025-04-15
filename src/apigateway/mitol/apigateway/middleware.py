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

    def process_request(self, request):
        """
        Modify the header to contaiin username, pass off to RemoteUserMiddleware
        """

        log.debug("ApisixUserMiddleware.process_request: started")

        if settings.MITOL_APIGATEWAY_DISABLE_MIDDLEWARE:
            return self.get_response(request)

        if request.META.get(settings.MITOL_APIGATEWAY_USERINFO_HEADER_NAME):
            new_header = get_user_id_from_userinfo_header(request)
            request.META["REMOTE_USER"] = new_header

        super().process_request(request)

        response = self.get_response(request)

        next_param = request.GET.get("next", None) if request.GET else None
        if next_param:
            log.debug(
                "ApisixUserMiddleware.process_request: Setting next cookie to %s",
                next_param,
            )
            response.set_cookie("next", next_param, max_age=30, secure=False)

        log.debug(
            "ApisixUserMiddleware.process_request: Next cookie is %s",
            response.cookies.get("next"),
        )

        return response


class PersistentApisixUserMiddleware(
    PersistentRemoteUserMiddleware, ApisixUserMiddleware
):
    """Persistent version of the ApisixUserMiddleware."""

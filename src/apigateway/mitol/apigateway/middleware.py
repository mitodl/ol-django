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
        if request.META.get(settings.MITOL_APIGATEWAY_USERINFO_HEADER_NAME):
            new_header = get_user_id_from_userinfo_header(request)
            request.META["REMOTE_USER"] = new_header

        return super().process_request(request)


class PersistentApisixUserMiddleware(
    PersistentRemoteUserMiddleware, ApisixUserMiddleware
):
    """Persistent version of the ApisixUserMiddleware."""

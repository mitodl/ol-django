"""
Middleware for Django Channels.

The RemoteUserMiddleware doesn't put the user information into the session, so
the AuthMiddleware that ships with Channels doesn't work. So, this middleware
(and related functions) work more like the RemoteUserMiddleware - we attach the
user to the scope but it's not in the session. There is no real need to login.

Important consideration for websocket consumers: the headers get attached when
the connection is made. This means that user change events don't propogate into
_running_ consumers. You will need to check and perform appropriate actions when
the user changes through some other means, or your websocket users will continue
to be logged in even if they've logged out elsewhere.
"""

import logging

from channels.auth import AuthMiddleware
from channels.db import database_sync_to_async
from channels.sessions import CookieMiddleware, SessionMiddleware

from mitol.apigateway.api import get_user_id_from_userinfo_header
from mitol.apigateway.backends import ApisixRemoteUserBackend

log = logging.getLogger(__name__)


@database_sync_to_async
def get_apisix_user(scope):
    """
    Get the user using the ApisixRemoteUserBackend.
    """

    user_id = get_user_id_from_userinfo_header(scope)

    log.debug("Got user ID %s", user_id)

    if user_id:
        backend = ApisixRemoteUserBackend()
        return backend.authenticate(request=scope, remote_user=user_id)

    from django.contrib.auth.models import AnonymousUser  # noqa: PLC0415

    return AnonymousUser()


class ApisixUserMiddleware(AuthMiddleware):
    """Retrieve the current user based on the APISIX headers provided."""

    async def resolve_scope(self, scope):
        """Resolve the user from the scope."""

        scope["user"]._wrapped = await get_apisix_user(scope)  # noqa: SLF001


def ApisixAuthMiddlewareStack(inner):  # noqa: N802
    """Wrap the ApisixUserMiddleware in a couple of other useful middlewares."""

    return CookieMiddleware(SessionMiddleware(ApisixUserMiddleware(inner)))

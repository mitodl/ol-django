"""API functions."""

import base64
import json
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import HttpRequest

log = logging.getLogger(__name__)
User = get_user_model()


def decode_x_header(request: HttpRequest | dict) -> dict | None:
    """
    Decode an 'X-' header.

    API gateways put the user information in a header, typically X-Userinfo, as
    a base64 encoded JSON string. This function decodes and de-JSONs that string
    and returns the resulting dict.

    This will work for both HttpRequest and Channel scopes.

    Args:
        request (HttpRequest): the HTTP request
    Returns:
    dict of decoded values, or None if the header isn't found
    """

    if isinstance(request, HttpRequest):
        x_userinfo = request.META.get(
            settings.MITOL_APIGATEWAY_USERINFO_HEADER_NAME, False
        )
    else:
        # We've likely got a scope dict from Channels.
        # We need to do some processing - scopes don't append HTTP_, don't upper
        # the header name, and don't convert - to _. (Also these get stored as
        # bytes.)
        check_header = (
            settings.MITOL_APIGATEWAY_USERINFO_HEADER_NAME.lower()
            .replace("http_", "")
            .replace("_", "-")
        )
        scope_headers = request.get("headers", [])
        x_userinfo = [x[1] for x in scope_headers if x[0].decode() == check_header]

        if len(x_userinfo) == 0:
            log.warning("No %s header found", check_header)
            return None

        x_userinfo = x_userinfo.pop()

    if not x_userinfo:
        log.warning(
            "No %s header found", settings.MITOL_APIGATEWAY_USERINFO_HEADER_NAME
        )
        return None

    decoded_x_userinfo = base64.b64decode(x_userinfo)
    return json.loads(decoded_x_userinfo)


def get_user_id_from_userinfo_header(request: HttpRequest | dict) -> str | None:
    """Return the user ID from the userinfo header."""

    decoded_headers = decode_x_header(request)

    if not decoded_headers:
        return None

    return decoded_headers.get(settings.MITOL_APIGATEWAY_USERINFO_ID_FIELD, None)


def get_username_from_userinfo_header(request: HttpRequest | dict) -> str | None:
    """Return the username from the userinfo header."""

    user_id = get_user_id_from_userinfo_header(request)

    if not user_id:
        return None

    return User.objects.get(global_id=user_id).username

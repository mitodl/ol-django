"""Authentication utils"""

import logging

from django.conf import settings
from django.http.request import HttpRequest
from django.utils.http import url_has_allowed_host_and_scheme

log = logging.getLogger(__name__)


def get_redirect_url(
    request: HttpRequest,
    *,
    param_names: list[str] | None = None,
    cookie_names: list[str] | None = None,
    default: str | None = None,
) -> str:
    """
    Get the redirect URL from the request.

    Args:
        request: Django request object
        param_names: Names of the GET parameters to look for the redirect URL;
            first match will be used.
        cookie_names: Names of the cookies to look for the redirect URL;
            first match will be used.
        default: Fallback URL if no valid redirect URL is found; defaults to
            settings.MITOL_DEFAULT_POST_LOGOUT_URL.

    Returns:
        str: Redirect URL
    """
    next_url = get_redirect_url_from_params(
        request, param_names
    ) or get_redirect_url_from_cookies(request, cookie_names)

    log.debug("get_redirect_url: next_url='%s'", next_url)

    return next_url or default or settings.MITOL_DEFAULT_POST_LOGOUT_URL or "/"


def get_redirect_url_from_cookies(
    request: HttpRequest, cookie_names: list[str] | None
) -> str | None:
    """
    Get the redirect URL from the request cookies.

    Args:
        request: Django request object
        cookie_names: Names of the cookies to look for the redirect URL;
            first match will be used.

    Returns:
        str: Redirect URL
    """
    return _get_redirect_url(request.COOKIES, cookie_names)


def get_redirect_url_from_params(
    request: HttpRequest, param_names: list[str] | None
) -> str | None:
    """
    Get the redirect URL from the request params.

    Args:
        request: Django request object
        param_names: Names of the GET parameter to look for the redirect URL;
            first match will be used.

    Returns:
        str: Redirect URL
    """

    return _get_redirect_url(request.GET, param_names)


def _get_redirect_url(record: dict[str, str], keys: list[str] | None) -> str | None:
    """
    Get a valid redirect
    """
    for key in keys or []:
        next_url = record.get(key)
        if next_url and url_has_allowed_host_and_scheme(
            next_url, allowed_hosts=settings.MITOL_ALLOWED_REDIRECT_HOSTS
        ):
            return next_url

    return None

"""URL utilities"""

from typing import Union, List, Tuple
from urllib.parse import ParseResult, urlparse, urlunparse

from django.conf import settings
from django.urls import include, path
from django.urls.conf import URLResolver, URLPattern

def ensure_trailing_slash(url: str) -> str:
    """Ensure a url has a trailing slash"""
    return url if url.endswith("/") else url + "/"


def remove_password_from_url(url: str) -> str:
    """
    Remove a password from a URL

    Args:
        url (str): A URL

    Returns:
        str: A URL without a password
    """
    pieces = urlparse(url)
    netloc = pieces.netloc
    userinfo, delimiter, hostinfo = netloc.rpartition("@")
    if delimiter:
        username, _, _ = userinfo.partition(":")
        rejoined_netloc = f"{username}{delimiter}{hostinfo}"
    else:
        rejoined_netloc = netloc

    return urlunparse(
        ParseResult(
            scheme=pieces.scheme,
            netloc=rejoined_netloc,
            path=pieces.path,
            params=pieces.params,
            query=pieces.query,
            fragment=pieces.fragment,
        )
    )


def prefix_url_patterns(urlpatterns: list[URLPattern]) -> Union[Tuple[URLResolver], List[URLPattern]]:
    """Add a prefix to all current app urlpatterns"""
    if settings.MITOL_APP_PATH_PREFIX:
        return (path(f"{settings.MITOL_APP_PATH_PREFIX.rstrip('/')}/", include(urlpatterns)),)
    return urlpatterns

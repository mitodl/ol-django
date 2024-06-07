"""Webpack utilities"""
from django.conf import settings
from django.http import HttpRequest
from django.templatetags.static import static

from mitol.common.utils.urls import ensure_trailing_slash


def webpack_public_path(request: HttpRequest) -> str:
    """
    Return the correct public_path for Webpack to use
    """
    if settings.WEBPACK_USE_DEV_SERVER:
        return ensure_trailing_slash(webpack_dev_server_url(request))
    else:
        return ensure_trailing_slash(static("bundles/"))


def webpack_dev_server_host(request: HttpRequest) -> str:
    """
    Get the correct webpack dev server host
    """
    return settings.WEBPACK_DEV_SERVER_HOST or request.get_host().split(":")[0]


def webpack_dev_server_url(request: HttpRequest) -> str:
    """
    Get the full URL where the webpack dev server should be running
    """
    return "http://{}:{}".format(
        webpack_dev_server_host(request), settings.WEBPACK_DEV_SERVER_PORT
    )

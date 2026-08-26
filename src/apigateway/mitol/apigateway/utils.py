"""API gateway utils"""

from django.conf import settings
from django.http.request import HttpRequest


def has_gateway_auth(request: HttpRequest) -> bool:
    """Return True if the request has auth information from the API gateway"""
    return bool(request.META.get(settings.MITOL_APIGATEWAY_USERINFO_HEADER_NAME))

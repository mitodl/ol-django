"""Exceptions for hubspot_api"""

from hubspot.crm.objects import ApiException


class TooManyRequestsException(ApiException):
    """
    Exception to raise if Hubspot API returns a 429
    """

"""Tests for hubspot_api decorators"""

import pytest
from hubspot.crm.objects import ApiException
from mitol.hubspot_api.decorators import raise_429
from mitol.hubspot_api.exceptions import TooManyRequestsException


@raise_429
def dummy_function(status):
    """Dummy function for tests"""  # noqa: D401
    raise ApiException(status=status)


@pytest.mark.parametrize(
    "status,expected_error",  # noqa: PT006
    [[429, TooManyRequestsException], [500, ApiException]],  # noqa: PT007
)
def test_raise_429(status, expected_error):
    """ """  # noqa: D419
    with pytest.raises(expected_error):
        dummy_function(status)

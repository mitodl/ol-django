"""client tests"""

import pytest
from edx_api.client import EdxApi


def test_request_id_credential():
    """access_token required in credentials"""
    with pytest.raises(AttributeError) as exc:
        EdxApi({})

    assert "access token" in str(exc.value)


def test_instantiation_happypath():
    """Instantiatable with correct args"""
    token = "asdf"
    client = EdxApi({"access_token": token})
    assert client.get_requester().headers["Authorization"] == f"Bearer {token}"


def test_enrollments_v2_sends_jwt():
    """The v2 enrollment API only accepts a JWT"""
    token = "asdf"
    client = EdxApi({"access_token": token})
    assert client.enrollments_v2.requester.headers["Authorization"] == f"jwt {token}"

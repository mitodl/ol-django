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

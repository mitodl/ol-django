"""Requests utils tests"""
import base64
import hashlib

import pytest
from requests.models import PreparedRequest

from mitol.digitalcredentials.requests_utils import (
    prepare_request_digest,
    prepare_request_hmac_signature,
)


REQUEST_BODY = '{"content": 1}'
REQUEST_DIGEST = base64.b64encode(
    hashlib.sha512(REQUEST_BODY.encode("utf-8")).digest()
).decode("ascii")


@pytest.mark.parametrize(
    "body, expected",
    [[REQUEST_BODY, REQUEST_DIGEST], [REQUEST_BODY.encode("utf-8"), REQUEST_DIGEST],],
)
def test_prepare_request_digest(mocker, body, expected):
    """Verify prepare_request_digest works as expected"""
    mock_request = mocker.Mock(spec=PreparedRequest, body=body)
    mock_request.copy.return_value.headers = {}

    request = prepare_request_digest(mock_request)

    assert request == mock_request.copy.return_value
    assert request.headers["Digest"] == f"SHA512={expected}"


def test_prepare_request_digest_invalid_body(mocker):
    """Verify prepare_request_digest raises an exception if the body isn't a str oy btes"""
    mock_request = mocker.Mock(spec=PreparedRequest, body=None)

    with pytest.raises(ValueError):
        prepare_request_digest(mock_request)


def test_prepare_request_hmac_signature(mocker):
    """Verify prepare_request_hmac_signature works as expected"""
    mock_request = mocker.Mock(spec=PreparedRequest)
    copied_request = mock_request.copy.return_value
    copied_request.method = "POST"
    copied_request.url = "/my/url"
    copied_request.headers = {
        "Digest": "abc",
        "User-Agent": "digitalcredentials",
        "Date": "Date: Wed, 21 Oct 2015 07:28:00 GMT",
    }

    request = prepare_request_hmac_signature(mock_request, "secret")
    assert request == mock_request.copy.return_value
    assert request.headers["Signature"] == (
        'keyId="abc",algorithm="hmac-sha512",headers="(request-target) digest user-agent date",signature="vcHuErUmrcHbaVZ4Ob85XyFNX0fGshZlQh+qorXW497WBuV4inMQLfwWHqAugaXWccL1LvZfZdcH964nuzasmw=="'
    )


def test_prepare_request_hmac_signature_invalid_method(mocker):
    """Verify prepare_request_hmac_signature raises an error on an invalid method"""
    mock_request = mocker.Mock(spec=PreparedRequest)
    copied_request = mock_request.copy.return_value
    copied_request.method = None
    with pytest.raises(ValueError):
        prepare_request_hmac_signature(mock_request, "secret")

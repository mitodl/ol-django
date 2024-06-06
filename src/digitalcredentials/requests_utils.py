"""Digital credentials request utils"""
import base64
import hashlib
import hmac
from typing import List, NamedTuple
from urllib.parse import urlparse

from requests.models import PreparedRequest


def prepare_request_digest(request: PreparedRequest) -> PreparedRequest:
    """Prepare the request further by adding a SHA-512 digest header"""
    if isinstance(request.body, str):
        body = request.body.encode("utf-8")
    elif isinstance(request.body, bytes):
        body = request.body
    else:
        raise ValueError(f"Request body cannot be {type(request.body)}")
    request = request.copy()
    digest = hashlib.sha512(body).digest()
    encoded = base64.b64encode(digest).decode("ascii")
    request.headers["Digest"] = f"SHA512={encoded}"
    return request


class HttpSignatureData(NamedTuple):
    """HTTP signature and headers"""

    signature: str
    headers: List[str]


def _generate_signature_data(request: PreparedRequest) -> HttpSignatureData:
    """Generate an http signature"""
    if not isinstance(request.method, str):
        raise ValueError("Request.method must be a string")
    header_names: List[str] = []
    path = urlparse(request.url).path
    signing_string_lines = [
        f"(request-target): {request.method.lower()} {path if isinstance(path, str) else path.decode('utf-8')}"
    ]
    for name, value in request.headers.items():
        name = name.lower()
        signing_string_lines.append(f"{name}: {value}")
        header_names.append(name)

    return HttpSignatureData("\n".join(signing_string_lines), header_names)


def prepare_request_hmac_signature(
    request: PreparedRequest, secret: str
) -> PreparedRequest:
    """Prepare a request with an HMAC signature header"""
    request = request.copy()

    signature_data = _generate_signature_data(request)
    signature_hmac = hmac.new(
        secret.encode("utf-8"),
        signature_data.signature.encode("utf-8"),
        digestmod=hashlib.sha512,
    )
    signature = base64.b64encode(signature_hmac.digest()).decode("utf-8")
    signature_headers = " ".join(signature_data.headers)
    request.headers[
        "Signature"
    ] = f'keyId="abc",algorithm="hmac-sha512",headers="(request-target) {signature_headers}",signature="{signature}"'
    return request

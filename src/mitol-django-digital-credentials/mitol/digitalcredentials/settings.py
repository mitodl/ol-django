"""Boilerplate settings parsing"""
# pragma: no cover
from mitol.common.envs import get_string


MITOL_DIGITAL_CREDENTIALS_VERIFY_SERVICE_BASE_URL = get_string(
    name="MITOL_DIGITAL_CREDENTIALS_VERIFY_SERVICE_BASE_URL",
    description="Base URL for sing-and-verify service to call for digital credentials",
    required=True,
)
MITOL_DIGITAL_CREDENTIALS_HMAC_SECRET = get_string(
    name="MITOL_DIGITAL_CREDENTIALS_HMAC_SECRET",
    description="HMAC secret to sign digital credentials requests with",
    required=True,
)

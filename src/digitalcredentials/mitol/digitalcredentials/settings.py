"""Boilerplate settings parsing"""
# pragma: no cover
from mitol.common.envs import get_string

MITOL_DIGITAL_CREDENTIALS_VERIFY_SERVICE_BASE_URL = get_string(
    name="MITOL_DIGITAL_CREDENTIALS_VERIFY_SERVICE_BASE_URL",
    description="Base URL for sing-and-verify service to call for digital credentials",
    required=False,
)
MITOL_DIGITAL_CREDENTIALS_HMAC_SECRET = get_string(
    name="MITOL_DIGITAL_CREDENTIALS_HMAC_SECRET",
    description="HMAC secret to sign digital credentials requests with",
    required=False,
)
MITOL_DIGITAL_CREDENTIALS_DEEP_LINK_URL = get_string(
    name="MITOL_DIGITAL_CREDENTIALS_DEEP_LINK_URL",
    default=None,
    description="URL at which to deep link the learner to for the digital credentials wallet",
    required=False,
)
MITOL_DIGITAL_CREDENTIALS_AUTH_TYPE = get_string(
    name="MITOL_DIGITAL_CREDENTIALS_AUTH_TYPE",
    default=None,
    description="Auth type that is passed to the digital credentials wallet app",
    required=False,
)

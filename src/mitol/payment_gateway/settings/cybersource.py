"""
Settings for CuberSource Secure Acceptance payments and REST APIs
"""

from mitol.common.envs import get_string
from mitol.payment_gateway.constants import MITOL_PAYMENT_GATEWAY_CYBERSOURCE

ECOMMERCE_DEFAULT_PAYMENT_GATEWAY = get_string(
    name="ECOMMERCE_DEFAULT_PAYMENT_GATEWAY",
    default=MITOL_PAYMENT_GATEWAY_CYBERSOURCE,
    description="The default payment gateway to use. Must match the "
    "value of the constant in the mitol.payment_gateway library.",
)

MITOL_PAYMENT_GATEWAY_CYBERSOURCE_PROFILE_ID = get_string(
    name="MITOL_PAYMENT_GATEWAY_CYBERSOURCE_PROFILE_ID",
    default=None,
    description="CyberSource profile ID",
)

MITOL_PAYMENT_GATEWAY_CYBERSOURCE_SECURITY_KEY = get_string(
    name="MITOL_PAYMENT_GATEWAY_CYBERSOURCE_SECURITY_KEY",
    default=None,
    description="CyberSource security key",
)

MITOL_PAYMENT_GATEWAY_CYBERSOURCE_SECURE_ACCEPTANCE_URL = get_string(
    name="MITOL_PAYMENT_GATEWAY_CYBERSOURCE_SECURE_ACCEPTANCE_URL",
    default=None,
    description="CyberSource secure acceptance URL",
)

MITOL_PAYMENT_GATEWAY_CYBERSOURCE_ACCESS_KEY = get_string(
    name="MITOL_PAYMENT_GATEWAY_CYBERSOURCE_ACCESS_KEY",
    default=None,
    description="CyberSource access key",
)

MITOL_PAYMENT_GATEWAY_CYBERSOURCE_MERCHANT_ID = get_string(
    name="MITOL_PAYMENT_GATEWAY_CYBERSOURCE_MERCHANT_ID",
    default="",
    description="CyberSource merchant ID",
)

MITOL_PAYMENT_GATEWAY_CYBERSOURCE_MERCHANT_SECRET = get_string(
    name="MITOL_PAYMENT_GATEWAY_CYBERSOURCE_MERCHANT_SECRET",
    default=None,
    description="CyberSource merchant secret key",
)

MITOL_PAYMENT_GATEWAY_CYBERSOURCE_MERCHANT_SECRET_KEY_ID = get_string(
    name="MITOL_PAYMENT_GATEWAY_CYBERSOURCE_MERCHANT_SECRET_KEY_ID",
    default=None,
    description="CyberSource merchant secret key ID",
)

MITOL_PAYMENT_GATEWAY_CYBERSOURCE_REST_API_ENVIRONMENT = get_string(
    name="MITOL_PAYMENT_GATEWAY_CYBERSOURCE_REST_API_ENVIRONMENT",
    default="apitest.cybersource.com",
    description="CyberSource REST API Environment",
)

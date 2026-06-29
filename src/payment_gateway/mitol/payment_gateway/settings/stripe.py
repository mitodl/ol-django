"""Settings for the Stripe payment gateway."""

from mitol.common.envs import get_string
from mitol.payment_gateway.constants import MITOL_PAYMENT_GATEWAY_CYBERSOURCE

ECOMMERCE_DEFAULT_PAYMENT_GATEWAY = get_string(
    name="ECOMMERCE_DEFAULT_PAYMENT_GATEWAY",
    default=MITOL_PAYMENT_GATEWAY_CYBERSOURCE,
    description="The default payment gateway to use. Must match the "
    "value of the constant in the mitol.payment_gateway library.",
)

MITOL_PAYMENT_GATEWAY_STRIPE_API_KEY = get_string(
    name="MITOL_PAYMENT_GATEWAY_STRIPE_API_KEY",
    default=None,
    description="Stripe API key",
    required=True,
)

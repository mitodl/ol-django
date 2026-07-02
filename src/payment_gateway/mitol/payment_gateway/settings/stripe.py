"""Settings for the Stripe payment gateway."""

from mitol.common.envs import get_string

MITOL_PAYMENT_GATEWAY_STRIPE_API_KEY = get_string(
    name="MITOL_PAYMENT_GATEWAY_STRIPE_API_KEY",
    default=None,
    description="Stripe API key",
    required=True,
)

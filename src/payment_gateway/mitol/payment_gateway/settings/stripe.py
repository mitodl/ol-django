"""Settings for the Stripe payment gateway."""

from mitol.common.envs import get_bool, get_string

MITOL_PAYMENT_GATEWAY_STRIPE_API_KEY = get_string(
    name="MITOL_PAYMENT_GATEWAY_STRIPE_API_KEY",
    default=None,
    description="Stripe API key",
)

MITOL_PAYMENT_GATEWAY_STRIPE_ENABLE_PAYMENT_METHOD_TYPES = get_bool(
    name="MITOL_PAYMENT_GATEWAY_STRIPE_ENABLE_PAYMENT_METHOD_TYPES",
    default=False,
    description=(
        "Send configured payment method types (including custom payment methods"
        " like PayPal) to Stripe when creating a Checkout Session. Leave this off"
        " for Stripe accounts without access to custom payment methods."
    ),
)

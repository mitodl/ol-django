"""General settings for the Payment Gateway app."""

from mitol.common.envs import get_string, import_settings_modules
from mitol.payment_gateway.constants import MITOL_PAYMENT_GATEWAY_NONE

ECOMMERCE_DEFAULT_PAYMENT_GATEWAY = get_string(
    name="ECOMMERCE_DEFAULT_PAYMENT_GATEWAY",
    default=MITOL_PAYMENT_GATEWAY_NONE,
    description="The default payment gateway to use. Must match the "
    "value of the constant in the mitol.payment_gateway library.",
)

import_settings_modules(
    "mitol.payment_gateway.settings.cybersource",
    "mitol.payment_gateway.settings.stripe",
)

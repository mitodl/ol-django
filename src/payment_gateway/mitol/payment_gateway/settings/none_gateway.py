"""Settings for the NonePaymentGateway."""

from mitol.common.envs import get_bool, get_string
from mitol.payment_gateway.constants import MITOL_PAYMENT_GATEWAY_NONE_ACTION_DENY

MITOL_PAYMENT_GATEWAY_NONE_DEFAULT_ACTION = get_string(
    name="MITOL_PAYMENT_GATEWAY_NONE_DEFAULT_ACTION",
    default=MITOL_PAYMENT_GATEWAY_NONE_ACTION_DENY,
    description="Default action to take in the NonePaymentGateway.",
)
MITOL_PAYMENT_GATEWAY_NONE_SUPPRESS_APPROVE_WARNINGS = get_bool(
    name="MITOL_PAYMENT_GATEWAY_NONE_SUPPRESS_APPROVE_WARNINGS",
    default=False,
    description="Suppress warning if the action is set to approve.",
)

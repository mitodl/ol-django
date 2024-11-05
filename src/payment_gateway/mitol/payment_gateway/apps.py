"""Payment Gateway app AppConfigs"""

import os

from mitol.common.apps import BaseApp


class PaymentGatewayApp(BaseApp):
    """Default configuration for the payment gateway app"""

    name = "mitol.payment_gateway"
    label = "payment_gateway"
    verbose_name = "Payment Gateway"

    required_settings = [
        "MITOL_PAYMENT_GATEWAY_CYBERSOURCE_ACCESS_KEY",
        "MITOL_PAYMENT_GATEWAY_CYBERSOURCE_PROFILE_ID",
        "MITOL_PAYMENT_GATEWAY_CYBERSOURCE_SECURITY_KEY",
        "MITOL_PAYMENT_GATEWAY_CYBERSOURCE_SECURE_ACCEPTANCE_URL",
        "MITOL_PAYMENT_GATEWAY_CYBERSOURCE_MERCHANT_ID",
        "MITOL_PAYMENT_GATEWAY_CYBERSOURCE_MERCHANT_SECRET",
        "MITOL_PAYMENT_GATEWAY_CYBERSOURCE_MERCHANT_SECRET_KEY_ID",
    ]

    # necessary because this is a namespaced app
    path = os.path.dirname(os.path.abspath(__file__))  # noqa: PTH100, PTH120

"""Payment Gateway app AppConfigs"""

import os

from mitol.common.apps import BaseApp


class PaymentGatewayApp(BaseApp):
    """Default configuration for the payment gateway app"""

    default_auto_field = "django.db.models.BigAutoField"

    name = "mitol.payment_gateway"
    label = "payment_gateway"
    verbose_name = "Payment Gateway"

    required_settings = [
        "ECOMMERCE_DEFAULT_PAYMENT_GATEWAY",
    ]

    # necessary because this is a namespaced app
    path = os.path.dirname(os.path.abspath(__file__))  # noqa: PTH100, PTH120

"""
PaymentGateway implementation for Stripe.

Notable decisions for the MVP of this implementation:
- Tax is always inclusive. The generated price data will include any specified
  tax in the cart line item. This will not currently support using Stripe Tax
  for automated tax calculation.
- Unit price is quantized to three decimal places.
"""

from decimal import Decimal

import stripe
from django.conf import settings
from mitol.payment_gateway.api import (
    CART_ITEM_DEFINED,
    CART_ITEM_INLINE,
    BaseCartItem,
    Order,
    PaymentGateway,
)
from mitol.payment_gateway.constants import (
    MITOL_PAYMENT_GATEWAY_STRIPE,
)
from mitol.payment_gateway.exceptions import ImproperCartItemError


class StripePaymentGateway(PaymentGateway, gateway_class=MITOL_PAYMENT_GATEWAY_STRIPE):
    """
    The implementation of PaymentGateway for Stripe.

    Relevant documentation: https://docs.stripe.com/api
    """

    stripe_client = None

    @staticmethod
    def get_client_configuration():
        """
        Get the Stripe client config.
        """
        configuration_dictionary = {
            "api_key": settings.MITOL_PAYMENT_GATEWAY_STRIPE_API_KEY,
        }
        return configuration_dictionary  # noqa: RET504

    def __init__(self):
        """Initialize the gateway and bring up a Stripe client."""

        config = StripePaymentGateway.get_client_configuration()
        self.stripe_client = stripe.StripeClient(config.get("api_key", None))

    def _generate_product_data(self, item: BaseCartItem):
        """
        Generate the Stripe product data for the line.

        The shape of the data changes if the product is defined in-line or not.
        """

        if item.item_type == CART_ITEM_DEFINED:
            return {"product": item.product_id}
        elif item.item_type == CART_ITEM_INLINE:
            return {
                "product_data": {
                    "name": item.name,
                    "description": item.name,
                    "metadata": item,
                }
            }

        raise ImproperCartItemError(item)

    def _generate_price_data(self, item: BaseCartItem):
        """
        Generate the price data for the item.

        This is always defined inline for this iteration. If a taxable amount is
        defined, then that amount is added to the unit price.

        Stripe is able to calculate taxes. However, we have been historically
        calculating this ourselves. So, this **always** sets the tax behavior to
        "inclusive" so that ti does not try to re-calculate the tax. This decision
        will need to be revisited if we opt to use Stripe's tax calculation
        functionality in the future.
        """

        return {
            "price_data": {
                "currency": "USD",
                "unit_amount_decimal": (
                    Decimal(item.unitprice + item.taxable).quantize(Decimal("1.000"))
                ),
                "tax_behavior": "inclusive",
                **self._generate_product_data(item),
            }
        }

    def _generate_line_item(self, item: BaseCartItem):
        """Generate a Stripe line item."""

        return {
            "quantity": item.quantity,
            **self._generate_price_data(item),
        }

    def prepare_checkout(
        self,
        order: Order,
        receipt_url: str | None = None,
        cancel_url: str | None = None,
        backoffice_post_url: str | None = None,  # noqa: ARG002
        **kwargs,  # noqa: ARG002
    ):
        """
        Set up and return the Checkout Session.

        Stripe doesn't support changing the backoffice URL or the receipt URL, so
        passing these in will have no effect. Instead, configure these through
        the Stripe dashboard.
        """

        stripe_session_data = {
            "client_reference_id": order.reference,
            "customer_email": order.email,
            "customer": order.username,
            "line_items": [self._generate_line_item(item) for item in order.items],
            "mode": "payment",
            "ui_mode": "hosted_page",
            "success_url": receipt_url,
            "cancel_url": cancel_url,
        }

        return self.stripe_client.v1.checkout.Session.create(**stripe_session_data)

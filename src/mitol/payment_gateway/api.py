"""
API for the Payment Gateway
"""
import abc
import hashlib
import hmac
import uuid
from base64 import b64encode
from dataclasses import dataclass
from decimal import Decimal
from typing import List

from django.conf import settings

from mitol.common.utils.datetime import now_in_utc
from mitol.payment_gateway.constants import (
    ISO_8601_FORMAT,
    MITOL_PAYMENT_GATEWAY_CYBERSOURCE,
)


@dataclass
class CartItem:
    """
    Represents an item in the cart. The mappings for xPro below are meant as an
    example; the actual data passed should make sense for your application.

    Fields:
    - code: Item code (in xPro, content_type)
    - name: Item name (in xPro, description)
    - quantity: Item quantity; defaults to 1.
    - sku: Item SKU (in xPro, content_object.id)
    - unitprice: Item price, after any necessary coupon/discout calculations
    - taxable: Taxable amount; defaults to 0.
    """

    code: str
    name: str
    sku: str
    unitprice: Decimal
    quantity: int = 1
    taxable: Decimal = Decimal(0)


@dataclass
class Order:
    """
    Represents an order, and is mostly metadata for an in-progress order.

    Fields:
    - username: Purchaser username
    - ip_address: Purchaser's IP address
    - reference: Order reference number
    - items: List of CartItems representing the items to be purchased
    """

    username: str
    ip_address: str
    reference: str
    items: List[CartItem]


class PaymentGateway(abc.ABC):
    """
    PaymentGateway provides a standardized interface to payment processors.
    This is designed to work with processors that have a hosted checkout-type
    product (i.e. you assemble a payload for the processor, do some sort of
    processing to make that suitable for them, and then redirect the customer to
    the processor to capture card information).
    """

    _GATEWAYS = {}

    def __init_subclass__(cls, *, gateway_class, **kwargs):
        super().__init_subclass__()

        if gateway_class in cls._GATEWAYS:
            raise TypeError(f"{gateway_class} has already been defined")

        cls._GATEWAYS[gateway_class] = cls

    @abc.abstractmethod
    def prepare_checkout(self, order, cart, receipt_url, cancel_url, **kwargs):
        """
        This is the entrypoint to the payment gateway.
        Args:
            order: Order object (see the dataclasses above)
            receipt_url: redirect URL used by the processor when the transaction is successful
            cancel_url: redirect URL used by the processor when the transaction has been cancelled
        Keyword Args:
            merchant_fields: list containing any additional data for the transaction
        Returns:
            dictionary:
                - url: URL to the workflow on the payment processor
                - payload: payload to send to the payment processor
                - method: HTTP method to use

        Total price will be calculated as quantity * unitprice. This is the only
        calculation the gateway does (or should do) - coupons and discounts
        should be handled before starting this process.

        The merchant_fields argument is processor dependent. A given payment
        processor may not have a facility to store arbitrary data with the
        transaction. CyberSource specifically has up to 100 definable
        merchant_defined_fields that can be specified - xPro uses this, and
        that's what this is for. This should just be a standard array - the
        class that handles this should format the data as needed for the
        processor in question (or ignore it entirely).
        """
        pass

    @classmethod
    def start_payment(
        cls, payment_type, order: Order, receipt_url: str, cancel_url: str, **kwargs
    ):
        """
        Starts the payment process for the given type. See prepare_checkout for
        more detail about these arguments (other than payment_type).

        Args:
            payment_type    String; gateway class to use
            order           Dict; order information
            cart            List; cart items
            receipt_url     String; success redirect URL target
            cancel_url      String; cancel redirect URL target
        Keyword Args:
            merchant_fields List; additional info for processor
        Returns:
            see prepare_checkout
        """
        if payment_type not in cls._GATEWAYS:
            return TypeError(f"{payment_type} not defined")

        GatewayCls = cls._GATEWAYS[payment_type]()

        return GatewayCls.prepare_checkout(order, receipt_url, cancel_url, **kwargs)


class CyberSourcePaymentGateway(
    PaymentGateway, gateway_class=MITOL_PAYMENT_GATEWAY_CYBERSOURCE
):
    """
    The CyberSource implementation of Payment Gateway. This provides the data
    manipulation and signing necessary to pass transactions to CyberSource via
    their Secure Acceptance Hosted Checkout product.
    """

    def _generate_line_items(self, cart):
        """
        Generates CyberSource-formatted line items based on what's in the cart.
        Args:
            cart (list):
        """
        lines = {}
        cart_total = 0

        for i, line in enumerate(cart):
            cart_total += line.quantity * line.unitprice

            lines[f"item_{i}_code"] = str(line.code)
            lines[f"item_{i}_name"] = str(line.name)[:254]
            lines[f"item_{i}_quantity"] = line.quantity
            lines[f"item_{i}_sku"] = line.sku
            lines[f"item_{i}_tax_amount"] = str(line.taxable)
            lines[f"item_{i}_unit_price"] = str(line.unitprice)

        return (lines, cart_total)

    def _generate_cybersource_sa_signature(self, payload):
        """
        Generate an HMAC SHA256 signature for the CyberSource Secure Acceptance payload
        Args:
            payload (dict): The payload to be sent to CyberSource
        Returns:
            str: The signature
        """
        # This is documented in certain CyberSource sample applications:
        # http://apps.cybersource.com/library/documentation/dev_guides/Secure_Acceptance_SOP/html/wwhelp/wwhimpl/js/html/wwhelp.htm#href=creating_profile.05.6.html
        keys = payload["signed_field_names"].split(",")
        message = ",".join(f"{key}={payload[key]}" for key in keys)

        digest = hmac.new(
            settings.MITOL_PAYMENT_GATEWAY_CYBERSOURCE_SECURITY_KEY.encode("utf-8"),
            msg=message.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()

        return b64encode(digest).decode("utf-8")

    def _sign_cybersource_payload(self, payload):
        """
        Return a payload signed with the CyberSource key

        Args:
            payload (dict): An unsigned payload to be sent to CyberSource

        Returns:
            dict:
                A signed payload to be sent to CyberSource
        """
        field_names = sorted(list(payload.keys()) + ["signed_field_names"])
        payload = {**payload, "signed_field_names": ",".join(field_names)}
        return {
            **payload,
            "signature": self._generate_cybersource_sa_signature(payload),
        }

    def prepare_checkout(
        self, order: Order, receipt_url: str, cancel_url: str, **kwargs
    ):
        """
        This acts more as a coordinator for the internal methods in the class
        """

        (line_items, total) = self._generate_line_items(order.items)

        formatted_merchant_fields = {}

        if "merchant_fields" in kwargs and kwargs["merchant_fields"] is not None:
            for (idx, field_data) in enumerate(kwargs["merchant_fields"], start=1):
                # CyberSource maxes out at 100 of these
                # there should really only ever be 6 at most (for xPro)
                if idx > 100:
                    break

                formatted_merchant_fields[f"merchant_defined_data{idx}"] = field_data

        payload = {
            "access_key": settings.MITOL_PAYMENT_GATEWAY_CYBERSOURCE_ACCESS_KEY,
            "amount": str(total),
            "consumer_id": order.username,
            "currency": "USD",
            "locale": "en-us",
            **line_items,
            "line_item_count": len(order.items),
            **formatted_merchant_fields,
            "reference_number": order.reference,
            "profile_id": settings.MITOL_PAYMENT_GATEWAY_CYBERSOURCE_PROFILE_ID,
            "signed_date_time": now_in_utc().strftime(ISO_8601_FORMAT),
            "override_custom_receipt_page": receipt_url,
            "override_custom_cancel_page": cancel_url,
            "transaction_type": "sale",
            "transaction_uuid": uuid.uuid4().hex,
            "unsigned_field_names": "",
            "customer_ip_address": order.ip_address if order.ip_address else None,
        }

        signed_payload = self._sign_cybersource_payload(payload)

        return {
            "payload": signed_payload,
            "url": settings.MITOL_PAYMENT_GATEWAY_CYBERSOURCE_SECURE_ACCEPTANCE_URL,
            "method": "POST",
        }

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
from functools import wraps
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


@dataclass
class ProcessorResponse:
    """
    Standardizes the salient parts of the response from the
    payment gateway after a transaction has come back to the app.

    Most of these fields are going to be processor-dependent, but each
    processor should at least have a state and a message. State should
    ideally be one of the ones that there are constants for here.

    Fields:
    - state: string, should be one of the constants
    - message: string, human-readable response from the processor
    - response_code: string, code representing more info about the transaction status
    - transaction_id: string, processor-dependent ID for the transaction
    """

    state: str
    message: str
    response_code: str
    transaction_id: str

    STATE_ACCEPTED = "ACCEPT"
    STATE_DECLINED = "DECLINE"
    STATE_ERROR = "ERROR"
    STATE_CANCELLED = "CANCEL"
    STATE_REVIEW = "REVIEW"


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

    def find_gateway_class(func):
        @wraps(func)
        def _find_gateway_class(cls, payment_type, *args, **kwargs):
            if payment_type not in cls._GATEWAYS:
                return TypeError(f"{payment_type} not defined")

            return func(cls, cls._GATEWAYS[payment_type](), *args, **kwargs)

        return _find_gateway_class

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

    @abc.abstractmethod
    def perform_processor_response_validation(self, request):
        """
        Validates a response generated by the payment processor. This is meant
        to be used in an authentication class.

        Args:
            request:    HttpRequest object or equivalent (DRF Request)

        Returns:
            True or False
        """
        pass

    @abc.abstractmethod
    def decode_processor_response(self, request):
        """
        Decodes the post-completion response from the payment processor
        and converts it to a generic representation of the data.

        Args:
            request:    HttpRequest object or equivalent (DRF Request)

        Returns:
            ProcessorResponse
        """
        pass

    @classmethod
    @find_gateway_class
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

        return payment_type.prepare_checkout(order, receipt_url, cancel_url, **kwargs)

    @classmethod
    @find_gateway_class
    def validate_processor_response(cls, payment_type, request):
        """
        Kicks off validation of a processor response.

        Args:
            payment_type:   String; gateway class to use
            request:        HttpRequest object or equivalent

        Returns:
            True or False (this is implementation-specific)
        """

        return payment_type.perform_processor_response_validation(request)

    @classmethod
    @find_gateway_class
    def get_formatted_response(cls, payment_type, request):
        """
        Runs the request through the processor response decoder.

        Args:
            payment_type:   String; gateway class to use
            request:        HttpRequest object or equivalent

        Returns:
            ProcessorResponse
        """

        return payment_type.decode_processor_response(request)

    @classmethod
    @find_gateway_class
    def get_gateway_class(cls, payment_type):
        """
        Just returns the resolved payment gateway class.
        """
        return payment_type


class CyberSourcePaymentGateway(
    PaymentGateway, gateway_class=MITOL_PAYMENT_GATEWAY_CYBERSOURCE
):
    """
    The CyberSource implementation of Payment Gateway. This provides the data
    manipulation and signing necessary to pass transactions to CyberSource via
    their Secure Acceptance Hosted Checkout product.

    Documentation about this: https://developer.cybersource.com/library/documentation/dev_guides/Secure_Acceptance_Hosted_Checkout/html/index.html#t=Topics%2Fcover_ENT.htm
    """

    def _generate_line_items(self, cart):
        """
        Generates CyberSource-formatted line items based on what's in the cart.
        Args:
            cart:   List of CartItems

        Retuns:
            Tuple: formatted lines and the total cart value
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
            payload:    Dict; the payload to be sent to CyberSource
        Returns:
            str: The signature
        """

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
            payload: Dict; an unsigned payload to be sent to CyberSource

        Returns:
            dict: A signed payload to be sent to CyberSource
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

    def perform_processor_response_validation(self, request):
        """
        CyberSource will send back a payload signed in the same manner that the
        original transaction was sent, so we just reuse that process here, with
        some logic to pull the proper request data out depending on HTTP verb.
        """
        if request.method == "POST":
            passed_payload = getattr(request, "data", getattr(request, "POST", {}))
        else:
            passed_payload = getattr(
                request, "query_params", getattr(request, "GET", {})
            )

        signature = self._generate_cybersource_sa_signature(passed_payload)

        return passed_payload["signature"] == signature

    def convert_to_order(response):
        """
        CyberSource includes the order in its response, using the same
        field names prepended with "req_". This will grab those fields
        out of the response and convert it back to an Order and a set of
        CartItems. (Not all payment processor APIs may support this, so this
        is just defined for the CyberSource one.)

        Args:
            response: Dict; the data from the response

        Returns:
            Order
        """
        items = []

        for i in range(0, int(response["req_line_item_count"])):
            line = CartItem(
                code=response[f"req_item_{i}_code"],
                name=response[f"req_item_{i}_name"],
                sku=response[f"req_item_{i}_sku"],
                unitprice=response[f"req_item_{i}_unit_price"],
                taxable=response[f"req_item_{i}_tax_amount"],
                quantity=response[f"req_item_{i}_quantity"],
            )
            items.append(line)

        order = Order(
            username=response["req_consumer_id"],
            ip_address=response["req_customer_ip_address"],
            reference=response["req_reference_number"],
            items=items,
        )

        return order

    def decode_processor_response(self, request):
        """
        The CyberSource implementation of this. The ProcessorResponse
        class was designed around this processor so the state codes map
        one-to-one to the decision field that gets passed back from them.

        The reason code and transaction ID fields don't appear in certain
        states.
        """
        if request.method == "POST":
            response = getattr(request, "data", getattr(request, "POST", {}))
        else:
            response = getattr(request, "query_params", getattr(request, "GET", {}))

        fmt_response = ProcessorResponse(
            ProcessorResponse.STATE_ERROR,
            "Could not decode the processor response",
            "",
            "",
        )

        fmt_response.message = response["message"]

        # CyberSource has no reason codes for cancellation at least
        if "reason_code" in response:
            fmt_response.response_code = response["reason_code"]

        # Same for transaction_id
        if "transaction_id" in response:
            fmt_response.transaction_id = response["transaction_id"]

        if response["decision"] == "ACCEPT":
            fmt_response.state = ProcessorResponse.STATE_ACCEPTED
        elif response["decision"] == "DECLINE":
            fmt_response.state = ProcessorResponse.STATE_DECLINED
        elif response["decision"] == "ERROR":
            fmt_response.state = ProcessorResponse.STATE_ERROR
            # maybe should log here? this is a straight-up something went wrong between the app and the processor state
        elif response["decision"] == "CANCEL":
            fmt_response.state = ProcessorResponse.STATE_CANCELLED
        elif response["decision"] == "REVIEW":
            fmt_response.state = ProcessorResponse.STATE_REVIEW

        return fmt_response

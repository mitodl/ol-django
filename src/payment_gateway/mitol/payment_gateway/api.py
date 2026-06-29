"""
API for the Payment Gateway
"""

import abc
from dataclasses import dataclass
from decimal import Decimal
from functools import wraps

CART_ITEM_INLINE = "inline"
CART_ITEM_DEFINED = "defined"
CART_ITEM_UNKNOWN = "unknown"


@dataclass
class BaseCartItem:
    """
    Base fields for a cart item.

    Fields:
    - quantity: Item quantity
    - unitprice: Item price, after any necessary coupon/discout calculations
    - taxable: Taxable amount
    """

    unitprice: Decimal = Decimal(0)
    quantity: int = 1
    taxable: Decimal = Decimal(0)

    @property
    def item_type(self):
        """Return what kind of item this is."""

        return CART_ITEM_UNKNOWN


@dataclass
class LookupCartItem(BaseCartItem):
    """
    Represents an item in the cart that is also configured in the payment processor.

    We can sometimes specify a cart item using an identifier. So, this is a cart
    item with just that and pricing data.
    """

    product_id: str | None = None

    @property
    def item_type(self):
        """Return what kind of item this is."""

        return CART_ITEM_DEFINED


@dataclass
class CartItem(BaseCartItem):
    """
    Represents an item in the cart. The mappings for xPro below are meant as an
    example; the actual data passed should make sense for your application.

    Fields:
    - code: Item code (in xPro, content_type)
    - name: Item name (in xPro, description)
    - sku: Item SKU (in xPro, content_object.id)
    """

    code: str | None = None
    name: str | None = None
    sku: str | None = None

    @property
    def item_type(self):
        """Return what kind of item this is."""

        return CART_ITEM_INLINE


@dataclass
class Order:
    """
    Represents an order, and is mostly metadata for an in-progress order.

    Fields:
    - username: Purchaser username
    - email: Purchaser email (default None)
    - ip_address: Purchaser's IP address
    - reference: Order reference number
    - items: List of CartItems representing the items to be purchased
    """

    username: str
    ip_address: str
    reference: str
    items: list[BaseCartItem]
    email: str | None = None


@dataclass
class Refund:
    """
    Represents a refund request data

    Fields:
    - transaction_id: transaction id of a successful payment
    - refund_amount: Amount to be refunded
    - refund_currency: Currency for refund amount (Ideally, this should be the currency used while payment)
    """  # noqa: E501

    transaction_id: str
    refund_amount: float
    refund_currency: str


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
    # In some cases we would need this data as traceback (Can be saved in the Transaction entries in Database)  # noqa: E501
    response_data: str

    STATE_ACCEPTED = "ACCEPT"
    STATE_DECLINED = "DECLINE"
    STATE_ERROR = "ERROR"
    STATE_CANCELLED = "CANCEL"
    STATE_REVIEW = "REVIEW"
    # It's more of a reason then state, but treating this as state keeps it bound with the overall architecture  # noqa: E501
    STATE_DUPLICATE = "DUPLICATE_REQUEST"
    # The possible state for a successful refund is always `PENDING`
    STATE_PENDING = "PENDING"


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
            raise TypeError(f"{gateway_class} has already been defined")  # noqa: EM102, TRY003

        cls._GATEWAYS[gateway_class] = cls

    def find_gateway_class(func):  # noqa: N805
        @wraps(func)
        def _find_gateway_class(cls, payment_type, *args, **kwargs):
            if payment_type not in cls._GATEWAYS:
                return TypeError(f"{payment_type} not defined")

            return func(cls, cls._GATEWAYS[payment_type](), *args, **kwargs)

        return _find_gateway_class

    @abc.abstractmethod
    def prepare_checkout(
        self, order, receipt_url, cancel_url, backoffice_post_url, **kwargs
    ):
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
        """  # noqa: E501, D401

    @staticmethod
    @abc.abstractmethod
    def get_refund_request(transaction_dict: dict):
        """
        This is the entrypoint to the payment gateway for creating refund request objects.
        Args:
            transaction_dict (Dict): Data dictionary of the payment transaction response of the Gateway
        Returns:
            Object (Refund): Refund An object of Refund class that can be used for Refund operations

        """  # noqa: E501, D401

    @abc.abstractmethod
    def perform_processor_response_validation(self, request):
        """
        Validates a response generated by the payment processor. This is meant
        to be used in an authentication class.

        Args:
            request:    HttpRequest object or equivalent (DRF Request)

        Returns:
            True or False
        """  # noqa: D401

    @abc.abstractmethod
    def decode_processor_response(self, request):
        """
        Decodes the post-completion response from the payment processor
        and converts it to a generic representation of the data.

        Args:
            request:    HttpRequest object or equivalent (DRF Request)

        Returns:
            ProcessorResponse
        """  # noqa: D401

    @staticmethod
    @abc.abstractmethod
    def get_client_configuration():
        """
        This is the function that will provide required configuration for a PaymentGateway
        """  # noqa: E501, D401

    @abc.abstractmethod
    def perform_refund(self, refund):
        """
        This is the entrypoint to the payment gateway.

        Args:
            refund: (Refund) Data class for refund request (see the data classes above)
        Returns:
            ProcessorResponse

        """  # noqa: D401

    @classmethod
    @find_gateway_class
    def start_payment(
        cls,
        payment_type,
        order: Order,
        receipt_url: str,
        cancel_url: str,
        backoffice_post_url: str | None = None,
        **kwargs,
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
        """  # noqa: D401

        return payment_type.prepare_checkout(
            order, receipt_url, cancel_url, backoffice_post_url, **kwargs
        )

    @classmethod
    @find_gateway_class
    def create_refund_request(cls, payment_type, transaction_dict: dict):
        """
        Iterate through the given payment transaction dictionary and returns a refund object to perform operations on.
        Args:
            payment_type (String): gateway class to use
            transaction_dict (Dict): Dictionary of the data acquired through a successful Gateway payment
        Returns:
            see get_refund_request
        """  # noqa: E501

        return payment_type.get_refund_request(transaction_dict)

    @classmethod
    @find_gateway_class
    def start_refund(cls, payment_type, refund: Refund):
        """
        Starts the payment refund process for the given type. See prepare_checkout for
        more detail about these arguments (other than payment_type).

        Args:
            payment_type    String; gateway class to use
            refund          Object: Refund
        Returns:
            see perform_refund
        """  # noqa: D401

        return payment_type.perform_refund(refund)

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
        """  # noqa: D401

        return payment_type.decode_processor_response(request)

    @classmethod
    @find_gateway_class
    def get_gateway_class(cls, payment_type):
        """
        Just returns the resolved payment gateway class.
        """
        return payment_type

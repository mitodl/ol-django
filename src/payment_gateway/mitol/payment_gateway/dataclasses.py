"""
Dataclasses for PaymentGateway.

These are the helper models for migrating data into and out of PaymentGateway
in a standard way, so it can then reformat it for the payment processor.
"""

from dataclasses import dataclass
from decimal import Decimal

from mitol.payment_gateway.constants import (
    CART_ITEM_DEFINED,
    CART_ITEM_INLINE,
    CART_ITEM_UNKNOWN,
)


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
    items: list[CartItem | LookupCartItem]
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
    refund_amount: float | Decimal
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


@dataclass
class StripeCheckoutSessionStatus:
    """Describes the overall status of a Stripe checkout session."""

    status: str
    checkout_session_id: str
    payment_intent_id: str | None
    cancel_reason: str | None
    action_reason: str | None
    transaction: dict | None

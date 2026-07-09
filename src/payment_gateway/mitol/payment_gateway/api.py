"""
API for the Payment Gateway
"""

import abc
import hashlib
import hmac
import json
import logging
import uuid
import warnings
from base64 import b64encode
from dataclasses import asdict, dataclass
from decimal import Decimal
from functools import wraps

with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=SyntaxWarning)
    from CyberSource import (
        CreateSearchRequest,
        Ptsv2paymentsClientReferenceInformation,
        Ptsv2paymentsidcapturesOrderInformationAmountDetails,
        Ptsv2paymentsidrefundsOrderInformation,
        RefundApi,
        RefundPaymentRequest,
        SearchTransactionsApi,
        TransactionDetailsApi,
    )
import stripe
from django.conf import settings
from django.http import HttpRequest
from mitol.common.utils.datetime import now_in_utc
from mitol.payment_gateway.constants import (
    CART_ITEM_DEFINED,
    CART_ITEM_INLINE,
    CART_ITEM_UNKNOWN,
    ISO_8601_FORMAT,
    MITOL_PAYMENT_GATEWAY_CYBERSOURCE,
    MITOL_PAYMENT_GATEWAY_STRIPE,
)
from mitol.payment_gateway.exceptions import (
    BadStripeWebhookSecretError,
    ImproperCartItemError,
    ImproperlyConfiguredError,
    ImproperStripeWebhookRequestError,
    InvalidTransactionException,
    NoStripeWebhookSecretError,
    RefundDuplicateException,
)
from mitol.payment_gateway.models import StripeWebhookSecret
from mitol.payment_gateway.payment_utils import (
    clean_request_data,
    quantize_decimal,
    strip_nones,
)

log = logging.getLogger(__name__)


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

        The unit price being stored should be the unit price after any discounts
        have been applied. The tax amount should be the _total_ for the line.

        Args:
            cart:   List of CartItems

        Retuns:
            Tuple: formatted lines and the total cart value
        """  # noqa: D401
        lines = {}
        cart_total = 0
        tax_total = 0

        for i, line in enumerate(cart):
            cart_total += line.quantity * line.unitprice
            tax_total += line.taxable

            lines[f"item_{i}_code"] = str(line.code)
            lines[f"item_{i}_name"] = str(line.name)[:254]
            lines[f"item_{i}_quantity"] = line.quantity
            lines[f"item_{i}_sku"] = line.sku
            lines[f"item_{i}_tax_amount"] = str(line.taxable)
            lines[f"item_{i}_unit_price"] = str(line.unitprice)

        return (lines, cart_total, tax_total)

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
        field_names = sorted(list(payload.keys()) + ["signed_field_names"])  # noqa: RUF005
        payload = {**payload, "signed_field_names": ",".join(field_names)}
        return {
            **payload,
            "signature": self._generate_cybersource_sa_signature(payload),
        }

    def prepare_checkout(
        self,
        order: Order,
        receipt_url: str,
        cancel_url: str,
        backoffice_post_url: str | None = None,
        **kwargs,
    ):
        """
        This acts more as a coordinator for the internal methods in the class.

        The username attached to the order is passed to CyberSource. However, it
        won't accept an email address-like username (see
        https://github.com/mitodl/mitxonline/issues/593), so this generates a
        sha256 hash of the username to pass in to CyberSource. This hash isn't
        stored anywhere.
        """  # noqa: D401

        (line_items, total, tax_total) = self._generate_line_items(order.items)

        formatted_merchant_fields = {}

        if "merchant_fields" in kwargs and kwargs["merchant_fields"] is not None:
            for idx, field_data in enumerate(kwargs["merchant_fields"], start=1):
                # CyberSource maxes out at 100 of these
                # there should really only ever be 6 at most (for xPro)
                if idx > 100:  # noqa: PLR2004
                    break

                formatted_merchant_fields[f"merchant_defined_data{idx}"] = field_data

        consumer_id = hashlib.sha256(order.username.encode("utf-8")).hexdigest()

        payload = {
            "access_key": settings.MITOL_PAYMENT_GATEWAY_CYBERSOURCE_ACCESS_KEY,
            "amount": str(quantize_decimal(total + tax_total)),
            "tax_amount": str(quantize_decimal(tax_total)),
            "consumer_id": consumer_id,
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
        if backoffice_post_url:
            payload["override_backoffice_post_url"] = backoffice_post_url

        signed_payload = self._sign_cybersource_payload(payload)

        return {
            "payload": signed_payload,
            "url": settings.MITOL_PAYMENT_GATEWAY_CYBERSOURCE_SECURE_ACCEPTANCE_URL,
            "method": "POST",
        }

    @staticmethod
    def get_client_configuration():
        """
        Get the configuration required for CyberSource API client
        """
        configuration_dictionary = {
            "authentication_type": "http_signature",
            "merchantid": settings.MITOL_PAYMENT_GATEWAY_CYBERSOURCE_MERCHANT_ID,
            "run_environment": settings.MITOL_PAYMENT_GATEWAY_CYBERSOURCE_REST_API_ENVIRONMENT,  # noqa: E501
            "merchant_keyid": settings.MITOL_PAYMENT_GATEWAY_CYBERSOURCE_MERCHANT_SECRET_KEY_ID,  # noqa: E501
            "merchant_secretkey": settings.MITOL_PAYMENT_GATEWAY_CYBERSOURCE_MERCHANT_SECRET,  # noqa: E501
            "timeout": 1000,
        }
        return configuration_dictionary  # noqa: RET504

    @staticmethod
    def get_refund_request(transaction_dict: dict):
        """
        Create a refund request object to from the required attributes in the payment dictionary
        Args:
            transaction_dict: (Dict) Data dictionary of the payment response of the Gateway
            Ideally, The transaction dictionary should have transaction_id, req_amount, req_currency in case of
            CyberSource.
        Returns:
            Object: Refund An object of Refund class that can be used to operate the Refunds

        """  # noqa: E501
        try:
            # If a required value exists we can't decide if it's valid so let the API throw that error itself  # noqa: E501
            transaction_id = transaction_dict["transaction_id"]
            order_amount = transaction_dict["req_amount"]
            order_currency = transaction_dict["req_currency"]

            return Refund(
                transaction_id=transaction_id,
                refund_amount=order_amount,
                refund_currency=order_currency,
            )
        except KeyError as error:
            raise InvalidTransactionException() from error  # noqa: RSE102

    def perform_refund(self, refund):
        """
        Based on the provided refund detail data object, this method calls the cyber source refund API call after
        performing the appropriate operation on the data.

        returns:
            i) API Success:
                Returns a ProcessorResponse object that the caller app can use to perform whatever they need

            ii)  API Failure ("DUPLICATE_REQUEST"):
                Raises RefundDuplicateException when the refund API call is duplicate

            iii)  API Failure (General):
                Raises the exception(Mostly CyberSource.rest.ApiException) to the caller to decide what their
                application behaviour
        """  # noqa: E501

        api_instance = RefundApi(self.get_client_configuration())
        refund_payload = self.generate_refund_payload(refund)
        transaction_id = refund.transaction_id

        try:
            _return_data, _status, body = api_instance.refund_payment(
                refund_payload, transaction_id
            )
            response_body = json.loads(body)

            # Transforming the response in a format that process response decoder can work on while keeping our  # noqa: E501
            # structure consistent
            response_transformed = {
                "data": response_body,
                "reason_code": response_body.get("processorInformation", {}).get(
                    "responseCode", ""
                ),
                "transaction_id": transaction_id,
                "message": "The refund request was successful",
                "decision": response_body["status"],
            }

            response = self.decode_processor_api_response(response_transformed)
            return response  # noqa: RET504, TRY300

        except Exception as ex:
            exception_body = json.loads(ex.body)

            # Special case for request failure when DUPLICATE_REQUEST
            if exception_body["reason"] == ProcessorResponse.STATE_DUPLICATE:
                raise RefundDuplicateException(  # noqa: B904
                    exception_body["reason"],
                    transaction_id,
                    refund.refund_amount,
                    exception_body,
                    message=exception_body["message"],
                )

            raise ex  # noqa: TRY201

    def generate_refund_payload(self, refund):
        """
        CyberSource API client would expect the payload in a specific format to perform the refund API call.
        This method generated that payload out of the Refund data class(s)
        """  # noqa: E501
        transaction_id = refund.transaction_id
        order_information_amount_details = (
            Ptsv2paymentsidcapturesOrderInformationAmountDetails(
                total_amount=refund.refund_amount, currency=refund.refund_currency
            )
        )

        order_information = Ptsv2paymentsidrefundsOrderInformation(
            amount_details=clean_request_data(order_information_amount_details.__dict__)
        )
        client_reference_information = Ptsv2paymentsClientReferenceInformation(
            transaction_id=transaction_id
        )
        refund_request = RefundPaymentRequest(
            client_reference_information=clean_request_data(
                client_reference_information.__dict__
            ),
            order_information=clean_request_data(order_information.__dict__),
        )
        refund_request = refund_request.__dict__

        return json.dumps(refund_request)

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

    def convert_to_order(self, response):
        """
        CyberSource includes the order in its response, using the same
        field names prepended with "req_". This will grab those fields
        out of the response and convert it back to an Order and a set of
        CartItems. (Not all payment processor APIs may support this, so this
        is just defined for the CyberSource one.)

        Note that the username that is returned by CyberSource will be the
        sha256 hash of the username that was originally passed in, and *not* the
        actual username.

        Args:
            response: Dict; the data from the response

        Returns:
            Order
        """
        items = []

        for i in range(int(response["req_line_item_count"])):
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

        return order  # noqa: RET504

    def decode_processor_response(self, request):
        """
        The CyberSource implementation of this. The ProcessorResponse
        class was designed around this processor so the state codes map
        one-to-one to the decision field that gets passed back from them.

        The reason code and transaction ID fields don't appear in certain
        states.
        """  # noqa: D401
        if request.method == "POST":
            response = getattr(request, "data", getattr(request, "POST", {}))
        else:
            response = getattr(request, "query_params", getattr(request, "GET", {}))

        fmt_response = ProcessorResponse(
            ProcessorResponse.STATE_ERROR,
            "Could not decode the processor response",
            "",
            "",
            "",
        )

        # Format the order response using quick wrapping functions
        fmt_response.message = self._get_response_message(response)
        fmt_response.response_code = self._get_reason_code(response)
        fmt_response.transaction_id = self._get_response_transaction_id(response)
        fmt_response.state = self._get_decision_from_response(response)

        return fmt_response

    def decode_processor_api_response(self, response):
        """
        The CyberSource implementation for decoding the processor response specifically for the API calls. The response
        from the SecureAccept and the REST API calls is different so like "decode_processor_response"
        this method generates the common ProcessorResponse out of the API response
        """  # noqa: E501, D401

        fmt_response = ProcessorResponse(
            ProcessorResponse.STATE_ERROR,
            "Could not decode the processor response",
            "",
            "",
            "",
        )
        fmt_response.message = self._get_response_message(response)

        # CyberSource has no reason codes for cancellation at least
        fmt_response.response_code = self._get_reason_code(response)

        # Same for transaction_id
        fmt_response.transaction_id = self._get_response_transaction_id(response)

        fmt_response.state = self._get_decision_from_response(response)
        fmt_response.response_data = response.get("data", "")

        return fmt_response

    def _get_response_message(self, response):
        """Getter for message key from payload"""
        return response.get("message", "")

    def _get_reason_code(self, response):
        """Getter for reason_code key from payload"""
        return response.get("reason_code", "")

    def _get_response_transaction_id(self, response):
        """Getter for transaction_id key from payload"""
        return response.get("transaction_id", "")

    def _get_decision_from_response(self, response):  # noqa: PLR0911
        """Getter for appropriate response state based on the decision key from payload"""  # noqa: E501
        decision = response.get("decision", None)

        if not decision or decision == "ERROR":
            return ProcessorResponse.STATE_ERROR
        elif decision == "ACCEPT":
            return ProcessorResponse.STATE_ACCEPTED
        elif decision == "DECLINE":
            return ProcessorResponse.STATE_DECLINED
            # maybe should log here? this is a straight-up something went wrong between the app and the processor state  # noqa: E501
        elif decision == "CANCEL":
            return ProcessorResponse.STATE_CANCELLED
        elif decision == "REVIEW":
            return ProcessorResponse.STATE_REVIEW
        elif decision == "PENDING":
            return ProcessorResponse.STATE_PENDING

        return ProcessorResponse.STATE_ERROR

    def find_transactions(self, reference_numbers: list[str], limit=20):
        """
        Performs a search for the transactions specified. For simplicity, this
        assumes the data set specified is reference numbers. If your system doesn't
        produce unique reference numbers (or if they get reused for whatever reason),
        this will likely return multiple transactions for the same order ID.

        Args:
        - reference_numbers (list of strings): List of reference numbers to look for
        - limit (int): Max number of rows to return (defaults to 20)

        Returns:
        - List of CyberSource transaction IDs

        Raises:
        - Exception if HTTP status returned is > 299
        - Any exception raised by the SearchTransactionsApi call
        """  # noqa: D401

        api = SearchTransactionsApi(self.get_client_configuration())

        query_string = " OR ".join(
            [f"clientReferenceInformation.code:{s}" for s in reference_numbers]
        )

        query_request = CreateSearchRequest(
            save=False,
            name="MITOL",
            timezone=settings.TIME_ZONE,
            offset=0,
            limit=limit,
            sort="submitTimeUtc:desc",
            query=query_string,
        )

        response, status, _body = api.create_search(
            json.dumps(strip_nones(query_request.__dict__))
        )

        if status > 299:  # noqa: PLR2004
            raise Exception(  # noqa: TRY002, TRY003
                f"CyberSource API returned HTTP status {status}: {response!s}"  # noqa: EM102
            )

        if response.total_count == 0:
            return []

        return [
            [
                summary.id,
                summary.client_reference_information.code,
                summary.submit_time_utc,
            ]
            for summary in response._embedded.transaction_summaries  # noqa: SLF001
        ]

    def get_transaction_details(self, transaction: str):
        """
        Gets the details for a particular transaction. The details will be
        reformmated into a format resembling a CyberSource payload. This expects
        a CyberSource transaction ID, not an app-specific ID; the
        find_transactions method can be used to retrieve that if you don't have
        the transaction ID.

        Args:
        - transaction: CyberSource transaction ID to retrieve

        Returns:
        - Tuple of TssV2TransactionsGet200Response and a CyberSource-specific transaction object

        Raises:
        - Exception if HTTP status returned is > 299
        - Any exception raised by the TransactionDetailsApi call
        """  # noqa: E501, D401

        api = TransactionDetailsApi(self.get_client_configuration())

        response, status, _body = api.get_transaction(transaction)

        if status > 299:  # noqa: PLR2004
            raise Exception(  # noqa: TRY002, TRY003
                f"CyberSource API returned HTTP status {status}: {response!s}"  # noqa: EM102
            )

        payload = {
            "utf8": "",
            "message": response.application_information.applications[-1].r_message,
            "decision": response.application_information.applications[-1].reason_code,
            "auth_code": response.processor_information.approval_code,
            "auth_time": response.submit_time_utc,
            "signature": "",
            "req_amount": response.order_information.amount_details.total_amount,
            "req_locale": "en-us",
            "auth_amount": response.order_information.amount_details.authorized_amount,
            "reason_code": response.application_information.applications[
                -1
            ].reason_code,
            "req_currency": response.order_information.amount_details.currency,
            "auth_avs_code": response.processor_information.avs.code,
            "auth_response": response.processor_information.response_code,
            "req_card_type": "",
            "request_token": "",
            "card_type_name": "",
            "req_access_key": "",
            "req_profile_id": settings.MITOL_PAYMENT_GATEWAY_CYBERSOURCE_PROFILE_ID,
            "transaction_id": response.root_id,
            "req_card_number": "",
            "req_consumer_id": response.buyer_information.merchant_customer_id,
            "req_line_item_count": len(response.order_information.line_items),
            "signed_date_time": response.submit_time_utc,
            "auth_avs_code_raw": response.processor_information.avs.code_raw,
            "auth_trans_ref_no": response.processor_information.network_transaction_id,
            "bill_trans_ref_no": response.processor_information.network_transaction_id,
            "req_payment_method": "card",
            "req_card_expiry_date": f"{response.payment_information.card.expiration_month}-{response.payment_information.card.expiration_year}",  # noqa: E501
            "req_transaction_type": "sale",
            "req_transaction_uuid": "",
            "req_customer_ip_address": response.device_information.ip_address,
            "signed_field_names": "",
            "req_bill_to_email": response.order_information.bill_to.email,
            "req_bill_to_surname": response.order_information.bill_to.last_name,
            "req_bill_to_forename": response.order_information.bill_to.first_name,
            "req_bill_to_address_city": response.order_information.bill_to.locality,
            "req_bill_to_address_line1": response.order_information.bill_to.address1,
            "req_bill_to_address_state": response.order_information.bill_to.administrative_area,  # noqa: E501
            "req_bill_to_address_country": response.order_information.bill_to.country,
            "req_bill_to_address_postal_code": response.order_information.bill_to.postal_code,  # noqa: E501
            "req_override_custom_cancel_page": "https://rc.mitxonline.mit.edu/checkout/result/",
            "req_override_custom_receipt_page": "https://rc.mitxonline.mit.edu/checkout/result/",
            "req_card_type_selection_indicator": response.payment_information.card.type,
            "req_reference_number": response.client_reference_information.code,
        }

        for idx, line_item in enumerate(response.order_information.line_items):
            payload = {
                **payload,
                f"req_item_{idx}_quantity": line_item.quantity,
                f"req_item_{idx}_code": line_item.product_code,
                f"req_item_{idx}_name": line_item.product_name,
                f"req_item_{idx}_tax_amount": line_item.tax_amount,
                f"req_item_{idx}_unit_price": line_item.unit_price,
                f"req_item_{idx}_sku": line_item.product_sku,
            }

        for merchant_info in response.merchant_defined_information:
            payload = {
                **payload,
                f"req_merchant_defined_data{merchant_info.key}": merchant_info.value,
            }

        return (response, payload)

    def find_and_get_transactions(self, reference_numbers: list[str]):
        """
        For the reference numbers specified, gets the transaction details and
        returns that. In the case that there are multiple results for the
        reference number, the *last* one will be the one it uses.

        Args:
        - reference_numbers (list of str): app-specific reference numbers to search for

        Returns:
        - Dict of formatted responses. The keys will be the reference numbers.
        """

        limit = len(reference_numbers) if len(reference_numbers) > 20 else 20  # noqa: PLR2004
        results = {}

        searches = self.find_transactions(reference_numbers, limit)

        for search in searches:
            results[search[1]] = search[0]

        for order_id in results.items():
            search_id = results[order_id]

            (_orig_response, formatted_response) = self.get_transaction_details(
                search_id
            )

            results[order_id] = formatted_response

        return results


class StripePaymentGateway(PaymentGateway, gateway_class=MITOL_PAYMENT_GATEWAY_STRIPE):
    """
    The implementation of PaymentGateway for Stripe.

    Relevant documentation: https://docs.stripe.com/api
    """

    stripe_client: stripe.StripeClient | None = None

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

        if not self.stripe_client:
            msg = "Unable to instantiate Stripe client."
            raise ImproperlyConfiguredError(msg)

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
                    "metadata": asdict(item),
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

        It's not entirely clear here from the docs but you actually have to pass
        the price in cents (for USD).
        """

        return {
            "price_data": {
                "currency": "USD",
                "unit_amount_decimal": (
                    Decimal(item.unitprice + item.taxable).quantize(Decimal("1.00"))
                    * 100
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
        backoffice_post_url: str | None = None,
        **kwargs,
    ):
        """
        Set up and return the Checkout Session.

        Checkout Session is Stripe's payment workflow. These are created via an
        API call, resulting in a Checkout Session object that includes a URL to
        send the user to.

        The full session object is returned in the "payload" key. The session
        object includes the ID for the session; this should be retained for
        future processing (e.g. on the success page), but the remaining data is
        not used by Payment Gateway.

        Stripe can inject the session ID into the receipt and cancel URLs. Also,
        the backoffice URL (webhook target URL) cannot be set here and will
        generate a warning message in the log if set. For more information, see
        README-Stripe.md.
        """

        if backoffice_post_url:
            log.warning(
                "prepare_checkout: custom backoffice URL set for Stripe "
                "transaction, ignoring"
            )

        merchant_fields = kwargs.get("merchant_fields", {})

        stripe_session_data = {
            "client_reference_id": order.reference,
            "customer_email": order.email,
            "line_items": [self._generate_line_item(item) for item in order.items],
            "mode": "payment",
            "ui_mode": "hosted_page",
            "success_url": receipt_url,
            "cancel_url": cancel_url,
            "metadata": merchant_fields if isinstance(merchant_fields, dict) else None,
        }

        response = self.stripe_client.v1.checkout.sessions.create(stripe_session_data)

        return {
            "payload": response,
            "url": response.url,
            "method": "GET",
        }

    @staticmethod
    def get_refund_request(transaction_dict: dict):
        """Set up and return a refund."""

        raise NotImplementedError

    def perform_processor_response_validation(self, request: HttpRequest):
        """
        Check for the signature header, and validate the signature against the store.

        Stripe signs webhook requests with a shared key. This key is specific to
        the configured webhook - there may be multiple valid keys configured for
        different webhooks, and there may be different configured webhooks for
        the same event type.

        The key store includes a mapping of urlconf routes to keys. This checks
        the provided signed signature against all of the applicable keys. If no
        keys are found (at all), then NoStripeWebhookSecretError is raised. If
        none of the keys are valid for the signature, then BadStripeWebhookSecretError
        is raised.

        If verification is successful, the event is returned.
        """

        payload = request.body

        if len(payload) == 0:
            msg = "Empty payload received."
            raise ImproperStripeWebhookRequestError(msg)

        try:
            payload_json = json.loads(payload)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            msg = "Improper JSON payload found."
            raise ImproperStripeWebhookRequestError(msg) from exc

        if "id" not in payload_json:
            msg = "Improper JSON payload found (no 'id' prop)."
            raise ImproperStripeWebhookRequestError(msg)

        event_id = payload_json["id"]

        if request.resolver_match:
            route = request.resolver_match.route
        else:
            log.warning(
                "StripePaymentGateway: could not get the route from the request,"
                " using path_info instead"
            )
            route = request.path_info

        key_qs = StripeWebhookSecret.objects.filter(routes__url_name=route)

        if not key_qs.exists():
            raise NoStripeWebhookSecretError(event_id=event_id, route=route)

        signature_to_validate = request.headers.get("Stripe-Signature", False)
        found_valid_key = False

        for key in key_qs.all():
            try:
                event = self.stripe_client.construct_event(
                    payload,
                    signature_to_validate,
                    key.webhook_secret,
                )
                found_valid_key = True
                break
            except ValueError as exc:
                raise ImproperStripeWebhookRequestError from exc
            except stripe.error.SignatureVerificationError:
                # We expect this one - if there's >1 key, then only one will be valid.
                pass

        if not found_valid_key:
            raise BadStripeWebhookSecretError(event_id=event_id, route=route)

        return event

    def decode_processor_response(self, request: HttpRequest):
        """
        Decode the response from Stripe.

        The validation returns the event; the event object contains the data
        associated with the event, so this strips the event parts out and returns
        just the data. The data returned will depend on the event that was triggered.
        """

        return self.perform_processor_response_validation(request).data.object

    def perform_refund(self, refund):
        """Perform a refund for an order."""

        raise NotImplementedError

    def retrieve_checkout(self, checkout_session_id):
        """
        Retrieve the Checkout Session.

        The response data will be normalized into the ProcessorResponse object,
        as that is designed to hold the data for a transaction. The Checkout
        Session only really has a "paid" and "not paid" status, so those are
        mapped to "accepted" and "pending". The full response is returned in
        response_data as a JSON-encoded string.

        This is most useful for the landing pages post-checkout - webhooks will
        be presented with an event that includes the checkout data.
        """

        response = self.stripe_client.v1.checkout.sessions.retrieve(checkout_session_id)

        return ProcessorResponse(
            state=(
                ProcessorResponse.STATE_ACCEPTED
                if response.payment_status != "unpaid"
                else ProcessorResponse.STATE_PENDING
            ),
            message="",
            response_code=response.payment_status,
            transaction_id=response.id,
            response_data=json.dumps(response),
        )

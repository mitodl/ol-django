"""Exceptions for the Payment Gateway"""

# Generic errors


class ImproperCartItemError(Exception):
    """Raised if the cart item is not configured correctly."""


class ImproperlyConfiguredError(Exception):
    """Raised if the gateway is missing settings."""


# CyberSource-specific errors


class RefundDuplicateException(Exception):  # noqa: N818
    """Exception class for Duplicate Refund requests"""

    def __init__(
        self,
        refund_reason_code,
        refund_transaction_id,
        refund_amount,
        response_body,
        message=None,
    ):
        self.reason_code = refund_reason_code
        self.transaction_id = refund_transaction_id
        self.amount = refund_amount
        self.body = response_body

        if message is None:
            message = f"There was an error in Refund API for transaction_id={self.transaction_id} with ReasonCode={self.reason_code}"  # noqa: E501
        super().__init__(message)


class InvalidTransactionException(Exception):  # noqa: N818
    """Exception class for Invalid transaction data"""

    def __init__(
        self,
        message=None,
    ):
        if message is None:
            message = "The provided transaction dictionary is invalid. Please check it contains transaction_id, req_amount, req_currency"  # noqa: E501

        super().__init__(message)


# Stripe-specifc errors


class NoStripeWebhookSecretError(Exception):
    """Raised when there isn't a matching secret for the route."""

    def __init__(
        self,
        event_id: str,
        route: str,
    ):
        self.event_id = event_id
        self.route = route

        message = (
            f"Unable to find a Stripe webhook secret for event '{event_id}'"
            f" received at route {route}."
        )

        super().__init__(message)


class BadStripeWebhookSecretError(Exception):
    """Raised when the signature can't be validated by any of the stored secrets."""

    def __init__(
        self,
        event_id: str,
        route: str,
    ):
        self.event_id = event_id
        self.route = route

        message = (
            f"No valid stored Stripe webhook secret(s) for event '{event_id}'"
            f" received at route {route}."
        )

        super().__init__(message)


class ImproperStripeWebhookRequestError(Exception):
    """Raised when validation encounters a request that isn't set up correctly."""

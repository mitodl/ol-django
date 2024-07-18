"""Exceptions for CyberSource"""


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

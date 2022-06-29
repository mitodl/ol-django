"""Exceptions for CyberSource"""


class RefundDuplicateException(Exception):
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
            self.message = f"There was an error in Refund API for transaction_id={self.transaction_id} with ReasonCode={self.reason_code}"
        super().__init__(message)

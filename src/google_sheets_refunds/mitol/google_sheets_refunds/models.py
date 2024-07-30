"""Models for Refunds"""
from mitol.google_sheets.models import GoogleSheetsRequestModel


class RefundRequest(GoogleSheetsRequestModel):
    """Model that represents a request to refund an enrollment"""

    def __str__(self):
        return "RefundRequest: id={}, form_response_id={}, completed={}".format(
            self.id, self.form_response_id, self.date_completed is not None
        )

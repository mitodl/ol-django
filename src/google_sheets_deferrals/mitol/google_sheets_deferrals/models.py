"""Models for Deferrals"""
from mitol.google_sheets.models import GoogleSheetsRequestModel


class DeferralRequest(GoogleSheetsRequestModel):
    """Model that represents a request to defer an enrollment"""

    def __str__(self):
        return "DeferralRequest: id={}, form_response_id={}, completed={}".format(
            self.id, self.form_response_id, self.date_completed is not None
        )

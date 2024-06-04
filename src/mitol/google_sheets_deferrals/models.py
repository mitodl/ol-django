"""Models for Deferrals"""

from mitol.google_sheets.models import GoogleSheetsRequestModel


class DeferralRequest(GoogleSheetsRequestModel):
    """Model that represents a request to defer an enrollment"""

    def __str__(self):
        return f"DeferralRequest: id={self.id}, form_response_id={self.form_response_id}, completed={self.date_completed is not None}"

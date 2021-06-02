"""URL configurations for digital credentials"""
from django.urls import path

from mitol.digitalcredentials.views import DigitalCredentialIssueView

app_name = "digital-credentials"

urlpatterns = [
    path(
        "credentials/issue/<str:uuid>/",
        DigitalCredentialIssueView.as_view(),
        name="credentials-issue",
    )
]

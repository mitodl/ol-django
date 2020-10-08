"""URL configurations for digital credentials"""
from django.urls import path

from mitol.digitalcredentials.views import DigitalCredentialRequestView


app_name = "digital-credentials"

urlpatterns = [
    path(
        "credentials/request/<str:uuid>/",
        DigitalCredentialRequestView.as_view(),
        name="credentials-request",
    )
]

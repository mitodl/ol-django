"""URL configurations for authentication.

Include either this module (no API gateway) or mitol.apigateway.urls (gateway
in front of the app) - not both; the apigateway views subsume these.
"""

from django.urls import re_path
from mitol.authentication.views import LoginRedirectView, LogoutRedirectView

urlpatterns = [
    re_path(r"^logout/?$", LogoutRedirectView.as_view(), name="logout"),
    re_path(r"^login/?$", LoginRedirectView.as_view(), name="login"),
]

"""URL configurations for authentication"""

from django.urls import re_path
from mitol.authentication.views import LoginRedirectView, LogoutRedirectView

urlpatterns = [
    re_path(r"^logout", LogoutRedirectView.as_view(), name="logout"),
    re_path(r"^login", LoginRedirectView.as_view(), name="login"),
]

"""Authentication views"""

from mitol.authentication.views.auth import (
    AuthRedirectView,
    LoginRedirectView,
    LogoutRedirectView,
)

__all__ = [
    "AuthRedirectView",
    "LoginRedirectView",
    "LogoutRedirectView",
]

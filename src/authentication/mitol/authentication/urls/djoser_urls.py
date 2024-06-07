"""URL configuration for djoser reset password functionality"""

from django.urls import path

from mitol.authentication.views.djoser_views import CustomDjoserAPIView

urlpatterns = [
    path(
        "password_reset/",
        CustomDjoserAPIView.as_view({"post": "reset_password"}),
        name="password-reset-api",
    ),
    path(
        "password_reset/confirm/",
        CustomDjoserAPIView.as_view({"post": "reset_password_confirm"}),
        name="password-reset-confirm-api",
    ),
    path(
        "set_password/",
        CustomDjoserAPIView.as_view({"post": "set_password"}),
        name="set-password-api",
    ),
]

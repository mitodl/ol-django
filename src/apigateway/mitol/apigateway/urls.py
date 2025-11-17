"""URL routes for the apigateway app."""

from django.urls import re_path

from mitol.apigateway.views import ApiGatewayLogoutView

urlpatterns = [
    re_path(r"^logout", ApiGatewayLogoutView.as_view(), name="logout"),
]

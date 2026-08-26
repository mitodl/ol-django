"""URL routes for the apigateway app."""

from django.urls import re_path
from mitol.apigateway.views import ApiGatewayLoginView, ApiGatewayLogoutView

urlpatterns = [
    re_path(r"^logout/?$", ApiGatewayLogoutView.as_view(), name="logout"),
    re_path(r"^login/?$", ApiGatewayLoginView.as_view(), name="login"),
]

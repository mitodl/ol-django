"""URL routes for the apigateway app. Mostly for testing."""

from django.urls import path

from mitol.apigateway.views import ApiGatewayLogoutView

urlpatterns = [
    path(
        "applogout/",
        ApiGatewayLogoutView.as_view(),
        name="logout",
    ),
]

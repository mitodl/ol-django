"""testapp URL Configuration"""
from django.urls import include, path


urlpatterns = [
    path(r"", include("social_django.urls", namespace="social")),
    path("", include("mitol.authentication.urls.saml")),
]  # pragma: no cover

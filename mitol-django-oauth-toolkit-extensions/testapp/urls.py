"""testapp URL Configuration"""
from django.contrib import admin
from django.urls import include, path
from oauth2_provider.urls import base_urlpatterns


urlpatterns = [
    path(
        "oauth2/",
        include((base_urlpatterns, "oauth2_provider"), namespace="oauth2_provider"),
    ),
    path("admin/", admin.site.urls),
]  # pragma: no cover
